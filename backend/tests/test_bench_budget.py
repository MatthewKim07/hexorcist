"""The strong-model baseline: its own endpoint, its own cost cap, and no call before the cap is checked."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench.llm_budget import Budget, BudgetExceeded, BudgetLLM, LLMEndpoint, endpoint_from_env, estimate_cost  # noqa: E402


class FakeClient:
    def __init__(self):
        self.kwargs = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.kwargs.append(kwargs)
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=2000, completion_tokens=1000),
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"bugs": []}'))],
        )


def strong(model, tmp_path, cap=2.0):
    ep = LLMEndpoint(name="strong", base_url="https://api.openai.com/v1", api_key="k", model=model, bucket="strong")
    budget = Budget(max_cost_strong=cap)
    llm = BudgetLLM(ep, budget, cache_dir=tmp_path)
    llm._client = FakeClient()
    return llm, budget


def test_the_strong_endpoint_reads_its_model_from_the_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("BASELINE_STRONG_MODEL", "")
    assert not endpoint_from_env("STRONG").configured
    monkeypatch.setenv("BASELINE_STRONG_MODEL", "gpt-4.1")
    ep = endpoint_from_env("STRONG")
    assert ep.configured and ep.model == "gpt-4.1" and ep.bucket == "strong"


def test_the_default_cap_is_two_dollars():
    assert Budget().max_cost_strong == 2.00


def test_strong_spend_is_tallied_apart_from_the_other_openai_baseline(tmp_path):
    llm, budget = strong("gpt-4.1", tmp_path)
    llm.chat([{"role": "user", "content": "x"}], step="t", max_tokens=1000)
    assert budget.spent_strong == pytest.approx(estimate_cost("gpt-4.1", 2000, 1000))
    assert budget.spent_openai == 0 and budget.spent_deepseek == 0
    assert budget.summary()["cap_strong"] == 2.0


def test_the_cap_stops_a_call_before_it_is_made(tmp_path):
    llm, budget = strong("gpt-4.1", tmp_path, cap=0.001)
    with pytest.raises(BudgetExceeded):
        llm.chat([{"role": "user", "content": "x"}], step="t", max_tokens=4000)
    assert llm._client.kwargs == []


def test_an_unknown_strong_model_is_priced_as_a_strong_one_so_the_cap_still_bites():
    unknown = estimate_cost("some-new-model", 1000, 1000, fallback="gpt-4o")
    small = estimate_cost("some-new-model", 1000, 1000)
    assert unknown > small * 10


def test_a_reasoning_model_gets_a_completion_budget_and_no_temperature(tmp_path):
    llm, _ = strong("o3", tmp_path)
    llm.chat([{"role": "user", "content": "x"}], step="t", max_tokens=16000)
    sent = llm._client.kwargs[0]
    assert sent["max_completion_tokens"] == 16000 and "temperature" not in sent and "max_tokens" not in sent


def test_an_ordinary_model_keeps_temperature_zero(tmp_path):
    llm, _ = strong("gpt-4.1", tmp_path)
    llm.chat([{"role": "user", "content": "x"}], step="t", max_tokens=4000)
    sent = llm._client.kwargs[0]
    assert sent["temperature"] == 0.0 and sent["max_tokens"] == 4000


def test_a_mixed_run_is_priced_per_provider_on_its_own_tokens():
    from bench.llm_budget import cost_by_bucket

    providers = [
        {"role": "agent", "model": "deepseek-chat", "host": "api.deepseek.com", "prompt_tokens": 100_000, "completion_tokens": 20_000},
        {"role": "cleanroom2", "model": "gpt-4o-mini", "host": "api.openai.com", "prompt_tokens": 10_000, "completion_tokens": 4_000},
    ]
    cost = cost_by_bucket(providers)
    assert cost["deepseek"] == pytest.approx(estimate_cost("deepseek-chat", 100_000, 20_000))
    assert cost["openai"] == pytest.approx(estimate_cost("gpt-4o-mini", 10_000, 4_000))
    assert set(cost) == {"deepseek", "openai"}


def test_a_run_without_providers_is_priced_as_one_model():
    from bench.llm_budget import cost_by_bucket

    assert cost_by_bucket([], "deepseek-chat", 1000, 500) == {"deepseek": pytest.approx(estimate_cost("deepseek-chat", 1000, 500))}
    assert cost_by_bucket([], "", 0, 0) == {}
