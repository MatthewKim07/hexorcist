"""OpenAI-compatible LLM client, configured only by LLM_BASE_URL, LLM_API_KEY and LLM_MODEL.

Built to survive weaker open models: tolerant JSON extraction, schema validation,
and exactly one automatic repair retry that feeds the error back to the model.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Optional, Type, TypeVar

from openai import APIError, APIStatusError, AsyncOpenAI
from pydantic import BaseModel, ValidationError

from .config import Settings

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\s*\n(.*?)```", re.DOTALL)


class LLMError(RuntimeError):
    pass


def extract_json_text(text: str) -> str:
    """Pull a JSON object out of a reply that may include fences or commentary."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    for block in _FENCE_RE.findall(text):
        if block.lstrip().startswith(("{", "[")):
            return block.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def extract_code(text: str) -> Optional[str]:
    """Return the longest fenced block, which is the sketch when a reply has several."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    blocks = _FENCE_RE.findall(text)
    if not blocks:
        return None
    return max(blocks, key=len).strip() + "\n"


@dataclass
class LLMCall:
    step: str
    duration_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    repaired: bool = False


@dataclass
class LLMClient:
    settings: Settings
    calls: list[LLMCall] = field(default_factory=list)
    _client: Optional[AsyncOpenAI] = None
    _json_mode: bool = True
    _send_temperature: bool = True

    @property
    def client(self) -> AsyncOpenAI:
        if not self.settings.llm_configured:
            raise LLMError("The LLM is not configured. Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env.")
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
                timeout=self.settings.llm_timeout_s,
                max_retries=2,
            )
        return self._client

    async def _complete(self, messages: list[dict], step: str, json_mode: bool) -> str:
        kwargs: dict = {"model": self.settings.llm_model, "messages": messages}
        if self._send_temperature:
            kwargs["temperature"] = 0.2
        if json_mode and self._json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        for _ in range(3):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                break
            except APIStatusError as exc:
                # Not every OpenAI-compatible server takes every parameter. Drop and retry.
                body = str(exc).lower()
                if exc.status_code == 400 and "response_format" in kwargs and ("response_format" in body or "json" in body):
                    self._json_mode = False
                    kwargs.pop("response_format")
                    continue
                if exc.status_code == 400 and "temperature" in kwargs and "temperature" in body:
                    self._send_temperature = False
                    kwargs.pop("temperature")
                    continue
                raise LLMError(f"LLM request failed with HTTP {exc.status_code}: {_short(exc)}") from exc
            except APIError as exc:
                raise LLMError(f"LLM request failed: {_short(exc)}") from exc
        else:
            raise LLMError("LLM rejected the request parameters.")

        usage = getattr(response, "usage", None)
        self.calls.append(
            LLMCall(
                step=step,
                duration_ms=(time.monotonic() - start) * 1000,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            )
        )
        if not response.choices:
            raise LLMError("LLM returned no choices.")
        return response.choices[0].message.content or ""

    async def json(self, system: str, user: str, schema: Type[T], step: str) -> T:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        reply = await self._complete(messages, step, json_mode=True)
        try:
            return schema.model_validate_json(extract_json_text(reply))
        except (ValidationError, ValueError, json.JSONDecodeError) as first_error:
            messages += [
                {"role": "assistant", "content": reply[:12000]},
                {
                    "role": "user",
                    "content": "That reply failed validation:\n"
                    f"{str(first_error)[:1500]}\n\n"
                    "Reply again with ONLY one corrected JSON object that matches the schema. No commentary, no code fences.",
                },
            ]
            repaired = await self._complete(messages, step, json_mode=True)
            self.calls[-1].repaired = True
            try:
                return schema.model_validate_json(extract_json_text(repaired))
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                raise LLMError(f"LLM output for {step} was still invalid after one repair: {str(exc)[:600]}") from exc

    async def code(self, system: str, user: str, step: str) -> tuple[str, str]:
        """Return (code, full reply). Code travels in a fence because JSON escaping breaks on weak models."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        reply = await self._complete(messages, step, json_mode=False)
        code = extract_code(reply)
        if code is not None:
            return code, reply
        messages += [
            {"role": "assistant", "content": reply[:12000]},
            {"role": "user", "content": "Your reply had no fenced code block. Reply again with the complete sketch in one ```cpp fenced block."},
        ]
        repaired = await self._complete(messages, step, json_mode=False)
        self.calls[-1].repaired = True
        code = extract_code(repaired)
        if code is None:
            raise LLMError(f"LLM output for {step} had no code block after one repair.")
        return code, repaired


def _short(exc: Exception) -> str:
    return str(exc)[:400]
