"""Anthropic tool-use definitions for the grid-side agent.

The grid agent uses these tools when it must pick which dispatch to issue
under stress. With ANTHROPIC_API_KEY set, Claude reasons over the tools and
picks; without it, the rule-based fallback in grid_agent.py handles it.
"""
from __future__ import annotations

# Tool schemas in Anthropic SDK format
GRID_TOOLS = [
    {
        "name": "list_envelopes",
        "description": (
            "List the standing FlexibilityEnvelopes committed by every facility "
            "in this BA. Use this to see who can shed how much load and at what cost."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ba": {"type": "string", "description": "Balancing authority code, e.g. CAISO/ERCOT/PJM"},
            },
            "required": ["ba"],
        },
    },
    {
        "name": "get_grid_state",
        "description": "Return current LMP, load, headroom, carbon, stress for a BA.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ba": {"type": "string"},
            },
            "required": ["ba"],
        },
    },
    {
        "name": "issue_dispatch",
        "description": (
            "Commit a dispatch request to a specific facility. Pick one and one only. "
            "needed_mw is negative for shed (decrease load), positive for lean-in."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ba": {"type": "string"},
                "facility_id": {"type": "string"},
                "needed_mw": {"type": "number", "description": "negative=shed, positive=lean-in"},
                "duration_min": {"type": "integer", "minimum": 5, "maximum": 240},
                "compensation_per_mwh": {"type": "number"},
                "priority": {"type": "string", "enum": ["economic", "reliability", "emergency"]},
                "reason": {"type": "string", "description": "Operator-style justification"},
            },
            "required": ["ba", "facility_id", "needed_mw", "duration_min",
                         "compensation_per_mwh", "priority", "reason"],
        },
    },
    {
        "name": "no_action",
        "description": "Decline to dispatch this tick — situation does not warrant action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
]


GRID_SYSTEM_PROMPT = """\
You are the dispatch operator for a balancing authority on the Murmuration protocol.

Your job: when grid stress emerges (high LMP, low headroom, high carbon, or contingency),
select a dispatch action from the flexibility envelopes that compute facilities have
already committed to you. You may also choose `no_action` if dispatch is not warranted.

Constraints:
- Never request beyond a facility's committed envelope.
- Honor `cannot_go_below_mw` floors absolutely (the protocol enforces this; don't try to violate).
- Prefer reliability dispatches when stress >= 0.7; prefer economic dispatches at lower stress.
- Within tier, prefer the cheapest envelope that meets the target relief.
- Output your decision via the `issue_dispatch` tool (or `no_action`).
- Cite the BA, LMP, target MW, duration, and reason in operator shift-log style.
- Only one tool call per decision.

Be terse. Be decisive."""
