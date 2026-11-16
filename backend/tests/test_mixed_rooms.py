"""Mixed-model clean rooms: room 2 is written by the OPENAI_* model, room 1 stays on the main model, and without OPENAI_* both use the main one."""
import asyncio
import json

from app.agent import Pipeline
from app.llm import LLMError
from tests.test_api import settings
from tests.test_cross_check import CLEAN_CHATTERS, CLEAN_OK, HEARTBEAT_ONLY, RoomLLM, RoomRunner
from tests.test_fix_loop import NullBus, NullStore, ORIGINAL, PERSIST_FIXED, SPEC_TEXT
from app.models import DeviceSpec, PinSpec

SPEC = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour=SPEC_TEXT)
SECOND = {"room2_base_url": "https://api.openai.com/v1", "room2_api_key": "sk-secret-room2", "room2_model": "gpt-4o-mini"}


class SecondLLM(RoomLLM):
    """The second endpoint: it only ever sees clean room 2."""

    def __init__(self, sketches, fail=False):
        super().__init__([], rooms=[[], list(sketches)])
        self.fail = fail
        self.steps: list[str] = []

    async def code(self, system, user, step, temperature=None, seed=None):
        self.steps.append(step)
        if self.fail:
            raise LLMError("LLM request failed with HTTP 401: bad key")
        return await super().code(system, user, step, temperature, seed)


class MainLLM(RoomLLM):
    def __init__(self, patches, room_one):
        super().__init__(patches, rooms=[list(room_one), []])
        self.steps: list[str] = []

    async def code(self, system, user, step, temperature=None, seed=None):
        self.steps.append(step)
        return await super().code(system, user, step, temperature, seed)


def run(patches, room_one=(CLEAN_OK,), room_two=(CLEAN_OK,), second=True, fail_second=False, **overrides):
    config = {"max_parallel": 2, "cross_check": True, **(SECOND if second else {}), **overrides}
    pipeline = Pipeline("r", settings(**config), RoomRunner(), NullStore(), NullBus())
    main = MainLLM(patches, room_one)
    pipeline.llm = main
    other = None
    if pipeline.llm2 is not None:
        other = SecondLLM(room_two, fail=fail_second)
        pipeline.llm2 = other
    status, report = asyncio.run(pipeline.run_break(ORIGINAL, SPEC))
    return status, report, main, other


def test_room_two_is_written_by_the_second_model_and_room_one_by_the_main_one():
    _, report, main, other = run([PERSIST_FIXED])
    assert [s for s in main.steps if s.startswith("cleanroom")] == ["cleanroom1"]
    assert other.steps == ["cleanroom2"]
    cross = report["cross_check"]
    assert [(r["index"], r["model"], r["host"]) for r in cross["rooms"]] == [(1, "m", "unused"), (2, "gpt-4o-mini", "api.openai.com")]
    diversity = cross["model_diversity"]
    assert diversity["mixed"] is True and diversity["fallback"] is False
    assert "gpt-4o-mini" in diversity["note"]


def test_both_rooms_get_the_same_spec_only_prompt():
    _, _, main, other = run([PERSIST_FIXED])
    assert main.room_prompts[1][0] == other.room_prompts[2][0]
    assert "CHATTER" not in other.room_prompts[2][0]
    assert other.room_sampling[2]["temperature"] == 0.7


def test_cost_is_recorded_per_provider():
    _, report, _, _ = run([HEARTBEAT_ONLY], room_one=[CLEAN_CHATTERS], room_two=[CLEAN_CHATTERS])
    llm = report["llm"]
    by_role = {p["role"]: p for p in llm["providers"]}
    assert set(by_role) == {"agent", "cleanroom2"}
    # The second endpoint only paid for clean room 2: one call of 100 prompt and 50 completion tokens.
    assert by_role["cleanroom2"] == {"role": "cleanroom2", "model": "gpt-4o-mini", "host": "api.openai.com", "calls": 1, "prompt_tokens": 100, "completion_tokens": 50}
    assert by_role["agent"]["model"] == "m" and by_role["agent"]["host"] == "unused"
    assert by_role["agent"]["calls"] + 1 == llm["calls"]
    assert by_role["agent"]["prompt_tokens"] + 100 == llm["prompt_tokens"]
    assert llm["by_step"]["cleanroom1"]["calls"] == 1 and llm["by_step"]["cleanroom2"]["calls"] == 1
    assert [r["llm_calls"] for r in report["cross_check"]["rooms"]] == [1, 1]


def test_the_same_two_room_80_percent_rule_applies_to_mixed_rooms():
    # Both models misread the spec the same way: the check is dropped, as with two rooms of one model.
    _, report, _, _ = run([HEARTBEAT_ONLY], room_one=[CLEAN_CHATTERS], room_two=[CLEAN_CHATTERS])
    assert report["cross_check"]["rule"] == "both"
    assert [u["assertion_type"] for u in report["cross_check"]["unconfirmed"]] == ["max_toggles"]
    # One model gets it wrong, the other right: the bug stays.
    _, report, _, _ = run([PERSIST_FIXED], room_one=[CLEAN_CHATTERS], room_two=[CLEAN_OK])
    assert report["cross_check"]["unconfirmed"] == []
    _, report, _, _ = run([PERSIST_FIXED], room_one=[CLEAN_OK], room_two=[CLEAN_CHATTERS])
    assert report["cross_check"]["unconfirmed"] == []


def test_fallback_runs_two_rooms_on_the_main_model():
    config = {"max_parallel": 2, "cross_check": True}
    pipeline = Pipeline("r", settings(**config), RoomRunner(), NullStore(), NullBus())
    assert pipeline.llm2 is None and pipeline._room_llm(2) is pipeline.llm and pipeline._room_llm(1) is pipeline.llm
    pipeline.llm = RoomLLM([HEARTBEAT_ONLY], rooms=[[CLEAN_CHATTERS], [CLEAN_CHATTERS]])
    status, report = asyncio.run(pipeline.run_break(ORIGINAL, SPEC))
    cross = report["cross_check"]
    assert cross["rule"] == "both" and [r["status"] for r in cross["rooms"]] == ["ready", "ready"]
    assert [u["assertion_type"] for u in cross["unconfirmed"]] == ["max_toggles"]
    diversity = cross["model_diversity"]
    assert diversity["mixed"] is False and diversity["fallback"] is True
    assert "OPENAI_* is not configured" in diversity["note"] and "same model" in diversity["note"]
    assert [r["model"] for r in cross["rooms"]] == ["m", "m"]
    # One provider only, and both rooms' calls sit on it.
    assert [p["role"] for p in report["llm"]["providers"]] == ["agent"]
    assert report["llm"]["by_step"]["cleanroom1"]["calls"] == 1 and report["llm"]["by_step"]["cleanroom2"]["calls"] == 1


def test_the_mixed_switch_turns_the_second_model_off_even_with_a_key():
    pipeline = Pipeline("r", settings(cross_check=True, cleanroom_mixed=False, **SECOND), RoomRunner(), NullStore(), NullBus())
    assert pipeline.llm2 is None
    assert "CLEANROOM_MIXED is off" in pipeline._model_diversity()["note"]


def test_one_clean_room_never_calls_the_second_model():
    pipeline = Pipeline("r", settings(cross_check=True, cleanroom_samples=1, **SECOND), RoomRunner(), NullStore(), NullBus())
    assert pipeline.llm2 is None
    diversity = pipeline._model_diversity()
    assert diversity["mixed"] is False and diversity["fallback"] is False and "CLEANROOM_SAMPLES=1" in diversity["note"]


def test_a_second_model_that_fails_costs_one_room_and_the_other_room_decides_alone():
    status, report, _, other = run([HEARTBEAT_ONLY], room_one=[CLEAN_CHATTERS], fail_second=True)
    cross = report["cross_check"]
    assert other.steps == ["cleanroom2"]
    assert [r["status"] for r in cross["rooms"]] == ["ready", "skipped"]
    assert "could not be built" in cross["rooms"][1]["reason"] and "HTTP 401" in cross["rooms"][1]["reason"]
    assert cross["rule"] == "single"
    assert any("Falling back" in w for w in report["warnings"])
    assert status in ("fixed", "partial", "clean")


def test_no_api_key_reaches_the_report_or_the_events():
    _, report, _, _ = run([HEARTBEAT_ONLY], room_one=[CLEAN_CHATTERS], room_two=[CLEAN_CHATTERS])
    assert "sk-secret-room2" not in json.dumps(report)


def test_the_second_client_points_at_the_openai_endpoint_and_the_first_stays_on_the_main_one():
    pipeline = Pipeline("r", settings(cross_check=True, **SECOND), RoomRunner(), NullStore(), NullBus())
    assert pipeline.llm.settings.llm_model == "m" and pipeline.llm.settings.llm_api_key == "k"
    second = pipeline.llm2.settings
    assert (second.llm_base_url, second.llm_model, second.llm_api_key) == ("https://api.openai.com/v1", "gpt-4o-mini", "sk-secret-room2")
    assert str(pipeline.llm2.client.base_url).startswith("https://api.openai.com/v1")
    assert str(pipeline.llm.client.base_url).startswith("http://unused/v1")


def test_nothing_is_billed_to_either_endpoint_when_no_check_fails():
    config = {"max_parallel": 2, "cross_check": True, **SECOND}
    pipeline = Pipeline("r", settings(**config), RoomRunner(), NullStore(), NullBus())
    pipeline.llm = MainLLM([], [CLEAN_OK])
    pipeline.llm2 = SecondLLM([CLEAN_OK])
    status, report = asyncio.run(pipeline.run_break(CLEAN_OK, SPEC))
    assert status == "clean" and report["cross_check"]["status"] == "not_needed"
    assert [s for s in pipeline.llm.steps if s.startswith("cleanroom")] == []
    assert pipeline.llm2.steps == []
    assert "providers" not in report["llm"] or all(p["role"] != "cleanroom2" or p["calls"] == 0 for p in report["llm"]["providers"])
