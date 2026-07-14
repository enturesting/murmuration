"""Cumulative metrics: $ paid out, MW relief, tCO2 avoided, SLA breaches."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime

import time
from murmuration.protocol import (
    DispatchRequest, DispatchAck, MurmurationBus, GridStateUpdate, ContingencyAlert,
)


@dataclass
class Totals:
    dispatches_issued: int = 0
    dispatches_accepted: int = 0
    dispatches_declined: int = 0
    counter_offers: int = 0
    contingency_responses: int = 0
    contingency_response_ms_avg: float = 0.0
    mw_shed_minutes: float = 0.0          # MW * minutes of demand reduction
    mw_lean_minutes: float = 0.0          # MW * minutes of opportunistic uptake
    dollars_paid: float = 0.0             # comp paid by grid to compute
    tco2_avoided: float = 0.0
    # counterfactual: what would have happened if no dispatch (pure flat baseline)
    cf_dollars_paid_to_peakers: float = 0.0    # what grid would've paid in peaker spot
    cf_tco2_emitted: float = 0.0               # what fossil generation we displaced
    sla_breaches: int = 0


class MetricsTracker:
    def __init__(self, bus: MurmurationBus):
        self.bus = bus
        self.totals = Totals()
        self._pending_requests: dict[str, DispatchRequest] = {}
        self._latest_carbon: dict[str, float] = {}    # ba -> g/kWh
        self._latest_lmp: dict[str, float] = {}       # ba -> $/MWh
        self._pending_contingencies: dict[str, float] = {}
        bus.subscribe(DispatchRequest, self._on_request)
        bus.subscribe(DispatchAck, self._on_ack)
        bus.subscribe(GridStateUpdate, self._on_grid)
        bus.subscribe(ContingencyAlert, self._on_contingency)

    def _on_contingency(self, m: ContingencyAlert) -> None:
        # First-frame: just record the time. The compute agent's response time
        # is exposed via its own attribute and surfaced in the tick payload.
        self._pending_contingencies[m.alert_id] = time.monotonic()
        self.totals.contingency_responses += 1

    def _on_grid(self, m: GridStateUpdate) -> None:
        self._latest_carbon[m.ba] = m.carbon_g_kwh
        self._latest_lmp[m.ba] = m.lmp_dollars_mwh

    def _on_request(self, m: DispatchRequest) -> None:
        self.totals.dispatches_issued += 1
        self._pending_requests[m.request_id] = m

    def _on_ack(self, m: DispatchAck) -> None:
        req = self._pending_requests.pop(m.request_id, None)
        if req is None:
            return
        if m.counter_offer is not None:
            self.totals.counter_offers += 1
        if m.accepted_mw == 0:
            self.totals.dispatches_declined += 1
            return
        self.totals.dispatches_accepted += 1
        mw = abs(m.accepted_mw)
        minutes = req.duration_min
        if m.accepted_mw < 0:    # decrease
            self.totals.mw_shed_minutes += mw * minutes
            self.totals.dollars_paid += mw * (minutes / 60.0) * req.compensation_per_mwh
            ci = self._latest_carbon.get(req.ba, 400.0)
            mwh_saved = mw * (minutes / 60.0)
            self.totals.tco2_avoided += mwh_saved * ci / 1000.0
            # counterfactual: without our dispatch, the grid would have run the
            # marginal peaker at the prevailing LMP. That LMP IS what the grid
            # was paying that interval, so it's the right comparison.
            counterfactual_rate = self._latest_lmp.get(req.ba, 200.0)
            self.totals.cf_dollars_paid_to_peakers += mwh_saved * counterfactual_rate
            self.totals.cf_tco2_emitted += mwh_saved * ci / 1000.0
        else:
            self.totals.mw_lean_minutes += mw * minutes

    def snapshot(self) -> dict:
        return asdict(self.totals)
