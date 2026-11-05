"""The plain code review shown beside Hexorcist's measured evidence.

One LLM call, no emulator, no sandbox. It exists to show the difference between a model
reading code and an agent running it, so it is optional and never part of a Break run.
"""
from __future__ import annotations

import time

from . import prompts
from .config import Settings
from .llm import LLMClient, LLMError
from .models import DeviceSpec

MAX_CONCERNS = 8


def _clip(text: str, limit: int) -> str:
    return text.strip()[:limit]


async def review_firmware(settings: Settings, firmware: str, spec: DeviceSpec) -> dict:
    """Return the review, ready to store. Raises LLMError when the model cannot be reached."""
    llm = LLMClient(settings)
    start = time.monotonic()
    reply = await llm.json(prompts.REVIEW_SYSTEM, prompts.review_user(firmware, spec), prompts.ReviewReply, "review")
    line_count = len(firmware.splitlines())
    concerns = [
        {
            "title": _clip(c.title, 140),
            "detail": _clip(c.detail, 700),
            "lines": sorted({n for n in c.lines if isinstance(n, int) and 1 <= n <= line_count}),
            "confidence": c.confidence,
        }
        for c in reply.concerns[:MAX_CONCERNS]
        if c.title.strip() or c.detail.strip()
    ]
    return {
        "model": settings.llm_model,
        "verdict": "issues_found" if concerns else "looks_correct",
        "summary": _clip(reply.summary, 500),
        "concerns": concerns,
        "suggested_fix": _clip(reply.suggested_fix, 1500),
        "executed": False,
        "llm_calls": len(llm.calls),
        "duration_ms": round((time.monotonic() - start) * 1000),
        "tokens": sum(c.prompt_tokens + c.completion_tokens for c in llm.calls),
    }


__all__ = ["review_firmware", "LLMError"]
