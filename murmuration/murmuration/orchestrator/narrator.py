"""Claude-backed narrator. Falls back to rule-based summaries if no API key."""
from __future__ import annotations
import os
import logging
from typing import Literal

log = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
    _has_sdk = True
except ImportError:
    _has_sdk = False


Voice = Literal["grid", "compute"]

VOICE_PROMPT = {
    "grid": (
        "You are an ISO control-room operator narrating dispatch decisions. "
        "Speak in shift-log style: cite specific BAs, LMPs, MW figures, and "
        "the reason. 1–2 sentences max. No fluff."
    ),
    "compute": (
        "You are a hyperscaler fleet-ops engineer narrating dispatch acceptance. "
        "Cite specific clusters, jobs paused or resumed, MW shed, and SLA impact. "
        "1–2 sentences max. No fluff."
    ),
}


class Narrator:
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.model = model
        self._client = None
        if _has_sdk and os.getenv("ANTHROPIC_API_KEY"):
            try:
                self._client = Anthropic()
            except Exception:
                log.warning("Anthropic client init failed; using rule-based narrator")

    @property
    def claude_enabled(self) -> bool:
        return self._client is not None

    def narrate(self, voice: Voice, context: str) -> str:
        if self._client is None:
            return self._fallback(voice, context)
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=180,
                system=VOICE_PROMPT[voice],
                messages=[{"role": "user", "content": context}],
            )
            text_blocks = [b.text for b in resp.content if hasattr(b, "text")]
            return " ".join(text_blocks).strip()
        except Exception:
            log.exception("Claude narration failed; using fallback")
            return self._fallback(voice, context)

    @staticmethod
    def _fallback(voice: Voice, context: str) -> str:
        # rule-based: just echo the context cleanly
        prefix = "[grid] " if voice == "grid" else "[compute] "
        return prefix + context
