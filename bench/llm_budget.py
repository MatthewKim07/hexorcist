"""Cached OpenAI-compatible chat calls with token accounting and hard USD caps.

Never logs API keys. Prices are estimates — verify on the provider's pricing page.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from openai import APIError, APIStatusError, OpenAI

from bench.case_io import CACHE_DIR, write_json

# USD per 1M tokens. Verify on each provider's pricing page before a paid run.
PRICE_PER_MTOK: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 0.28, "output": 0.42},  # DeepSeek chat cache-miss-ish ballpark
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "o4-mini": {"input": 1.10, "output": 4.40},
}

DEFAULT_JUDGE_MODEL = "gpt-4o-mini"


def _redact(text: str) -> str:
    return re.sub(r"(sk-[A-Za-z0-9_\-]{8,})", "sk-***", text)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = PRICE_PER_MTOK.get(model) or PRICE_PER_MTOK.get(model.split("/")[-1])
    if not prices:
        # Unknown model: assume gpt-4o-mini rates so caps still bite.
        prices = PRICE_PER_MTOK["gpt-4o-mini"]
    return (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1_000_000.0


def provider_bucket(model: str, base_url: str) -> str:
    u = (base_url or "").lower()
    m = (model or "").lower()
    if "deepseek" in u or m.startswith("deepseek"):
        return "deepseek"
    if "openai" in u or m.startswith("gpt") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
        return "openai"
    return "other"


@dataclass
class Budget:
    max_cost_deepseek: float = 0.80
    max_cost_openai: float = 3.00
    spent_deepseek: float = 0.0
    spent_openai: float = 0.0
    spent_other: float = 0.0
    calls: list[dict[str, Any]] = field(default_factory=list)

    def spent(self, bucket: str) -> float:
        return {"deepseek": self.spent_deepseek, "openai": self.spent_openai}.get(bucket, self.spent_other)

    def cap(self, bucket: str) -> float:
        return {"deepseek": self.max_cost_deepseek, "openai": self.max_cost_openai}.get(bucket, 1e9)

    def would_exceed(self, bucket: str, extra: float) -> bool:
        return self.spent(bucket) + extra > self.cap(bucket) + 1e-12

    def add(self, bucket: str, cost: float, record: dict[str, Any]) -> None:
        if bucket == "deepseek":
            self.spent_deepseek += cost
        elif bucket == "openai":
            self.spent_openai += cost
        else:
            self.spent_other += cost
        self.calls.append(record)

    def summary(self) -> dict[str, Any]:
        return {
            "spent_deepseek": round(self.spent_deepseek, 6),
            "spent_openai": round(self.spent_openai, 6),
            "spent_other": round(self.spent_other, 6),
            "cap_deepseek": self.max_cost_deepseek,
            "cap_openai": self.max_cost_openai,
            "calls": len(self.calls),
        }


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class LLMEndpoint:
    name: str
    base_url: str
    api_key: str
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


def endpoint_from_env(prefix: str = "LLM") -> LLMEndpoint:
    """prefix LLM → LLM_BASE_URL/API_KEY/MODEL; OPENAI → OPENAI_* with OpenAI default URL."""
    if prefix == "OPENAI":
        return LLMEndpoint(
            name="openai",
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
            api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            model=os.environ.get("OPENAI_MODEL", DEFAULT_JUDGE_MODEL).strip(),
        )
    return LLMEndpoint(
        name="llm",
        base_url=os.environ.get("LLM_BASE_URL", "").strip(),
        api_key=os.environ.get("LLM_API_KEY", "").strip(),
        model=os.environ.get("LLM_MODEL", "").strip(),
    )


def _cache_key(model: str, messages: list[dict], max_tokens: int, temperature: float) -> str:
    blob = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


class BudgetLLM:
    def __init__(self, endpoint: LLMEndpoint, budget: Budget, cache_dir: Path = CACHE_DIR):
        self.endpoint = endpoint
        self.budget = budget
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if not self.endpoint.configured:
            raise RuntimeError(f"LLM endpoint {self.endpoint.name} is not configured")
        if self._client is None:
            self._client = OpenAI(base_url=self.endpoint.base_url, api_key=self.endpoint.api_key, timeout=180, max_retries=0)
        return self._client

    def chat(
        self,
        messages: list[dict],
        *,
        step: str,
        max_tokens: int,
        temperature: float = 0.0,
        json_mode: bool = False,
        allow_retry: bool = True,
    ) -> dict[str, Any]:
        model = self.endpoint.model
        key = _cache_key(model, messages, max_tokens, temperature)
        cache_path = self.cache_dir / f"{key}.json"
        if cache_path.is_file():
            cached = json.loads(cache_path.read_text())
            cached["cached"] = True
            return cached

        bucket = provider_bucket(model, self.endpoint.base_url)
        # Pre-flight: assume worst-case full max_tokens at model rates (conservative).
        projected = estimate_cost(model, 4000, max_tokens)
        if self.budget.would_exceed(bucket, projected):
            raise BudgetExceeded(
                f"{bucket} budget would exceed cap ${self.budget.cap(bucket):.2f} "
                f"(spent ${self.budget.spent(bucket):.4f}, projected +${projected:.4f})"
            )

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        attempts = 0
        last_err: Optional[Exception] = None
        while attempts < (2 if allow_retry else 1):
            attempts += 1
            start = time.monotonic()
            try:
                resp = self.client.chat.completions.create(**kwargs)
                usage = getattr(resp, "usage", None)
                pt = int(getattr(usage, "prompt_tokens", 0) or 0)
                ct = int(getattr(usage, "completion_tokens", 0) or 0)
                text = (resp.choices[0].message.content or "") if resp.choices else ""
                cost = estimate_cost(model, pt, ct)
                if self.budget.would_exceed(bucket, cost):
                    # Record and stop — do not keep calling.
                    raise BudgetExceeded(
                        f"{bucket} budget exceeded after call accounting "
                        f"(spent ${self.budget.spent(bucket):.4f} + ${cost:.4f} > ${self.budget.cap(bucket):.2f})"
                    )
                record = {
                    "step": step,
                    "model": model,
                    "base_url": self.endpoint.base_url,
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "cost_usd": round(cost, 8),
                    "duration_ms": round((time.monotonic() - start) * 1000),
                    "text": text,
                    "cached": False,
                    "attempts": attempts,
                }
                self.budget.add(bucket, cost, {k: v for k, v in record.items() if k != "text"})
                write_json(cache_path, record)
                return record
            except BudgetExceeded:
                raise
            except APIStatusError as exc:
                last_err = exc
                body = str(exc).lower()
                if exc.status_code == 400 and "response_format" in kwargs and ("response_format" in body or "json" in body):
                    kwargs.pop("response_format", None)
                    continue
                if attempts >= (2 if allow_retry else 1):
                    break
            except APIError as exc:
                last_err = exc
                if attempts >= (2 if allow_retry else 1):
                    break
        raise RuntimeError(_redact(f"LLM call failed: {last_err}"))
