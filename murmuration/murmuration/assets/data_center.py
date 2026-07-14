"""DataCenter — the #1 flagship client. A fleet of jobs across workload classes."""
from __future__ import annotations
from datetime import datetime, timedelta
import logging

from murmuration.protocol import (
    FlexibilityBand, FlexibilityEnvelope, DispatchRequest, DispatchAck,
    CounterOffer, TelemetryFrame, expires_at,
)
from murmuration.assets.base import FlexibleAsset, AssetState, Job

log = logging.getLogger(__name__)


# how each workload class behaves under throttle pressure
CLASS_PROFILE = {
    "training":     {"flex_cost": 20,  "preempt_priority": 1},
    "fine_tune":    {"flex_cost": 40,  "preempt_priority": 2},
    "embedding":    {"flex_cost": 50,  "preempt_priority": 3},
    "batch_infer":  {"flex_cost": 80,  "preempt_priority": 4},
    "online_serve": {"flex_cost": 9999,"preempt_priority": 99},  # ~immutable
}


class DataCenter(FlexibleAsset):
    """A simulated GW-scale data center.

    Tracks a list of jobs across workload classes and maintains a throttle
    factor per active dispatch. The serving floor is hard-enforced.
    """

    def __init__(
        self,
        asset_id: str,
        location_ba: str,
        node_id: str,
        nominal_max_mw: float,
        serving_floor_mw: float,
        jobs: list[Job],
        eligible_regions: list[str] | None = None,
    ):
        self.asset_id = asset_id
        self.asset_type = "data_center"
        self.location_ba = location_ba
        self.node_id = node_id
        self.nominal_max_mw = nominal_max_mw
        self.serving_floor_mw = serving_floor_mw
        self.jobs = jobs
        self.eligible_regions = eligible_regions or [location_ba]
        self._active_dispatches: dict[str, dict] = {}    # request_id -> state
        # AZ-level health: when True, this AZ's substation is overloaded and the
        # AZ exposes ZERO flexibility. Grid agent's dispatcher will pass over it
        # and pick a sibling AZ in the same region. Set by ScenarioManager.
        self.unavailable: bool = False

    # ---- power accounting ----
    def current_mw(self, t: datetime | None = None) -> float:
        active = sum(j.mw for j in self.jobs if not j.paused)
        # active dispatches subtract additional MW
        for d in self._active_dispatches.values():
            if t is None or t < d["expires_at"]:
                active -= d["shed_mw"]
        return max(self.serving_floor_mw, active)

    # ---- protocol surface ----
    def get_state(self, t: datetime) -> AssetState:
        return AssetState(
            asset_id=self.asset_id,
            asset_type=self.asset_type,
            location_ba=self.location_ba,
            node_id=self.node_id,
            current_mw=self.current_mw(t),
            nominal_max_mw=self.nominal_max_mw,
            constraints={
                "serving_floor_mw": self.serving_floor_mw,
                "active_jobs": sum(1 for j in self.jobs if not j.paused),
                "paused_jobs": sum(1 for j in self.jobs if j.paused),
                "unavailable": self.unavailable,
            },
        )

    def get_envelope(self, t: datetime, horizon_min: int = 240) -> FlexibilityEnvelope:
        baseline = self.current_mw(t)
        bands: list[FlexibilityBand] = []
        # AZ unavailable: expose zero flexibility so grid agent picks a sibling
        if self.unavailable:
            return FlexibilityEnvelope(
                facility_id=self.asset_id, timestamp=t, ba=self.location_ba,
                node_id=self.node_id, baseline_mw=baseline, bands=[],
                cannot_go_below_mw=self.serving_floor_mw,
                data_locality_constraints=self.eligible_regions,
                valid_until=expires_at(t, 5),
            )

        # build decrease bands by aggregating jobs by class, sorted by preempt priority
        by_cls: dict[str, list[Job]] = {}
        for j in self.jobs:
            if j.paused:
                continue
            if j.workload_class == "online_serve":
                continue
            by_cls.setdefault(j.workload_class, []).append(j)

        for cls in sorted(by_cls, key=lambda c: CLASS_PROFILE[c]["preempt_priority"]):
            mw = sum(j.mw for j in by_cls[cls])
            if mw < 0.1:
                continue
            cap_min = horizon_min if cls == "training" else min(horizon_min, 240)
            bands.append(FlexibilityBand(
                direction="decrease",
                mw=mw,
                for_min=cap_min,
                workload_class=cls,
                cost_per_mwh=CLASS_PROFILE[cls]["flex_cost"],
                constraint_notes=f"{len(by_cls[cls])} {cls} jobs, checkpointable",
            ))

        # increase band: how much can we lean in if there's surplus clean energy
        ramp_up = max(0.0, self.nominal_max_mw - baseline) * 0.7
        if ramp_up > 1:
            bands.append(FlexibilityBand(
                direction="increase",
                mw=ramp_up,
                for_min=horizon_min,
                workload_class="training",
                cost_per_mwh=15,
                constraint_notes="queue-fed: pull more training from global queue",
            ))

        return FlexibilityEnvelope(
            facility_id=self.asset_id,
            timestamp=t,
            ba=self.location_ba,
            node_id=self.node_id,
            baseline_mw=baseline,
            bands=bands,
            cannot_go_below_mw=self.serving_floor_mw,
            data_locality_constraints=self.eligible_regions,
            valid_until=expires_at(t, 5),
        )

    def dispatch(self, req: DispatchRequest, t: datetime) -> DispatchAck:
        # only honor requests for this facility
        if req.facility_id != self.asset_id:
            return self._decline(req, t, "wrong facility")

        target = req.needed_mw
        envelope = self.get_envelope(t, horizon_min=req.duration_min)
        decrease_capacity = sum(b.mw for b in envelope.bands if b.direction == "decrease")
        increase_capacity = sum(b.mw for b in envelope.bands if b.direction == "increase")

        actions: list[str] = []
        if target < 0:    # decrease
            need = abs(target)
            counter: CounterOffer | None = None
            if need > decrease_capacity:
                accepted = -decrease_capacity
                declined = -(need - decrease_capacity)
                reason = "exceeds decrease envelope at requested duration"
                # counter-offer: same MW request, but shorter duration we *can* honor
                # (training jobs pause cheaply for short windows)
                shorter = max(15, req.duration_min // 3)
                if shorter < req.duration_min:
                    counter = CounterOffer(
                        proposed_mw=target,    # full requested MW
                        proposed_duration_min=shorter,
                        proposed_compensation_per_mwh=req.compensation_per_mwh,
                        reason=f"can honor full {abs(target):.0f} MW for {shorter} min instead of {req.duration_min} min",
                    )
            else:
                accepted = -need
                declined = 0.0
                reason = ""
            shed = abs(accepted)
            self._pause_jobs_to_match(shed, actions, t)
            self._active_dispatches[req.request_id] = {
                "shed_mw": shed,
                "expires_at": t + timedelta(minutes=req.duration_min),
            }
            return DispatchAck(
                request_id=req.request_id,
                timestamp=t,
                facility_id=self.asset_id,
                accepted_mw=accepted,
                declined_mw=declined,
                decline_reason=reason,
                effective_at=t,
                expected_until=t + timedelta(minutes=req.duration_min),
                actions_taken=actions,
                counter_offer=counter,
            )
        else:    # lean in
            available = increase_capacity
            accepted = min(target, available)
            self._add_jobs(accepted, actions, t)
            self._active_dispatches[req.request_id] = {
                "shed_mw": -accepted,    # negative = we added load
                "expires_at": t + timedelta(minutes=req.duration_min),
            }
            return DispatchAck(
                request_id=req.request_id,
                timestamp=t,
                facility_id=self.asset_id,
                accepted_mw=accepted,
                declined_mw=max(0, target - accepted),
                decline_reason="" if accepted == target else "exceeds increase envelope",
                effective_at=t,
                expected_until=t + timedelta(minutes=req.duration_min),
                actions_taken=actions,
            )

    def telemetry(self, t: datetime) -> TelemetryFrame:
        return TelemetryFrame(
            facility_id=self.asset_id,
            timestamp=t,
            actual_mw=self.current_mw(t),
            power_factor=0.98,
            queue_depth=sum(1 for j in self.jobs if j.paused),
            active_dispatches=[d for d, s in self._active_dispatches.items()
                               if t < s["expires_at"]],
        )

    def report(self, since: datetime, until: datetime) -> dict:
        return {
            "asset_id": self.asset_id,
            "active_jobs": sum(1 for j in self.jobs if not j.paused),
            "paused_jobs": sum(1 for j in self.jobs if j.paused),
            "active_dispatches": len(self._active_dispatches),
        }

    # ---- internals ----
    def _decline(self, req: DispatchRequest, t: datetime, reason: str) -> DispatchAck:
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

    def _pause_jobs_to_match(self, shed_mw: float, actions: list[str], t: datetime) -> None:
        ordered = sorted(
            (j for j in self.jobs if not j.paused and j.workload_class != "online_serve"),
            key=lambda j: (CLASS_PROFILE[j.workload_class]["preempt_priority"], -j.mw),
        )
        accumulated = 0.0
        for j in ordered:
            if accumulated >= shed_mw:
                break
            j.paused = True
            accumulated += j.mw
            actions.append(f"paused {j.job_id} ({j.workload_class}, {j.mw:.0f}MW)")

    def _add_jobs(self, lean_mw: float, actions: list[str], t: datetime) -> None:
        # resume paused jobs first
        ordered = sorted(
            (j for j in self.jobs if j.paused),
            key=lambda j: -j.mw,
        )
        accumulated = 0.0
        for j in ordered:
            if accumulated >= lean_mw:
                break
            j.paused = False
            accumulated += j.mw
            actions.append(f"resumed {j.job_id} ({j.workload_class}, {j.mw:.0f}MW)")
        if accumulated < lean_mw:
            actions.append(f"pulled {lean_mw - accumulated:.0f}MW more from global training queue")

    def take_jobs(self, jobs: list[Job]) -> None:
        """Receive migrated jobs from another DC. Mark them un-paused so they run."""
        for j in jobs:
            j.paused = False
            self.jobs.append(j)

    def release_jobs(self, target_mw: float, classes: tuple[str, ...] = ("training", "fine_tune", "batch_infer")) -> list[Job]:
        """Remove and return jobs totaling up to target_mw, picking from the
        given workload classes. Used by the router as the source side of a migration."""
        out: list[Job] = []
        accumulated = 0.0
        # snapshot the current list since we'll mutate it
        eligible = [j for j in self.jobs if j.workload_class in classes and not j.paused]
        # bigger jobs first to reach target with fewer migrations
        eligible.sort(key=lambda j: -j.mw)
        for j in eligible:
            if accumulated >= target_mw:
                break
            self.jobs.remove(j)
            out.append(j)
            accumulated += j.mw
        return out

    def fast_contingency_drop(self, target_pct: float, t: datetime) -> tuple[float, list[str]]:
        """Sub-second emergency response: drop target_pct of training MW immediately.

        Returns (mw_shed, actions). Doesn't go through DispatchRequest cycle —
        this is the pre-authorized fast channel. Always preserves the serving floor.
        """
        actions: list[str] = []
        eligible = [
            j for j in self.jobs
            if not j.paused
            and j.workload_class in ("training", "fine_tune")
        ]
        target_shed = sum(j.mw for j in eligible) * target_pct
        # respect serving floor
        max_droppable = max(0.0, self.current_mw(t) - self.serving_floor_mw)
        actual_target = min(target_shed, max_droppable)
        ordered = sorted(eligible, key=lambda j: -j.mw)
        accumulated = 0.0
        for j in ordered:
            if accumulated >= actual_target:
                break
            j.paused = True
            accumulated += j.mw
            actions.append(f"emergency-paused {j.job_id} ({j.mw:.0f}MW)")
        # log under a synthetic dispatch id so telemetry reflects it
        from datetime import timedelta as _td
        contingency_id = f"contingency-{t.timestamp():.0f}"
        self._active_dispatches[contingency_id] = {
            "shed_mw": accumulated,
            "expires_at": t + _td(minutes=2),
        }
        return accumulated, actions

    def expire_dispatches(self, t: datetime) -> None:
        """Remove dispatches whose window has closed; resume paused jobs to match."""
        expired = [rid for rid, s in self._active_dispatches.items() if t >= s["expires_at"]]
        for rid in expired:
            del self._active_dispatches[rid]
        # if no active decrease dispatches, resume any jobs we paused
        if not any(s["shed_mw"] > 0 for s in self._active_dispatches.values()):
            for j in self.jobs:
                j.paused = False
