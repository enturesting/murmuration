"""Tiered workload router.

When an AZ goes unavailable (substation overload, scenario-driven, or anomaly),
the router escalates through tiers to find homes for stranded workloads:

  Tier 1: Sibling AZ in the same region (sub-ms latency, no data migration)
  Tier 2: Cross-region    (10–100 ms latency, data must be staged)
  Tier 3: Throttle in place (last resort — work is shed, MW counts as relief)

Each migration is published on the bus as a WorkloadMigration so the UI can
draw tier-aware arcs and judges can see the escalation logic narrated live.
"""
from __future__ import annotations
from datetime import datetime
from typing import Iterable
import logging
import uuid

from murmuration.protocol import (
    WorkloadMigration, MurmurationBus, expires_at,
)
from murmuration.assets import DataCenter

log = logging.getLogger(__name__)

# Latency penalty per tier — order of magnitude rough estimates
TIER_LATENCY_MS = {
    "intra_region": 0.5,    # sub-ms
    "cross_region": 45.0,   # transcontinental round-trip
}


class WorkloadRouter:
    def __init__(self, bus: MurmurationBus, assets: list):
        self.bus = bus
        self.assets = assets
        # Indexed lookups for fast routing
        self._dc_by_id: dict[str, DataCenter] = {
            a.asset_id: a for a in assets if isinstance(a, DataCenter)
        }
        self._region_of: dict[str, str | None] = {
            a.asset_id: getattr(a, "region", None) for a in assets if isinstance(a, DataCenter)
        }
        self._unavailable_seen: set[str] = set()    # tracks already-handled outages

    def attach_regions(self, region_map: dict[str, str]) -> None:
        """Server pushes the {asset_id: region} map after construction
        (because region is in ASSET_GEO, not on the asset itself)."""
        self._region_of.update(region_map)

    async def reconcile(self, t: datetime) -> list[WorkloadMigration]:
        """Inspect every DC. For each AZ that just became unavailable, evict
        its jobs to siblings/cross-region. Idempotent — only fires once per
        unavailability transition."""
        migrations: list[WorkloadMigration] = []
        for dc in self._dc_by_id.values():
            currently = bool(getattr(dc, "unavailable", False))
            previously = dc.asset_id in self._unavailable_seen
            if currently and not previously:
                # transition healthy → unavailable: evict
                migs = await self._evict(dc, t)
                migrations.extend(migs)
                self._unavailable_seen.add(dc.asset_id)
            elif not currently and previously:
                # recovered: just clear the flag (jobs don't auto-return)
                self._unavailable_seen.remove(dc.asset_id)
        return migrations

    async def _evict(self, src: DataCenter, t: datetime) -> list[WorkloadMigration]:
        """Move jobs off `src` using the tiered cascade. Online-serve workloads
        cannot cross regions, so they only get Tier 1 destinations."""
        # cap how much we try to move per eviction
        eligible_classes = ("training", "fine_tune", "batch_infer", "online_serve")
        evicted = src.release_jobs(target_mw=src.nominal_max_mw, classes=eligible_classes)
        if not evicted:
            return []

        log.info("router: evicting %d jobs (%.0f MW) from %s",
                 len(evicted), sum(j.mw for j in evicted), src.asset_id)

        migrations: list[WorkloadMigration] = []
        # Build candidate sets per tier
        src_region = self._region_of.get(src.asset_id)
        siblings = [
            d for d in self._dc_by_id.values()
            if d.asset_id != src.asset_id
            and self._region_of.get(d.asset_id) == src_region
            and not d.unavailable
        ]
        cross_region = [
            d for d in self._dc_by_id.values()
            if d.asset_id != src.asset_id
            and self._region_of.get(d.asset_id) != src_region
            and not d.unavailable
        ]

        for job in evicted:
            placed = False
            for tier_name, candidates in (("intra_region", siblings),
                                          ("cross_region", cross_region)):
                if tier_name == "cross_region" and job.workload_class == "online_serve":
                    continue   # latency-sensitive workloads cannot cross regions
                # pick the candidate with the most headroom relative to floor
                ranked = sorted(
                    candidates,
                    key=lambda d: -(d.nominal_max_mw - d.current_mw()),
                )
                for dest in ranked:
                    headroom = dest.nominal_max_mw - dest.current_mw()
                    if headroom < job.mw + 1:
                        continue
                    dest.take_jobs([job])
                    mig = WorkloadMigration(
                        timestamp=t,
                        job_id=job.job_id,
                        src_facility=src.asset_id,
                        dest_facility=dest.asset_id,
                        tier=tier_name,
                        workload_class=job.workload_class,
                        mw=job.mw,
                        latency_ms_added=TIER_LATENCY_MS[tier_name],
                        reason=(f"{src.asset_id} unavailable; "
                                f"{tier_name} migration to {dest.asset_id} "
                                f"({headroom:.0f} MW headroom)"),
                    )
                    await self.bus.publish(mig)
                    migrations.append(mig)
                    placed = True
                    log.info("router: migrated %s (%.0f MW, %s) %s -> %s",
                             job.job_id, job.mw, job.workload_class,
                             src.asset_id, dest.asset_id)
                    break
                if placed:
                    break
            if not placed:
                # Tier 3: throttle in place — job stays paused on src (lost compute)
                job.paused = True
                src.jobs.append(job)
                log.info("router: could not place %s; throttled in place at %s",
                         job.job_id, src.asset_id)
        return migrations
