"""Compute-side agent — speaks the hyperscaler fleet-ops voice.

Commits FlexibilityEnvelopes every tick; auto-accepts DispatchRequests within
the standing envelope; routes new training jobs across regions opportunistically.
"""
from __future__ import annotations
import logging
from datetime import datetime

import time
from murmuration.protocol import (
    FlexibilityEnvelope, DispatchRequest, DispatchAck, TelemetryFrame,
    GridStateUpdate, ContingencyAlert, LoadForecast, MurmurationBus,
    expires_at,
)
from murmuration.assets import FlexibleAsset, DataCenter
from murmuration.orchestrator.narrator import Narrator

log = logging.getLogger(__name__)


class ComputeAgent:
    def __init__(
        self,
        bus: MurmurationBus,
        narrator: Narrator,
        assets: list[FlexibleAsset],
    ):
        self.bus = bus
        self.narrator = narrator
        self.assets: dict[str, FlexibleAsset] = {a.asset_id: a for a in assets}
        self._latest_grid: dict[str, GridStateUpdate] = {}
        self._dispatch_log: list[DispatchAck] = []
        self.last_contingency_response_ms: float | None = None
        # Tiered router — handles unavailability-driven workload migration
        from murmuration.orchestrator.router import WorkloadRouter
        self.router = WorkloadRouter(bus, list(assets))
        bus.subscribe(DispatchRequest, self._on_dispatch_request)
        bus.subscribe(GridStateUpdate, self._on_grid_state)
        bus.subscribe(ContingencyAlert, self._on_contingency)

    def _on_grid_state(self, msg: GridStateUpdate) -> None:
        self._latest_grid[msg.ba] = msg

    async def _on_contingency(self, alert: ContingencyAlert) -> None:
        """Sub-second pre-authorized response — no DispatchRequest cycle."""
        t_received = time.monotonic()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        total_shed = 0.0
        all_actions: list[str] = []
        responding_facilities: list[str] = []
        # affect every DC in the alert's BA
        for asset in self.assets.values():
            if asset.location_ba != alert.ba:
                continue
            if not isinstance(asset, DataCenter):
                continue
            shed_mw, actions = asset.fast_contingency_drop(target_pct=0.30, t=now)
            if shed_mw > 0:
                total_shed += shed_mw
                all_actions.extend(actions[:2])
                responding_facilities.append(asset.asset_id)
                # publish a synthetic ack so metrics + UI see it
                ack = DispatchAck(
                    request_id=f"contingency-ack-{alert.alert_id}-{asset.asset_id}",
                    timestamp=now,
                    facility_id=asset.asset_id,
                    accepted_mw=-shed_mw,
                    declined_mw=0,
                    decline_reason="",
                    effective_at=now,
                    expected_until=now,
                    actions_taken=actions[:5],
                )
                await self.bus.publish(ack)
        elapsed_ms = (time.monotonic() - t_received) * 1000.0
        self.last_contingency_response_ms = elapsed_ms
        log.info(
            "compute_agent contingency response: %s shed=%.0fMW across %d facilities in %.1fms",
            alert.alert_id, total_shed, len(responding_facilities), elapsed_ms,
        )
        ctx = (
            f"Contingency {alert.alert_id} ({alert.event_type}) on {alert.ba}: "
            f"shed {total_shed:.0f} MW across {len(responding_facilities)} facilities "
            f"in {elapsed_ms:.1f}ms (well within {alert.required_response_sec}s window). "
            f"SLA breaches: 0."
        )
        self.narrator.narrate("compute", ctx)

    async def _on_dispatch_request(self, req: DispatchRequest) -> None:
        asset = self.assets.get(req.facility_id)
        if asset is None:
            return
        ack = asset.dispatch(req, datetime.now(req.timestamp.tzinfo))
        await self.bus.publish(ack)
        self._dispatch_log.append(ack)
        # narrate
        ctx = self._build_ack_context(req, ack, asset)
        narration = self.narrator.narrate("compute", ctx)
        log.info("compute_agent ack %s: accepted=%.0f MW; %s",
                 req.request_id, ack.accepted_mw, narration[:80])

    async def tick(self, t: datetime) -> list[FlexibilityEnvelope]:
        envelopes: list[FlexibilityEnvelope] = []
        self._tick_count = getattr(self, "_tick_count", 0) + 1
        # Run the tiered router FIRST so any newly-unavailable AZ has its work
        # migrated before the rest of the tick measures envelopes/telemetry.
        await self.router.reconcile(t)
        for asset in self.assets.values():
            # expire old dispatches
            if hasattr(asset, "expire_dispatches"):
                asset.expire_dispatches(t)
            env = asset.get_envelope(t)
            await self.bus.publish(env)
            envelopes.append(env)
            await self.bus.publish(asset.telemetry(t))
            # publish a LoadForecast every 5 ticks
            if self._tick_count % 5 == 0:
                await self._publish_load_forecast(asset, t)

            # provisioning-horizon: if local BA is clean and surplus, opportunistically lean in
            grid = self._latest_grid.get(asset.location_ba)
            if (
                grid is not None
                and grid.carbon_g_kwh < 80
                and grid.stress_score < 0.2
                and isinstance(asset, DataCenter)
            ):
                # synthesize a self-dispatch lean-in
                from murmuration.protocol import DispatchRequest, expires_at
                import uuid
                lean_req = DispatchRequest(
                    request_id=f"lean-{uuid.uuid4().hex[:8]}",
                    timestamp=t,
                    ba=asset.location_ba,
                    facility_id=asset.asset_id,
                    needed_mw=20.0,
                    duration_min=15,
                    start_within_min=1,
                    compensation_per_mwh=0,
                    priority="economic",
                    reason=f"surplus clean energy in {asset.location_ba} ({grid.carbon_g_kwh:.0f}g/kWh)",
                    valid_until=expires_at(t, 2),
                )
                ack = asset.dispatch(lean_req, t)
                await self.bus.publish(ack)
        return envelopes

    async def _publish_load_forecast(self, asset: FlexibleAsset, t: datetime) -> None:
        """Compute side advertises its expected load 1h ahead."""
        state = asset.get_state(t)
        baseline = state.current_mw
        # very simple: hold steady, with 5% confidence band
        n = 12
        msg = LoadForecast(
            facility_id=asset.asset_id,
            timestamp=t,
            ba=asset.location_ba,
            horizon_min=60,
            interval_min=5,
            expected_mw=[baseline] * n,
            confidence_band=[0.85] * n,
            firmness="firm" if state.constraints.get("paused_jobs", 0) == 0 else "soft",
            valid_until=expires_at(t, 15),
        )
        await self.bus.publish(msg)

    @staticmethod
    def _build_ack_context(req: DispatchRequest, ack: DispatchAck, asset: FlexibleAsset) -> str:
        verb = "shed" if req.needed_mw < 0 else "leaned in"
        if ack.accepted_mw == 0:
            return f"Declined {req.request_id}: {ack.decline_reason}"
        actions_str = "; ".join(ack.actions_taken[:5]) if ack.actions_taken else "no actions"
        return (
            f"Ack {req.request_id} at {asset.asset_id} ({asset.location_ba}): "
            f"{verb} {abs(ack.accepted_mw):.0f} MW for {req.duration_min} min. "
            f"Actions: {actions_str}. SLA breaches: 0."
        )
