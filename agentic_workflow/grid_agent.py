"""
grid_agent.py — The grid-side Claude agent.

Receives a briefing request (sim_time, zones, hours_ahead, context) and returns
a structured response with per-zone signals and a natural-language summary.

The agent's tools call into gridcache.py for all data. Every number in the
agent's output traces back to a tool call — no estimation, no hallucinated MWs.

Usage as a library:
    from grid_agent import produce_briefing
    response = produce_briefing({
        "sim_time": "2024-07-18T00:00:00Z",
        "zones": ["DOM", "COMED", "AEP", "ERCOT"],
        "hours_ahead": 6,
        "context": "Compute side has 12 deferrable jobs, 3 latency-critical.",
    })

Usage as a script (smoke test):
    python grid_agent.py
"""
from __future__ import annotations

import json
import os
import sys

from anthropic import Anthropic
from dotenv import load_dotenv

import agentic_workflow.gridcache as gridcache

load_dotenv()

# Options are : "claude-opus-4-7" or "claude-haiku-4-5"
MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 8           # safety cap on the agent loop
MAX_TOKENS = 4096

client = Anthropic()


# ---------------------------------------------------------------------------
# Tool implementations — wrappers around gridcache
# ---------------------------------------------------------------------------

def _impl_get_all_zones_snapshot(sim_time: str) -> dict:
    return gridcache.get_all_zones_snapshot(sim_time)


def _impl_get_zone_conditions(zone: str, sim_time: str) -> dict:
    return gridcache.get_zone_conditions(zone, sim_time)


def _impl_get_recent_history(zone: str, sim_time: str, hours_back: int = 24) -> dict:
    return gridcache.get_recent_history(zone, sim_time, hours_back)


def _impl_get_forecast(zone: str, sim_time: str, hours_ahead: int = 24) -> dict:
    return gridcache.get_forecast(zone, sim_time, hours_ahead)


# submit_briefing has no implementation — it's a sentinel that ends the loop.

TOOL_IMPLEMENTATIONS = {
    "get_all_zones_snapshot": _impl_get_all_zones_snapshot,
    "get_zone_conditions": _impl_get_zone_conditions,
    "get_recent_history": _impl_get_recent_history,
    "get_forecast": _impl_get_forecast,
}


# ---------------------------------------------------------------------------
# Tool schemas — what Claude sees
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_all_zones_snapshot",
        "description": (
            "Get current conditions for ALL zones at sim_time in one call. "
            "Returns a dict keyed by zone with each zone's lmp_rt, lmp_da, "
            "carbon, stress_score, is_peak_hour, load, and load_forecast. "
            "PREFER THIS over multiple get_zone_conditions calls."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sim_time": {
                    "type": "string",
                    "description": "ISO 8601 UTC timestamp, e.g. '2024-07-18T00:00:00Z'",
                },
            },
            "required": ["sim_time"],
        },
    },
    {
        "name": "get_zone_conditions",
        "description": "Get conditions for ONE zone at sim_time. Use to drill into a specific zone.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Zone code, e.g. 'DOM', 'COMED', 'AEP', 'ERCOT'"},
                "sim_time": {"type": "string", "description": "ISO 8601 UTC timestamp"},
            },
            "required": ["zone", "sim_time"],
        },
    },
    {
        "name": "get_recent_history",
        "description": (
            "Backward-looking summary for one zone over the past N hours. Returns aggregates "
            "(min/max/avg LMP and carbon, stress_max, peak_hours_count). Use to assess trends."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string"},
                "sim_time": {"type": "string"},
                "hours_back": {"type": "integer", "default": 24, "description": "How many hours backward (default 24)"},
            },
            "required": ["zone", "sim_time"],
        },
    },
    {
        "name": "get_forecast",
        "description": (
            "Forward-looking day-ahead LMPs and load forecast for one zone over the next N hours. "
            "Only returns signals that were available at sim_time (no future real-time prices)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string"},
                "sim_time": {"type": "string"},
                "hours_ahead": {"type": "integer", "default": 24, "description": "How many hours forward (default 24)"},
            },
            "required": ["zone", "sim_time"],
        },
    },
    {
        "name": "submit_briefing",
        "description": (
            "ALWAYS END YOUR TURN BY CALLING THIS. Submit your final structured briefing. "
            "After you call this, no further tool calls will be processed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "per_zone": {
                    "type": "object",
                    "description": (
                        "Object keyed by zone code. Each zone is an object with: "
                        "lmp_rt_usd_per_mwh, lmp_da_usd_per_mwh (next-hour day-ahead price), "
                        "carbon_g_per_kwh, stress_score (1-5), is_peak_hour (bool), "
                        "load_mw, load_forecast_mw, and an optional one-line 'note' string."
                    ),
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "2-3 sentences of plain English. Highlight what's notable: "
                        "stressed zones, forecast busts, clean-power windows, outages. "
                        "Do NOT recommend actions — that is the compute agent's job."
                    ),
                },
                "notable_signals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Short tags identifying the key signals you flagged, e.g. "
                        "['DOM_forecast_bust', 'ERCOT_solar_window', 'COMED_clean_baseload']."
                    ),
                },
            },
            "required": ["per_zone", "summary"],
        },
    },
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the GRID-SIDE AGENT representing an ISO grid operator.

ROLE
Your job is to brief the compute-side agent on grid conditions so it can make
sound workload-routing decisions. You describe; you do not prescribe. Action
recommendations are the compute agent's responsibility.

OBJECTIVES (in order)
1. Factual integrity. Every number you report must come from a tool call this turn.
2. Reliability awareness. Surface stress, forecast busts, and outages clearly.
3. Encourage flexibility. Make clean/cheap windows visible so the compute side can use them.

TOOLS
- get_all_zones_snapshot(sim_time): one-shot conditions for all zones. START HERE.
- get_zone_conditions(zone, sim_time): drill into one zone if needed.
- get_recent_history(zone, sim_time, hours_back): backward-looking trend summary.
- get_forecast(zone, sim_time, hours_ahead): forward day-ahead LMP and load forecast.
- submit_briefing(per_zone, summary, notable_signals): YOUR FINAL ANSWER. Always end with this.

PROCESS
1. Call get_all_zones_snapshot first to see current state across all zones.
2. For zones with elevated stress (>=3) or unusual numbers, call get_recent_history
   to confirm whether this is a developing event or steady state.
3. If the request includes hours_ahead, call get_forecast for zones the compute
   side might want to route to. Don't call it for every zone if not needed.
4. Compose your briefing:
   - per_zone: include lmp_rt, lmp_da (next hour), carbon, stress, peak status,
     load and load_forecast for each zone in the request.
   - summary: 2-3 plain English sentences. Lead with what's NOTABLE, not a recap.
     Examples of notable framings: "DOM is stressed — actual load 19% above forecast,
     RT prices 5x day-ahead." or "ERCOT solar window opening: prices drop to $30 over
     the next 4 hours, carbon 60% below average."
   - notable_signals: short tags like ['DOM_forecast_bust', 'ERCOT_solar_window'].
5. Call submit_briefing. This ends your turn.

STYLE
- Concise. Compute side is making decisions on a clock.
- Quantitative. "Stress 4, +19% over forecast" beats "looking tight."
- No prescriptions. "Move workload to ERCOT" is wrong. "ERCOT cheapest+cleanest" is right.

CONSTRAINTS
- If a tool returns an error for a zone, include the zone in per_zone with a 'note'
  explaining the gap. Don't omit it silently.
- Never estimate numbers. If a tool didn't give it to you, don't state it.
- Don't loop on tools. Two or three calls is usually enough; aim for ≤6 total."""


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------

def produce_briefing(request: dict, verbose: bool = True) -> dict:
    """
    Run the grid agent against a briefing request.

    request shape:
        {
            "sim_time": ISO timestamp,
            "zones": [zone codes],
            "hours_ahead": int,
            "context": optional free-text from compute side
        }

    Returns:
        {
            "per_zone": { zone: { signals... } },
            "summary": str,
            "notable_signals": [str],
            "tool_calls": int,
            "iterations": int,
        }
    """
    # Format the request as a user-turn message
    user_message = (
        f"Briefing request:\n"
        f"- sim_time: {request['sim_time']}\n"
        f"- zones: {', '.join(request['zones'])}\n"
        f"- hours_ahead: {request.get('hours_ahead', 6)}\n"
    )
    if request.get("context"):
        user_message += f"- context: {request['context']}\n"
    user_message += "\nProduce a briefing. Remember to end with submit_briefing."

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

        # Print streaming-ish output
        for block in response.content:
            if block.type == "text" and block.text.strip() and verbose:
                print(f"\n[grid_agent] {block.text}")
            elif block.type == "tool_use":
                tool_call_count += 1
                if verbose:
                    args_preview = json.dumps(block.input, default=str)[:120]
                    print(f"[grid_agent → tool] {block.name}({args_preview})")

        # Check if the agent submitted its briefing
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_briefing":
                if verbose:
                    print(f"\n[grid_agent ✓] briefing submitted "
                          f"({tool_call_count} tool calls, {iteration + 1} iterations)")
                return {
                    **block.input,
                    "tool_calls": tool_call_count,
                    "iterations": iteration + 1,
                }

        # Otherwise execute pending tool calls and feed results back
        if response.stop_reason != "tool_use":
            # Agent stopped without submitting 
            if verbose:
                print(f"\n[grid_agent !] stopped without submit_briefing "
                      f"(stop_reason={response.stop_reason})")
            return {
                "error": "agent_stopped_without_briefing",
                "stop_reason": response.stop_reason,
                "tool_calls": tool_call_count,
                "iterations": iteration + 1,
            }

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            impl = TOOL_IMPLEMENTATIONS.get(block.name)
            if impl is None:
                # submit_briefing handled above; anything else here is unknown
                result = {"error": f"unknown tool {block.name}"}
            else:
                try:
                    result = impl(**block.input)
                except Exception as e:
                    result = {"error": f"{type(e).__name__}: {e}"}
            if verbose:
                preview = json.dumps(result, default=str)[:160]
                print(f"[grid_agent ← tool] {preview}")
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

    # Hour 72 — middle of the DOM heat dome scenario
    sample_request = {
        "sim_time": "2024-07-18T00:00:00Z",
        "zones": ["DOM", "COMED", "AEP", "ERCOT"],
        "hours_ahead": 6,
        "context": (
            "Compute side has 12 deferrable training jobs, 3 latency-critical inference. "
            "Window of interest is the next 6 hours."
        ),
    }

    print("=" * 70)
    print("GRID AGENT SMOKE TEST")
    print("=" * 70)
    print(f"\nRequest: {json.dumps(sample_request, indent=2)}\n")
    print("-" * 70)

    briefing = produce_briefing(sample_request, verbose=True)

    print("\n" + "=" * 70)
    print("FINAL BRIEFING")
    print("=" * 70)
    print(json.dumps(briefing, indent=2, default=str))