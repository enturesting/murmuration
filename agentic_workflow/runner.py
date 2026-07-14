"""
runner.py — Orchestrates the multi-tick simulation.

Advances simulated time across the data window. At each tick:
  1. Calls compute_agent.run_scheduling_pass(sim_time, excluded=already_decided)
  2. Compute agent internally calls grid_agent (the bus crossing)
  3. Records decisions, never re-decides a job
  4. Updates running totals (cost, carbon, status counts)

Outputs:
  out/run_<timestamp>/decisions.json    — every decision made, with tick metadata
  out/run_<timestamp>/events.json       — full per-tick agent output
  out/run_<timestamp>/scorecard.json    — totals and rates

Usage:
    python runner.py
    # or programmatically:
    from runner import Runner
    r = Runner(start="2024-07-17T00:00:00Z", end="2024-07-19T00:00:00Z", tick_hours=6)
    r.run()
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

import agentic_workflow.compute_agent as compute_agent
import agentic_workflow.gridcache as gridcache

load_dotenv()


# ---------------------------------------------------------------------------
# Config — edit these to change what the runner does
# ---------------------------------------------------------------------------

# Default replay window. Hour 0 is 2024-07-15T00:00 UTC.
# Hour 60-96 is the DOM heat dome.
# Hour 150-168 is the AEP+ERCOT wind ramp.
DEFAULT_START = "2024-07-17T00:00:00Z"   # hour 48, just before heat dome
DEFAULT_END   = "2024-07-22T00:00:00Z"   # hour 168, end of wind ramp
DEFAULT_TICK_HOURS = 6                   # agent runs every 6 simulated hours

# Safety cap so a runaway loop doesn't drain the API budget
MAX_TICKS = 30

OUT_BASE = Path("out")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@dataclass
class Runner:
    start: str = DEFAULT_START
    end: str = DEFAULT_END
    tick_hours: int = DEFAULT_TICK_HOURS
    verbose: bool = True

    # Internal state
    decisions: list[dict] = field(default_factory=list)   # all decisions, with tick metadata
    events: list[dict] = field(default_factory=list)      # raw per-tick agent output
    out_dir: Path = field(default_factory=lambda: OUT_BASE / f"run_{datetime.utcnow():%Y%m%dT%H%M%S}")

    def __post_init__(self):
        self._start_ts = gridcache._normalize_ts(self.start)
        self._end_ts = gridcache._normalize_ts(self.end)
        if self._end_ts <= self._start_ts:
            raise ValueError("end must be after start")
        self.out_dir.mkdir(parents=True, exist_ok=True)

    # ---- core loop ----

    def run(self) -> dict:
        """Run the full simulation and return the scorecard."""
        if self.verbose:
            self._print_header()

        ticks_executed = 0
        current = self._start_ts
        t_start = time.time()

        while current < self._end_ts and ticks_executed < MAX_TICKS:
            ticks_executed += 1
            self._tick(current, ticks_executed)
            current += pd.Timedelta(hours=self.tick_hours)

        elapsed = time.time() - t_start
        scorecard = self._build_scorecard(ticks_executed, elapsed)
        self._persist(scorecard)

        if self.verbose:
            self._print_scorecard(scorecard)

        return scorecard

    def _tick(self, sim_time: pd.Timestamp, tick_num: int):
        """Run the compute agent at one sim_time and accumulate results."""
        if self.verbose:
            self._print_tick_header(sim_time, tick_num)

        # Already-decided jobs: don't re-decide them
        decided_ids = {d["job_id"] for d in self.decisions}

        try:
            result = compute_agent.run_scheduling_pass(
                sim_time=sim_time.isoformat(),
                verbose=self.verbose,
                excluded_job_ids=decided_ids,
            )
        except Exception as e:
            if self.verbose:
                print(f"\n[runner !] tick {tick_num} crashed: {type(e).__name__}: {e}")
            self.events.append({
                "tick": tick_num,
                "sim_time": sim_time.isoformat(),
                "error": f"{type(e).__name__}: {e}",
            })
            return

        # Record decisions with tick metadata
        new_decisions = result.get("decisions", [])
        for d in new_decisions:
            self.decisions.append({
                "tick": tick_num,
                "decided_at_sim_time": sim_time.isoformat(),
                **d,
            })

        # Record full event for replay
        self.events.append({
            "tick": tick_num,
            "sim_time": sim_time.isoformat(),
            "result": result,
        })

        if self.verbose:
            self._print_tick_summary(new_decisions)

    # ---- scorecard ----

    def _build_scorecard(self, ticks_executed: int, elapsed_seconds: float) -> dict:
        """Compute totals across all decisions in this run."""
        status_counts: dict[str, int] = {}
        zone_counts: dict[str, int] = {}
        total_cost = 0.0
        total_carbon_kg = 0.0

        for d in self.decisions:
            status = d.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            if d.get("zone"):
                zone_counts[d["zone"]] = zone_counts.get(d["zone"], 0) + 1
            total_cost += d.get("estimated_cost_usd") or 0
            total_carbon_kg += d.get("estimated_carbon_kg") or 0

        return {
            "policy": "agent",
            "start": self.start,
            "end": self.end,
            "tick_hours": self.tick_hours,
            "ticks_executed": ticks_executed,
            "wall_clock_seconds": round(elapsed_seconds, 1),
            "total_decisions": len(self.decisions),
            "status_counts": status_counts,
            "zone_counts": zone_counts,
            "total_cost_usd": round(total_cost, 2),
            "total_carbon_kg": round(total_carbon_kg, 1),
            "reject_rate": (
                round(status_counts.get("rejected_no_feasible_slot", 0)
                      / max(len(self.decisions), 1), 3)
            ),
        }

    # ---- persistence ----

    def _persist(self, scorecard: dict):
        with open(self.out_dir / "decisions.json", "w") as f:
            json.dump(self.decisions, f, indent=2, default=str)
        with open(self.out_dir / "events.json", "w") as f:
            json.dump(self.events, f, indent=2, default=str)
        with open(self.out_dir / "scorecard.json", "w") as f:
            json.dump(scorecard, f, indent=2, default=str)
        if self.verbose:
            print(f"\n[runner] artifacts written to {self.out_dir}/")

    # ---- pretty printing ----

    def _print_header(self):
        print("=" * 72)
        print("RUNNER")
        print("=" * 72)
        print(f"  window:     {self.start}  →  {self.end}")
        print(f"  tick:       every {self.tick_hours}h "
              f"(~{int((self._end_ts - self._start_ts).total_seconds() / 3600 / self.tick_hours)} ticks)")
        print(f"  output:     {self.out_dir}/")
        print(f"  zones:      {gridcache.available_zones()}")
        print()

    def _print_tick_header(self, sim_time, tick_num):
        print()
        print("─" * 72)
        print(f"TICK {tick_num}    sim_time = {sim_time.isoformat()}")
        print("─" * 72)

    def _print_tick_summary(self, new_decisions: list[dict]):
        if not new_decisions:
            print("\n[runner] no new decisions this tick")
            return
        print(f"\n[runner] {len(new_decisions)} new decisions:")
        for d in new_decisions:
            jid = d.get("job_id", "?")
            status = d.get("status", "?")
            zone = d.get("zone", "—")
            tag = {
                "scheduled": "✓",
                "escalated_must_run": "!",
                "rejected_no_feasible_slot": "✗",
            }.get(status, "?")
            cost = d.get("estimated_cost_usd")
            cost_s = f"${cost:,.0f}" if cost else ""
            print(f"  {tag} {jid:<22s} {status:<28s} {zone:<6s} {cost_s}")

    def _print_scorecard(self, sc: dict):
        print()
        print("=" * 72)
        print("SCORECARD")
        print("=" * 72)
        print(f"  ticks executed:     {sc['ticks_executed']}")
        print(f"  wall clock:         {sc['wall_clock_seconds']}s")
        print(f"  total decisions:    {sc['total_decisions']}")
        print(f"  status breakdown:   {sc['status_counts']}")
        print(f"  zone placements:    {sc['zone_counts']}")
        print(f"  total cost:         ${sc['total_cost_usd']:,.2f}")
        print(f"  total carbon:       {sc['total_carbon_kg']:,.1f} kg")
        print(f"  reject rate:        {sc['reject_rate']:.1%}")
        print("=" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to .env and try again.")
        sys.exit(1)

    # Quick safety check on the data
    t0, t1 = gridcache.time_range()
    s0 = gridcache._normalize_ts(DEFAULT_START)
    s1 = gridcache._normalize_ts(DEFAULT_END)
    if s0 < t0 or s1 > t1:
        print(f"ERROR: requested window {s0}→{s1} is outside data window {t0}→{t1}")
        print("Either adjust DEFAULT_START/DEFAULT_END or regenerate data with synthetic_grid.py")
        sys.exit(1)

    print("\nNOTE: Each tick runs both compute_agent AND grid_agent (nested).")
    print("Cost estimate: ~$0.10–0.20 per tick × ticks. Hit Ctrl-C to abort.\n")

    runner = Runner()
    runner.run()