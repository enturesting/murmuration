"""HomeBattery + HomeAggregator — the #2 flagship client.

Each HomeBattery is a tiny FlexibleAsset (~5 kW peak, ~13 kWh capacity).
A HomeAggregator bundles many homes and exposes ONE FlexibilityEnvelope to
the protocol — identical schema to a DataCenter envelope. This is the proof
that the protocol scales six orders of magnitude with no schema change.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import random
import uuid

from murmuration.protocol import (
    FlexibilityBand, FlexibilityEnvelope, DispatchRequest, DispatchAck,
    TelemetryFrame, expires_at,
)
from murmuration.assets.base import FlexibleAsset, AssetState

log = logging.getLogger(__name__)


@dataclass
class HomeBattery:
    home_id: str
    capacity_kwh: float = 13.5     # ~Powerwall
    max_kw: float = 5.0
    soc: float = 0.65              # 0..1
    owner_reserve: float = 0.30    # never discharge below 30%
    ev_charging_kw: float = 0.0    # if EV plugged in & charging
    ev_departure_min: int | None = None
    thermostat_band: float = 1.0   # degrees of comfort flex
    opted_in: bool = True
    paused_charging: bool = False
    discharging: bool = False
    lat: float = 0.0
    lon: float = 0.0

    def usable_kwh(self) -> float:
        return max(0.0, self.capacity_kwh * (self.soc - self.owner_reserve))

    def discharge_capacity_kw(self) -> float:
        if not self.opted_in:
            return 0.0
        if self.usable_kwh() < 0.2:
            return 0.0
        return self.max_kw

    def discharge_duration_min(self) -> int:
        if self.max_kw <= 0:
            return 0
        return int((self.usable_kwh() / self.max_kw) * 60)

    def ev_pause_capacity_kw(self) -> float:
        if not self.opted_in or self.ev_charging_kw <= 0:
            return 0.0
        if self.ev_departure_min is not None and self.ev_departure_min < 60:
            return 0.0    # leaving soon, can't pause
        return self.ev_charging_kw

    def thermostat_capacity_kw(self) -> float:
        # rough: 0.6 kW reduction per °F of comfort flex
        if not self.opted_in:
            return 0.0
        return self.thermostat_band * 0.6


class HomeAggregator(FlexibleAsset):
    """One facility-shaped wrapper around N homes. Exposes one envelope."""

    def __init__(
        self,
        asset_id: str,
        location_ba: str,
        node_id: str,
        homes: list[HomeBattery],
        lat: float,
        lon: float,
    ):
        self.asset_id = asset_id
        self.asset_type = "vpp_aggregator"
        self.location_ba = location_ba
        self.node_id = node_id
        self.homes = homes
        self.lat = lat
        self.lon = lon
        self._active_dispatches: dict[str, dict] = {}

    # ---- aggregate accounting ----
    def baseline_mw(self) -> float:
        # baseline = current household consumption (rough: 1.5 kW avg + EV charging)
        avg_household_kw = 1.5
        ev = sum(h.ev_charging_kw for h in self.homes if not h.paused_charging)
        return (avg_household_kw * len(self.homes) + ev) / 1000.0    # kW -> MW

    def current_mw(self, t: datetime | None = None) -> float:
        baseline = self.baseline_mw()
        for d in self._active_dispatches.values():
            if t is None or t < d["expires_at"]:
                baseline -= d["shed_mw"]
        return max(0.0, baseline)

    # ---- protocol surface ----
    def get_state(self, t: datetime) -> AssetState:
        opted_in = sum(1 for h in self.homes if h.opted_in)
        avg_soc = sum(h.soc for h in self.homes) / max(len(self.homes), 1)
        return AssetState(
            asset_id=self.asset_id,
            asset_type=self.asset_type,
            location_ba=self.location_ba,
            node_id=self.node_id,
            current_mw=self.current_mw(t),
            nominal_max_mw=self._nominal_max_mw(),
            constraints={
                "homes_total": len(self.homes),
                "homes_opted_in": opted_in,
                "homes_responding": sum(1 for h in self.homes if h.discharging or h.paused_charging),
                "avg_soc": round(avg_soc, 2),
            },
        )

    def _nominal_max_mw(self) -> float:
        return sum(h.max_kw for h in self.homes) / 1000.0

    def get_envelope(self, t: datetime, horizon_min: int = 240) -> FlexibilityEnvelope:
        # build separate bands per resource type
        battery_kw = sum(h.discharge_capacity_kw() for h in self.homes)
        battery_minutes = (
            sum(h.discharge_duration_min() * h.discharge_capacity_kw() for h in self.homes) /
            max(battery_kw, 1.0)
        )
        ev_kw = sum(h.ev_pause_capacity_kw() for h in self.homes)
        thermostat_kw = sum(h.thermostat_capacity_kw() for h in self.homes)

        bands: list[FlexibilityBand] = []
        if battery_kw > 0:
            bands.append(FlexibilityBand(
                direction="decrease",
                mw=battery_kw / 1000.0,
                for_min=min(int(battery_minutes), horizon_min),
                workload_class="batch_infer",   # closest analog for VPP class
                cost_per_mwh=120,
                constraint_notes=f"{sum(1 for h in self.homes if h.discharge_capacity_kw() > 0)} home batteries above reserve floor",
            ))
        if ev_kw > 0:
            bands.append(FlexibilityBand(
                direction="decrease",
                mw=ev_kw / 1000.0,
                for_min=min(60, horizon_min),
                workload_class="batch_infer",
                cost_per_mwh=70,
                constraint_notes=f"{sum(1 for h in self.homes if h.ev_pause_capacity_kw() > 0)} EVs not departing within 60 min",
            ))
        if thermostat_kw > 0:
            bands.append(FlexibilityBand(
                direction="decrease",
                mw=thermostat_kw / 1000.0,
                for_min=min(120, horizon_min),
                workload_class="batch_infer",
                cost_per_mwh=40,
                constraint_notes="thermostat setpoint nudge ±1°F (within owner comfort)",
            ))

        return FlexibilityEnvelope(
            facility_id=self.asset_id,
            timestamp=t,
            ba=self.location_ba,
            node_id=self.node_id,
            baseline_mw=self.baseline_mw(),
            bands=bands,
            cannot_go_below_mw=0.0,    # homes can go to zero net consumption
            data_locality_constraints=[self.location_ba],
            valid_until=expires_at(t, 5),
        )

    def dispatch(self, req: DispatchRequest, t: datetime) -> DispatchAck:
        if req.facility_id != self.asset_id:
            return self._decline(req, t, "wrong facility")
        if req.needed_mw >= 0:
            return self._decline(req, t, "VPP only supports decrease (no lean-in)")
        need_kw = abs(req.needed_mw) * 1000.0
        actions: list[str] = []

        # ranking: cheapest first (thermostat, then EV, then battery)
        plans = self._build_response_plan(need_kw)
        actually_kw = self._execute_plan(plans, actions)
        accepted_mw = -(actually_kw / 1000.0)
        declined_mw = -((need_kw - actually_kw) / 1000.0) if actually_kw < need_kw else 0.0

        self._active_dispatches[req.request_id] = {
            "shed_mw": actually_kw / 1000.0,
            "expires_at": t + timedelta(minutes=req.duration_min),
            "plans": plans,
        }

        return DispatchAck(
            request_id=req.request_id,
            timestamp=t,
            facility_id=self.asset_id,
            accepted_mw=accepted_mw,
            declined_mw=declined_mw,
            decline_reason="" if declined_mw == 0 else "exceeds aggregate flexibility",
            effective_at=t,
            expected_until=t + timedelta(minutes=req.duration_min),
            actions_taken=actions[:8],
        )

    def telemetry(self, t: datetime) -> TelemetryFrame:
        return TelemetryFrame(
            facility_id=self.asset_id,
            timestamp=t,
            actual_mw=self.current_mw(t),
            power_factor=0.97,
            queue_depth=sum(1 for h in self.homes if h.discharging or h.paused_charging),
            active_dispatches=[d for d, s in self._active_dispatches.items() if t < s["expires_at"]],
        )

    def expire_dispatches(self, t: datetime) -> None:
        expired = [rid for rid, s in self._active_dispatches.items() if t >= s["expires_at"]]
        for rid in expired:
            for home in self.homes:
                home.discharging = False
                home.paused_charging = False
            del self._active_dispatches[rid]

    # ---- internals ----
    def _decline(self, req, t, reason):
        return DispatchAck(
            request_id=req.request_id,
            timestamp=t,
            facility_id=self.asset_id,
            accepted_mw=0,
            declined_mw=req.needed_mw,
            decline_reason=reason,
            effective_at=t,
            expected_until=t,
            actions_taken=[],
        )

    def _build_response_plan(self, need_kw: float) -> dict:
        """Pick cheapest mix of thermostat/EV/battery to hit need_kw."""
        plan = {"thermostat": [], "ev": [], "battery": [], "opt_out": []}
        remaining = need_kw

        # 1) thermostat nudges
        for h in self.homes:
            if remaining <= 0: break
            cap = h.thermostat_capacity_kw()
            if cap > 0 and h.opted_in:
                plan["thermostat"].append(h)
                remaining -= cap

        # 2) EV pauses
        for h in self.homes:
            if remaining <= 0: break
            cap = h.ev_pause_capacity_kw()
            if cap > 0:
                plan["ev"].append(h)
                remaining -= cap

        # 3) battery discharge
        for h in self.homes:
            if remaining <= 0: break
            cap = h.discharge_capacity_kw()
            if cap > 0:
                plan["battery"].append(h)
                remaining -= cap

        # mark non-respondents (for visualization)
        responders = set(id(h) for grp in plan.values() for h in grp)
        for h in self.homes:
            if id(h) not in responders:
                plan["opt_out"].append(h)
        return plan

    def _execute_plan(self, plan: dict, actions: list[str]) -> float:
        kw = 0.0
        for h in plan["thermostat"]:
            kw += h.thermostat_capacity_kw()
        if plan["thermostat"]:
            actions.append(f"{len(plan['thermostat'])} thermostats nudged ±1°F")
        for h in plan["ev"]:
            h.paused_charging = True
            kw += h.ev_pause_capacity_kw()
        if plan["ev"]:
            actions.append(f"{len(plan['ev'])} EV chargers paused")
        for h in plan["battery"]:
            h.discharging = True
            kw += h.discharge_capacity_kw()
        if plan["battery"]:
            actions.append(f"{len(plan['battery'])} home batteries discharging")
        if plan["opt_out"]:
            actions.append(f"{len(plan['opt_out'])} opted out (comfort/EV/SOC constraints)")
        return kw


def make_bay_area_vpp(seed: int = 7) -> HomeAggregator:
    """100 simulated homes scattered across the SF Bay Area."""
    rnd = random.Random(seed)
    homes: list[HomeBattery] = []
    # bay area cluster: roughly 37.3–37.85 N, -122.5 to -121.85 W
    for i in range(100):
        lat = 37.3 + rnd.random() * 0.55
        lon = -122.5 + rnd.random() * 0.65
        soc = 0.5 + rnd.random() * 0.45
        ev_charging = rnd.choice([0.0, 0.0, 0.0, 7.2, 11.5])      # ~40% EVs, half charging
        ev_dep = None if ev_charging == 0 else rnd.randint(45, 600)
        homes.append(HomeBattery(
            home_id=f"home-{i:03d}",
            capacity_kwh=rnd.choice([10.0, 13.5, 13.5, 16.0]),
            max_kw=rnd.choice([3.5, 5.0, 5.0, 7.6]),
            soc=soc,
            owner_reserve=rnd.choice([0.20, 0.30, 0.30, 0.40]),
            ev_charging_kw=ev_charging,
            ev_departure_min=ev_dep,
            thermostat_band=rnd.choice([0.0, 0.5, 1.0, 1.5, 2.0]),
            opted_in=rnd.random() > 0.07,    # 93% opt-in
            lat=lat, lon=lon,
        ))
    return HomeAggregator(
        asset_id="VPP-CA-Bay",
        location_ba="CAISO",
        node_id="CAISO-NP15",
        homes=homes,
        lat=37.55, lon=-122.15,
    )
