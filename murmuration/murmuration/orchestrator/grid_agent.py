"""Grid-side agent — speaks the ISO control-room voice. Issues DispatchRequests."""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

import os
from murmuration.protocol import (
    GridStateUpdate, GridForecast, DispatchRequest, FlexibilityEnvelope,
    MurmurationBus, expires_at,
)
from murmuration.data import ISOClient, BaSnapshot
from murmuration.forecast import Forecaster, NRELClient, expected_solar_now
from murmuration.orchestrator.narrator import Narrator
from murmuration.orchestrator.tools_grid import GRID_TOOLS, GRID_SYSTEM_PROMPT

try:
    from anthropic import Anthropic
    _has_anthropic = True
except ImportError:
    _has_anthropic = False

log = logging.getLogger(__name__)


class GridAgent:
    def __init__(
        self,
        bus: MurmurationBus,
        iso: ISOClient,
        narrator: Narrator,
        bas: list[str],
        stress_threshold: float = 0.55,
    ):
        self.bus = bus
        self.iso = iso
        self.narrator = narrator
        self.bas = bas
        self.stress_threshold = stress_threshold
        self._envelopes: dict[tuple[str, str], FlexibilityEnvelope] = {}
        self._last_dispatch_at: dict[str, datetime] = {}
        self._forecasters: dict[str, Forecaster] = {ba: Forecaster() for ba in bas}
        # NREL solar profiles per BA, lazy-fetched once and cached
        self._nrel = NRELClient()
        # representative lat/lon per BA (HQ + a major load center)
        self._ba_solar_anchors = {
            "CAISO": (37.34, -121.97),    # NP15 hub area
            "ERCOT": (29.76,  -95.37),    # Houston
            "PJM":   (39.04,  -77.49),    # Loudoun, VA
        }
        self._solar_profiles: dict[str, object | None] = {}
        if self._nrel.enabled:
            log.info("NREL PVWatts client enabled — pre-fetching solar profiles")
            for ba, (lat, lon) in self._ba_solar_anchors.items():
                self._solar_profiles[ba] = self._nrel.solar_profile(lat, lon)
        self._tick_count = 0
        # Optional Claude tool-use for dispatch decisions
        self._claude = None
        self._claude_model = "claude-haiku-4-5-20251001"
        if _has_anthropic and os.getenv("ANTHROPIC_API_KEY"):
            try:
                self._claude = Anthropic()
            except Exception:
                pass
        bus.subscribe(FlexibilityEnvelope, self._on_envelope)

    def _on_envelope(self, env: FlexibilityEnvelope) -> None:
        self._envelopes[(env.ba, env.facility_id)] = env

    async def tick(self, t: datetime) -> list[GridStateUpdate]:
        updates: list[GridStateUpdate] = []
        self._tick_count += 1
        for ba in self.bas:
            snap = self.iso.snapshot(ba)
            update = self._snapshot_to_update(snap, t)
            await self.bus.publish(update)
            updates.append(update)
            self._forecasters[ba].ingest(t, snap.load_mw, snap.lmp_dollars_mwh, snap.carbon_g_kwh)
            if self._tick_count % 5 == 0:
                await self._publish_forecast(ba, t)
            if update.stress_score >= self.stress_threshold:
                await self._maybe_dispatch(ba, snap, t)
            # Surplus path: when carbon is super clean AND price is below floor,
            # signal VPPs and DCs to lean in (curtailment soak).
            elif snap.carbon_g_kwh < 60 and snap.lmp_dollars_mwh < 25:
                await self._maybe_surplus_dispatch(ba, snap, t)
        return updates

    async def _maybe_surplus_dispatch(self, ba: str, snap: BaSnapshot, t: datetime) -> None:
        """Issue a curtailment-soak request to any facility in BA with increase capacity."""
        last = self._last_dispatch_at.get(ba)
        if last and (t - last).total_seconds() < 90:
            return
        candidates = [
            (fid, env) for (b, fid), env in self._envelopes.items()
            if b == ba and any(bnd.direction == "increase" for bnd in env.bands)
        ]
        if not candidates:
            return
        # pick the largest available increase
        best_fid, best_band = None, None
        for fid, env in candidates:
            for band in env.bands:
                if band.direction == "increase" and (best_band is None or band.mw > best_band.mw):
                    best_fid, best_band = fid, band
        if best_band is None:
            return
        lean_mw = min(best_band.mw, 40.0)
        req = DispatchRequest(
            request_id=f"lean-{uuid.uuid4().hex[:8]}",
            timestamp=t,
            ba=ba,
            facility_id=best_fid,
            needed_mw=lean_mw,    # positive = lean in
            duration_min=30,
            start_within_min=2,
            compensation_per_mwh=0,    # surplus: no payment needed
            priority="economic",
            reason=(
                f"{ba} surplus: carbon {snap.carbon_g_kwh:.0f} g/kWh, "
                f"LMP ${snap.lmp_dollars_mwh:.0f}/MWh — would otherwise curtail. Soak it."
            ),
            valid_until=expires_at(t, 5),
        )
        await self.bus.publish(req)
        self._last_dispatch_at[ba] = t
        log.info("grid_agent SURPLUS-LEAN-IN %s for %s -> %s (+%.0f MW)",
                 req.request_id, ba, best_fid, lean_mw)

    async def _publish_forecast(self, ba: str, t: datetime) -> None:
        f = self._forecasters[ba].forecast(t, horizon_min=60, interval_min=5)

        # Bend carbon forecast using NREL TMY solar shape: more expected solar
        # → lower expected carbon. Multiplier is 1.0 baseline, dropping by up
        # to ~25% at solar peak (capacity factor scaled).
        prof = self._solar_profiles.get(ba)
        carbon = list(f["carbon"])
        if prof is not None:
            for i in range(len(carbon)):
                future_t = datetime.fromtimestamp(
                    t.timestamp() + i * f["interval_min"] * 60, tz=t.tzinfo,
                )
                solar_frac = expected_solar_now(prof, future_t)    # 0..~0.7
                # damp: solar=0 -> 1.0x, solar=0.5 -> 0.85x, solar=0.7 -> 0.78x
                carbon[i] = carbon[i] * max(0.7, 1.0 - solar_frac * 0.45)

        msg = GridForecast(
            timestamp=t,
            ba=ba,
            horizon_min=f["horizon_min"],
            interval_min=f["interval_min"],
            lmp_forecast=f["lmp"],
            load_forecast=f["load"],
            carbon_forecast=carbon,
            confidence_band=f["confidence"],
            valid_until=expires_at(t, 15),
        )
        await self.bus.publish(msg)
        if f.get("trained"):
            log.debug("GBM forecast for %s · n_samples=%d · NREL=%s",
                      ba, f["n_samples"], "yes" if prof else "no")

    @staticmethod
    def _snapshot_to_update(snap: BaSnapshot, t: datetime) -> GridStateUpdate:
        return GridStateUpdate(
            timestamp=t,
            ba=snap.ba,
            node_id=f"{snap.ba}-MAIN",
            lmp_dollars_mwh=snap.lmp_dollars_mwh,
            load_mw=snap.load_mw,
            headroom_mw=snap.headroom_mw,
            carbon_g_kwh=snap.carbon_g_kwh,
            stress_score=snap.stress_score,
            valid_until=expires_at(t, 5),
            notes=snap.notes,
        )

    async def _maybe_dispatch(self, ba: str, snap: BaSnapshot, t: datetime) -> None:
        # find a facility envelope in this BA
        candidates = [
            (fid, env) for (b, fid), env in self._envelopes.items()
            if b == ba and any(bnd.direction == "decrease" for bnd in env.bands)
        ]
        if not candidates:
            return
        # don't re-issue dispatch within 8 sec of last one for same BA
        last = self._last_dispatch_at.get(ba)
        if last and (t - last).total_seconds() < 8:
            return

        # Claude-decided path (if API key set). Falls back to rule-based on any error.
        if self._claude is not None:
            try:
                req = await self._claude_pick_dispatch(ba, snap, candidates, t)
                if req is not None:
                    await self.bus.publish(req)
                    self._last_dispatch_at[ba] = t
                    log.info("grid_agent (CLAUDE) issued %s for %s -> %s (%.0f MW)",
                             req.request_id, ba, req.facility_id, req.needed_mw)
                    return
                # Claude said no_action; respect that
                return
            except Exception:
                log.exception("Claude dispatch failed; falling back to rule-based")

        # Rule-based path
        req = self._rule_pick_dispatch(ba, snap, candidates, t)
        if req is None:
            return
        await self.bus.publish(req)
        self._last_dispatch_at[ba] = t
        log.info("grid_agent (rule) issued %s for %s -> %s (%.0f MW)",
                 req.request_id, ba, req.facility_id, req.needed_mw)

        # Fan out: ALSO send a smaller dispatch to any VPP-style aggregator in
        # this BA (so multi-asset-class response is visible in the demo).
        await self._fanout_to_vpp(ba, snap, candidates, primary_facility=req.facility_id, t=t)

    async def _fanout_to_vpp(self, ba, snap, candidates, primary_facility, t):
        for fid, env in candidates:
            if fid == primary_facility:
                continue
            if not fid.startswith("VPP"):
                continue
            # find any decrease band on this aggregator
            decrease_total = sum(b.mw for b in env.bands if b.direction == "decrease")
            if decrease_total <= 0:
                continue
            ask = min(decrease_total * 0.7, 0.8)    # ask for 70% of capacity, capped at 0.8 MW
            req = DispatchRequest(
                request_id=f"vpp-{uuid.uuid4().hex[:8]}",
                timestamp=t,
                ba=ba,
                facility_id=fid,
                needed_mw=-ask,
                duration_min=30,
                start_within_min=2,
                compensation_per_mwh=max(snap.lmp_dollars_mwh * 0.6, 60.0),
                priority="economic",
                reason=f"{ba} aggregator participation alongside large-load dispatch",
                valid_until=expires_at(t, 5),
            )
            await self.bus.publish(req)
            log.info("grid_agent fanout %s for %s -> %s (-%.2f MW)",
                     req.request_id, ba, fid, ask)
            return    # one VPP per fanout

    def _rule_pick_dispatch(self, ba: str, snap: BaSnapshot, candidates, t: datetime) -> "DispatchRequest | None":
        target_relief = min(180.0, snap.stress_score * 250.0)
        best_facility, best_band = None, None
        for fid, env in candidates:
            for band in env.bands:
                if band.direction != "decrease":
                    continue
                if band.mw + 5 < target_relief:
                    continue
                if best_band is None or band.cost_per_mwh < best_band.cost_per_mwh:
                    best_facility, best_band = fid, band
        if best_band is None:
            for fid, env in candidates:
                for band in env.bands:
                    if band.direction == "decrease" and (best_band is None or band.mw > best_band.mw):
                        best_facility, best_band = fid, band
        if best_band is None:
            return None
        accepted_mw = min(best_band.mw, target_relief)
        compensation = max(snap.lmp_dollars_mwh * 0.7, 80.0)
        return DispatchRequest(
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            timestamp=t,
            ba=ba,
            facility_id=best_facility,
            needed_mw=-accepted_mw,
            duration_min=min(best_band.for_min, 90),
            start_within_min=2,
            compensation_per_mwh=compensation,
            priority="reliability" if snap.stress_score > 0.8 else "economic",
            reason=(
                f"{ba} stress {snap.stress_score:.2f}, LMP "
                f"${snap.lmp_dollars_mwh:.0f}/MWh, headroom "
                f"{snap.headroom_mw:,.0f} MW"
            ),
            valid_until=expires_at(t, 5),
        )

    async def _claude_pick_dispatch(self, ba, snap, candidates, t) -> "DispatchRequest | None":
        """Single-turn tool-use: feed Claude the situation and let it pick."""
        # build a compact text description of the envelopes
        env_text = []
        for fid, env in candidates:
            for band in env.bands:
                if band.direction != "decrease":
                    continue
                env_text.append(
                    f"  {fid}: can shed {band.mw:.0f} MW for {band.for_min} min, "
                    f"cost ${band.cost_per_mwh}/MWh, class={band.workload_class}, "
                    f"floor={env.cannot_go_below_mw:.0f} MW"
                )
        situation = (
            f"BA: {ba}\n"
            f"Stress: {snap.stress_score:.2f}\n"
            f"LMP: ${snap.lmp_dollars_mwh:.0f}/MWh\n"
            f"Headroom: {snap.headroom_mw:,.0f} MW\n"
            f"Carbon: {snap.carbon_g_kwh:.0f} g/kWh\n"
            f"Standing envelopes:\n" + "\n".join(env_text)
        )
        # use prompt caching on the static system prompt + tools
        msg = self._claude.messages.create(
            model=self._claude_model,
            max_tokens=400,
            system=[
                {"type": "text", "text": GRID_SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}},
            ],
            tools=GRID_TOOLS,
            messages=[{"role": "user", "content": situation}],
        )
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                if block.name == "no_action":
                    return None
                if block.name == "issue_dispatch":
                    inp = block.input
                    return DispatchRequest(
                        request_id=f"req-{uuid.uuid4().hex[:8]}",
                        timestamp=t,
                        ba=inp["ba"],
                        facility_id=inp["facility_id"],
                        needed_mw=float(inp["needed_mw"]),
                        duration_min=int(inp["duration_min"]),
                        start_within_min=2,
                        compensation_per_mwh=float(inp["compensation_per_mwh"]),
                        priority=inp["priority"],
                        reason=inp["reason"],
                        valid_until=expires_at(t, 5),
                    )
        return None

    async def narrate_dispatch(self, req: DispatchRequest) -> str:
        ctx = (
            f"Issued {req.request_id}: {req.ba} requesting "
            f"{abs(req.needed_mw):.0f} MW shed at {req.facility_id} "
            f"for {req.duration_min} min @ ${req.compensation_per_mwh:.0f}/MWh "
            f"({req.priority} priority). {req.reason}"
        )
        return self.narrator.narrate("grid", ctx)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
