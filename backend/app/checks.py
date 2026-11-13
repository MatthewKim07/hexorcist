"""Reading machine-checkable assertions from a spec, on its own, so they can be previewed and edited before a run.

This is the run's UNDERSTAND step and nothing else: one LLM call, no sandbox. A run given the
previewed checks reuses them, so what the user saw is exactly what gets evaluated.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from . import prompts
from .agent import normalize_assertions
from .config import Settings
from .llm import LLMClient, LLMError
from .models import DeviceSpec

MAX_CHECKS = 30


class CheckSet(BaseModel):
    """Checks sent back with a run. They are validated again, exactly like the model's own output."""
    assertions: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_CHECKS)
    device_model: Optional[prompts.DeviceModel] = None
    source: str = Field(default="preview", pattern="^(preview|example)$")


async def read_checks(settings: Settings, firmware: str, spec: DeviceSpec) -> dict:
    """Return the checks the run would derive from this spec. Raises LLMError when the model cannot be reached."""
    llm = LLMClient(settings)
    start = time.monotonic()
    reply = await llm.json(prompts.UNDERSTAND_SYSTEM, prompts.understand_user(firmware, spec), prompts.UnderstandReply, "understand")
    assertions, warnings = normalize_assertions(reply.assertions, spec)
    return {
        "assertions": [a.model_dump(exclude_none=True) for a in assertions],
        "device_model": reply.device_model.model_dump(),
        "warnings": warnings,
        "model": settings.llm_model,
        "duration_ms": round((time.monotonic() - start) * 1000),
    }


__all__ = ["CheckSet", "read_checks", "LLMError", "MAX_CHECKS"]
