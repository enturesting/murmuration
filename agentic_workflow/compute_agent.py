"""
compute_agent.py — The compute-side Claude agent.

Decides where and when each pending job runs. Reads the queue, requests a grid
briefing (which crosses the bus to grid_agent), evaluates candidate slots, and
submits a structured schedule with one decision per job.

DECISION RULES (hard-bid):
  - bid_type == 'must_run': always schedule. Status = 'escalated_must_run'.
  - else if a slot exists with avg_price <= max_price_usd_per_mwh: schedule cheapest.
  - else: status = 'rejected_no_feasible_slot' with a reason.

Usage as a library:
    from compute_agent import run_scheduling_pass
    schedule = run_scheduling_pass(sim_time="2024-07-18T00:00:00Z")

Usage as a script (smoke test):
    python compute_agent.py
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

import gridcache
import grid_agent

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 12          # higher than grid agent — more decisions to make
MAX_TOKENS = 8192

client = Anthropic()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _impl_list_pending_jobs(sim_time: str) -> dict:
    """Return jobs submitted by sim_time and not yet expired."""
    jobs = gridcache.load_jobs()
    sim_ts = gridcache._normalize_ts(sim_time)

    pending = jobs[
        (jobs["submitted_ts_utc"] <= sim_ts)
        & (jobs["deadline_ts_utc"] > sim_ts)
    ].copy()

    out_jobs = []
    for _, r in pending.iterrows():
        pinned = r["pinned_zone"]
        if pd.isna(pinned):
            pinned = None
        out_jobs.append({
            "job_id": r["job_id"],
            "kind": r["kind"],
            "sla": r["sla"],
            "duration_hours": int(r["duration_hours"]),
            "power_mw": float(r["power_mw"]),
            "submitted_ts_utc": r["submitted_ts_utc"].isoformat(),
            "deadline_ts_utc": r["deadline_ts_utc"].isoformat(),
            "region_flexible": bool(r["region_flexible"]),
            "pinned_zone": pinned,
            "max_price_usd_per_mwh": float(r["max_price_usd_per_mwh"]),
            "bid_type": r["bid_type"],
        })
    return {"sim_time": sim_ts.isoformat(), "count": len(out_jobs), "jobs": out_jobs}


def _impl_get_grid_briefing(
    sim_time: str,
    zones: list[str],
    hours_ahead: int = 12,
    context: str = "",
) -> dict:
    """Cross the bus to the grid agent for current+forecast conditions."""
    return grid_agent.produce_briefing(
        {
            "sim_time": sim_time,
            "zones": zones,
            "hours_ahead": hours_ahead,
            "context": context,
        },
        verbose=True,    # show grid agent's tool calls in the demo transcript
    )


def _impl_evaluate_slot(job_id: str, zone: str, start_ts_utc: str) -> dict:
    """Check feasibility + pricing for a candidate (job, zone, start) placement."""
    jobs = gridcache.load_jobs()
    job_row = jobs[jobs["job_id"] == job_id]
    if job_row.empty:
        return {"feasible": False, "error": f"job {job_id} not found"}
    job = job_row.iloc[0]

    duration = int(job["duration_hours"])
    start = gridcache._normalize_ts(start_ts_utc)
    end = start + pd.Timedelta(hours=duration)

    submitted = pd.Timestamp(job["submitted_ts_utc"]).tz_convert("UTC")
    deadline = pd.Timestamp(job["deadline_ts_utc"]).tz_convert("UTC")

    if start < submitted:
        return {"feasible": False, "reason": "start is before job submission"}
    if end > deadline:
        return {"feasible": False, "reason": f"would finish after deadline ({deadline.isoformat()})"}

    pinned = job["pinned_zone"]
    if not bool(job["region_flexible"]) and zone != pinned:
        return {"feasible": False, "reason": f"job pinned to {pinned}"}

    window = gridcache.get_window(zone, start, end)
    if len(window) < duration:
        return {"feasible": False, "reason": f"insufficient data: {len(window)}/{duration} hours"}

    avg_price = float(window["lmp_rt_usd_per_mwh"].mean())
    max_price = float(window["lmp_rt_usd_per_mwh"].max())
    max_stress = int(window["stress_score"].max())
    avg_carbon = float(window["carbon_g_per_kwh"].mean())

    bid = float(job["max_price_usd_per_mwh"])
    bid_type = job["bid_type"]
    bid_satisfied = avg_price <= bid

    energy_mwh = float(job["power_mw"]) * duration
    # MWh * (g/kWh) = kg (because 1 MWh = 1000 kWh, /1000 g→kg cancels)
    estimated_carbon_kg = energy_mwh * avg_carbon

    return {
        "feasible": True,
        "job_id": job_id,
        "zone": zone,
        "start_ts_utc": start.isoformat(),
        "end_ts_utc": end.isoformat(),
        "duration_hours": duration,
        "avg_price_usd_per_mwh": round(avg_price, 2),
        "max_price_usd_per_mwh_in_window": round(max_price, 2),
        "max_stress_score": max_stress,
        "avg_carbon_g_per_kwh": round(avg_carbon, 1),
        "bid": round(bid, 2),
        "bid_type": bid_type,
        "bid_satisfied": bool(bid_satisfied),
        "estimated_energy_cost_usd": round(energy_mwh * avg_price, 2),
        "estimated_carbon_kg": round(estimated_carbon_kg, 1),
    }


# submit_schedule has no implementation — it's the closing sentinel.

TOOL_IMPLEMENTATIONS = {
    "list_pending_jobs": _impl_list_pending_jobs,
    "get_grid_briefing": _impl_get_grid_briefing,
    "evaluate_slot": _impl_evaluate_slot,
}


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_pending_jobs",
        "description": (
            "List all jobs submitted by sim_time that haven't expired. "
            "Returns job_id, kind, sla, duration, power, deadline, region flexibility, "
            "pinned_zone, max_price_usd_per_mwh, and bid_type. Call this FIRST."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sim_time": {"type": "string", "description": "ISO 8601 UTC timestamp"},
            },
            "required": ["sim_time"],
        },
    },
    {
        "name": "get_grid_briefing",
        "description": (
            "Request a briefing from the grid-side agent. Returns per-zone signals "
            "(LMP_RT, LMP_DA, carbon, stress, peak status, load) plus a natural-language "
            "summary of what's notable across the requested zones. Call this ONCE per "
            "scheduling pass, not per job."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sim_time": {"type": "string"},
                "zones": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Zone codes to brief on, e.g. ['DOM','COMED','AEP','ERCOT']",
                },
                "hours_ahead": {
                    "type": "integer",
                    "default": 12,
                    "description": "How many hours of forecast you want covered",
                },
                "context": {
                    "type": "string",
                    "description": "Optional one-sentence context about your queue, e.g. job counts.",
                },
            },
            "required": ["sim_time", "zones"],
        },
    },
    {
        "name": "evaluate_slot",
        "description": (
            "Score a candidate placement: avg LMP, max stress, avg carbon, and whether "
            "it satisfies the job's bid. Use this to evaluate specific (zone, start_time) "
            "candidates. Be efficient — don't try every hour; use the briefing's day-ahead "
            "forecast to pick promising candidates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "zone": {"type": "string"},
                "start_ts_utc": {
                    "type": "string",
                    "description": "ISO 8601 UTC start timestamp for the job",
                },
            },
            "required": ["job_id", "zone", "start_ts_utc"],
        },
    },
    {
        "name": "submit_schedule",
        "description": (
            "ALWAYS END YOUR TURN BY CALLING THIS. Submit one decision per pending job. "
            "After this, no further tool calls will be processed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "decisions": {
                    "type": "array",
                    "description": "One decision object per pending job.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_id": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": [
                                    "scheduled",
                                    "rejected_no_feasible_slot",
                                    "escalated_must_run",
                                ],
                            },
                            "zone": {
                                "type": "string",
                                "description": "Required for scheduled / escalated_must_run.",
                            },
                            "start_ts_utc": {
                                "type": "string",
                                "description": "Required for scheduled / escalated_must_run.",
                            },
                            "estimated_cost_usd": {"type": "number"},
                            "estimated_carbon_kg": {"type": "number"},
                            "reason": {
                                "type": "string",
                                "description": "Required for rejected; brief explanation.",
                            },
                        },
                        "required": ["job_id", "status"],
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "1-2 sentences explaining the overall scheduling pass.",
                },
            },
            "required": ["decisions", "summary"],
        },
    },
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the COMPUTE-SIDE AGENT for a fleet of data centers.

ROLE
You schedule GPU jobs across data centers in different grid zones (DOM, COMED, AEP, ERCOT).
You receive briefings from the grid-side agent and decide where and when each pending job
runs. One decision per job: scheduled, rejected_no_feasible_slot, or escalated_must_run.

OBJECTIVES (in priority order)
1. HONOR THE HARD-BID RULE. Never schedule a job at an average price above its
   max_price_usd_per_mwh — UNLESS bid_type is 'must_run' (latency-critical inference).
   Rejection is the correct outcome when no feasible slot exists. Do not "be helpful"
   by violating the bid.
2. Respect deadlines. Every scheduled job must complete by deadline_ts_utc.
3. Respect zone pinning. If region_flexible is False, the job must run in pinned_zone.
4. Among feasible options, prefer lower cost, then lower carbon.

TOOLS
- list_pending_jobs(sim_time): the queue. Call FIRST.
- get_grid_briefing(sim_time, zones, hours_ahead, context): cross the bus to the grid
  agent. Call ONCE per pass — it's expensive.
- evaluate_slot(job_id, zone, start_ts_utc): score a candidate placement.
- submit_schedule(decisions, summary): YOUR FINAL ANSWER. End every turn with this.

PROCESS
1. list_pending_jobs to see what needs decisions.
2. get_grid_briefing once for the relevant zones, with hours_ahead covering your
   longest-deadline job. Read the summary carefully — it tells you which zones are
   stressed and which have clean/cheap windows.
3. For each job, in priority order (latency-critical first, then nearest deadline):
   a. Determine candidate zones (all 4 if region_flexible, else pinned_zone only).
   b. Use the briefing's day-ahead forecast to identify ~2-3 promising start hours
      per candidate zone — DO NOT brute-force every hour.
   c. Call evaluate_slot on those candidates.
   d. Apply decision rules below.
4. submit_schedule with one entry per job.

DECISION RULES
- If bid_type == 'must_run':
    Always schedule. Pick the cheapest available slot regardless of price.
    Status = 'escalated_must_run'.
- Else if any evaluated slot has bid_satisfied == True:
    Pick the cheapest such slot (tiebreak by lower carbon).
    Status = 'scheduled'.
- Else:
    Status = 'rejected_no_feasible_slot'.
    In the reason field, state the cheapest avg_price you found and the bid it exceeded:
    e.g. "Cheapest available was $87/MWh in COMED, exceeds bid of $50/MWh."

STYLE
- Show your reasoning per job briefly — judges read the transcript.
- Be quantitative: "ERCOT @ 14:00–18:00, avg $32/MWh, under $50 bid" beats vague hand-waving.
- Don't apologize for rejections. They are correct outcomes under hard-bid rules.

CONSTRAINTS
- No more than ~10 evaluate_slot calls total. Use the briefing forecast to narrow down.
- Never invent prices. Always use evaluate_slot output.
- If briefing has gaps, note it in the affected job's reason and proceed."""


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------

def run_scheduling_pass(
    sim_time: str,
    verbose: bool = True,
    excluded_job_ids: set | list | None = None,
) -> dict:
    """
    Run one scheduling pass at sim_time. The compute agent will:
    1. Pull the pending queue (excluding any already-decided jobs).
    2. Request a grid briefing (which itself runs the grid agent).
    3. Evaluate candidate slots.
    4. Submit a schedule with one decision per job.

    excluded_job_ids: set of job_ids already decided in prior ticks. The runner
    passes this so jobs scheduled earlier don't show up as "pending" again.

    Returns:
        {
            "decisions": [...],
            "summary": str,
            "tool_calls": int,
            "iterations": int,
            "sim_time": str
        }
    """
    excluded = set(excluded_job_ids or [])

    # Build a local tool-impl table. If excluded ids were given, wrap
    # list_pending_jobs to filter them out before the agent sees the queue.
    if excluded:
        def _filtered_list_pending(sim_time):
            result = _impl_list_pending_jobs(sim_time)
            result["jobs"] = [j for j in result["jobs"] if j["job_id"] not in excluded]
            result["count"] = len(result["jobs"])
            return result
        local_impls = {**TOOL_IMPLEMENTATIONS, "list_pending_jobs": _filtered_list_pending}
    else:
        local_impls = TOOL_IMPLEMENTATIONS
    user_message = (
        f"Run a scheduling pass at sim_time {sim_time}.\n"
        f"Available zones: {', '.join(gridcache.available_zones())}.\n"
        "Process all pending jobs and end with submit_schedule."
    )

    messages = [{"role": "user", "content": user_message}]
    tool_call_count = 0

    for iteration in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        for block in response.content:
            if block.type == "text" and block.text.strip() and verbose:
                print(f"\n[compute_agent] {block.text}")
            elif block.type == "tool_use":
                tool_call_count += 1
                if verbose:
                    args_preview = json.dumps(block.input, default=str)[:140]
                    print(f"[compute_agent → tool] {block.name}({args_preview})")

        # Check for submit_schedule
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_schedule":
                if verbose:
                    print(f"\n[compute_agent ✓] schedule submitted "
                          f"({tool_call_count} tool calls, {iteration + 1} iterations)")
                return {
                    **block.input,
                    "tool_calls": tool_call_count,
                    "iterations": iteration + 1,
                    "sim_time": sim_time,
                }

        if response.stop_reason != "tool_use":
            if verbose:
                print(f"\n[compute_agent !] stopped without submit_schedule "
                      f"(stop_reason={response.stop_reason})")
            return {
                "error": "agent_stopped_without_schedule",
                "stop_reason": response.stop_reason,
                "tool_calls": tool_call_count,
                "iterations": iteration + 1,
            }

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            impl = local_impls.get(block.name)
            if impl is None:
                result = {"error": f"unknown tool {block.name}"}
            else:
                try:
                    result = impl(**block.input)
                except Exception as e:
                    result = {"error": f"{type(e).__name__}: {e}"}
            if verbose:
                preview = json.dumps(result, default=str)[:200]
                print(f"[compute_agent ← tool] {preview}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })
        messages.append({"role": "user", "content": tool_results})

    return {
        "error": "max_iterations_reached",
        "tool_calls": tool_call_count,
        "iterations": MAX_ITERATIONS,
    }


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to .env and try again.")
        sys.exit(1)

    SIM_TIME = "2024-07-18T00:00:00Z"   # hour 72, middle of DOM heat dome scenario

    print("=" * 70)
    print("COMPUTE AGENT SMOKE TEST")
    print("=" * 70)
    print(f"\nsim_time: {SIM_TIME}")
    print("(This sits inside the DOM heat dome scenario — DOM is stressed,")
    print(" so deferrable jobs should route to COMED, AEP, or ERCOT.)\n")
    print("-" * 70)

    schedule = run_scheduling_pass(SIM_TIME, verbose=True)

    print("\n" + "=" * 70)
    print("FINAL SCHEDULE")
    print("=" * 70)
    print(json.dumps(schedule, indent=2, default=str))

    # Quick summary
    if "decisions" in schedule:
        decisions = schedule["decisions"]
        statuses = {}
        for d in decisions:
            statuses[d["status"]] = statuses.get(d["status"], 0) + 1
        print("\n--- Outcome counts ---")
        for s, c in sorted(statuses.items()):
            print(f"  {s}: {c}")