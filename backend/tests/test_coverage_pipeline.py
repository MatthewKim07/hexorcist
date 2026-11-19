"""The spec-coverage step inside the pipeline, with a scripted model and a fake sandbox."""
import asyncio
import json
from pathlib import Path

from app.agent import Pipeline
from app.llm import LLMCall, LLMError
from app.models import DeviceSpec, PinSpec
from tests.test_api import settings
from tests.test_cross_check import CLEAN_OK, HEARTBEAT_ONLY, RoomLLM, RoomRunner
from tests.test_fix_loop import NullBus, NullStore, PERSIST_FIXED, run as plain_run

CHATTER = {"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 1000, "description": "No chatter", "spec_quote": "D9 must not chatter"}
HEARTBEAT = {"type": "serial_period", "pattern": "^hb$", "period_ms": 250, "tolerance_ms": 50, "description": "Heartbeat", "spec_quote": "Heartbeat every 250 ms"}
SPEC_TEXT = "- D9 must not chatter.\n- Heartbeat every 250 ms.\n"
SPEC = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour=SPEC_TEXT)
SILENT_ROOM = "void setup() {}\nvoid loop() { read(); } // SILENT\n"
SILENT_FW = SILENT_ROOM  # chatter-free, but the heartbeat the second bullet asks for never prints


class CoverageLLM(RoomLLM):
    """First pass returns `first`; the coverage call returns `extra` (or raises when extra is an exception)."""

    def __init__(self, first, extra, patches=(), rooms=None):
        super().__init__(list(patches), rooms)
        self.first, self.extra = first, extra
        self.steps: list[str] = []
        self.coverage_prompts: list[str] = []

    async def json(self, system, user, schema, step):
        self.steps.append(step)
        if step == "understand":
            return schema.model_validate({"assertions": self.first})
        if step == "coverage":
            self.coverage_prompts.append(user)
            self.calls.append(LLMCall(step=step, duration_ms=900, prompt_tokens=300, completion_tokens=80))
            if isinstance(self.extra, Exception):
                raise self.extra
            return schema.model_validate({"assertions": self.extra})
        return schema.model_validate({})


def go(first, extra, patches=(), rooms=None, coverage=True, spec=SPEC, firmware=CLEAN_OK):
    pipeline = Pipeline("r", settings(max_parallel=2, cross_check=True, coverage=coverage), RoomRunner(), NullStore(), NullBus())
    pipeline.llm = CoverageLLM(first, extra, patches, rooms)
    status, report = asyncio.run(pipeline.run_break(firmware, spec))
    return status, report, pipeline.llm


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items() if not (k.endswith("_s") or k in ("seconds", "wall_s", "elapsed_s", "created_at", "duration_s"))}
    if isinstance(o, list):
        return [clean(x) for x in o]
    return o


# ---------------------------------------------------------------- the switch is really off


def test_with_the_flag_off_the_report_is_exactly_the_one_the_code_gave_before_the_step_existed():
    status, report, runner, _ = plain_run([PERSIST_FIXED])
    golden = json.loads((Path(__file__).parent / "golden_flag_off.json").read_text())
    now = json.loads(json.dumps({"status": status, "report": clean(report), "compiled": runner.compiled}, sort_keys=True, default=str))
    assert now == golden
    assert "coverage" not in report


def test_with_the_flag_off_no_coverage_call_is_made_even_when_a_bullet_is_uncovered():
    status, report, llm = go([CHATTER], [HEARTBEAT], coverage=False)
    assert "coverage" not in llm.steps and "coverage" not in report and "coverage" not in report["llm"]["by_step"]
    assert [a["type"] for a in report["assertions"]] == ["max_toggles", "no_crash"]


def test_a_model_supplied_origin_is_never_trusted():
    status, report, llm = go([{**CHATTER, "origin": "coverage"}, HEARTBEAT], [], coverage=False)
    assert all("origin" not in a for a in report["assertions"])


# ---------------------------------------------------------------- covered and uncovered


def test_when_every_bullet_is_covered_there_is_no_extra_call():
    status, report, llm = go([CHATTER, HEARTBEAT], [HEARTBEAT])
    assert "coverage" not in llm.steps
    cov = report["coverage"]
    assert cov["enabled"] and cov["called"] is False and cov["uncovered"] == [] and cov["added"] == []
    assert [b["covered"] for b in cov["bullets"]] == [True, True]
    assert "coverage" not in report["llm"]["by_step"]


def test_a_covered_run_matches_the_flag_off_run_apart_from_the_coverage_record():
    on = go([CHATTER, HEARTBEAT], [], coverage=True)
    off = go([CHATTER, HEARTBEAT], [], coverage=False)
    a, b = clean(on[1]), clean(off[1])
    a.pop("coverage")
    assert on[0] == off[0] and a == b


def test_an_uncovered_bullet_costs_exactly_one_extra_call_and_gets_a_check():
    status, report, llm = go([CHATTER], [HEARTBEAT], patches=[PERSIST_FIXED], firmware=SILENT_FW)
    assert llm.steps.count("coverage") == 1
    cov = report["coverage"]
    assert cov["called"] and cov["uncovered"] == ["Heartbeat every 250 ms."] and cov["proposed"] == 1 and cov["rejected"] == []
    assert [b["covered"] for b in cov["bullets"]] == [True, False]
    added = [a for a in report["assertions"] if a.get("origin") == "coverage"]
    assert [a["type"] for a in added] == ["serial_period"] and cov["added"] == [added[0]["id"]]
    assert [a.get("origin") for a in report["assertions"] if a["type"] != "serial_period"] == [None, None]
    assert "Heartbeat every 250 ms" in llm.coverage_prompts[0] and "UNCOVERED BULLETS" in llm.coverage_prompts[0]
    assert report["llm"]["by_step"]["coverage"]["calls"] == 1


def test_a_check_from_the_coverage_step_is_reported_fixed_and_verified_like_any_other():
    # The silent heartbeat is found only through the coverage check, then fixed and re-run over the whole suite.
    status, report, llm = go([CHATTER], [HEARTBEAT], patches=[PERSIST_FIXED], rooms=[[CLEAN_OK], [CLEAN_OK]], firmware=SILENT_FW)
    assert status == "fixed" and report["fix"]["all_passing"] is True
    bug = next(b for b in report["bugs"] if b["assertion_type"] == "serial_period")
    assert bug["assertion_id"] == report["coverage"]["added"][0] and bug["verified"] is True


def test_the_check_exists_but_stays_unseen_without_the_step():
    status, report, llm = go([CHATTER], [HEARTBEAT], coverage=False, firmware=SILENT_FW)
    assert not any(b["assertion_type"] == "serial_period" for b in report["bugs"])


# ---------------------------------------------------------------- an empty or bad answer


def test_an_empty_answer_changes_nothing():
    status, report, llm = go([CHATTER], [])
    cov = report["coverage"]
    assert cov["called"] and cov["proposed"] == 0 and cov["added"] == []
    off = go([CHATTER], [], coverage=False)[1]
    assert [a["type"] for a in report["assertions"]] == [a["type"] for a in off["assertions"]] and "origin" not in json.dumps(report["assertions"])


def test_a_failed_coverage_call_leaves_the_checks_alone_and_says_so():
    status, report, llm = go([CHATTER], LLMError("boom"))
    assert report["coverage"]["error"] == "boom" and report["coverage"]["added"] == []
    assert any("spec coverage step failed" in w for w in report["warnings"])
    assert [a["type"] for a in report["assertions"]] == ["max_toggles", "no_crash"]


def test_a_check_quoting_a_covered_bullet_or_no_bullet_is_rejected():
    stray = {**HEARTBEAT, "spec_quote": "something the spec never says"}
    again = {**CHATTER, "max_toggles": 1}  # quotes the bullet that is already covered
    status, report, llm = go([CHATTER], [stray, again])
    cov = report["coverage"]
    assert cov["proposed"] == 2 and cov["added"] == [] and len(cov["rejected"]) == 2
    assert [a["type"] for a in report["assertions"]] == ["max_toggles", "no_crash"]


def test_a_quote_clipped_from_a_bullet_still_counts_as_covering_it():
    status, report, llm = go([CHATTER, {**HEARTBEAT, "spec_quote": "Heartbeat every 250"}], [HEARTBEAT])
    assert "coverage" not in llm.steps  # the quote falls inside the bullet, so it was covered


# ---------------------------------------------------------------- the same path as every other check


def test_a_coverage_check_asking_for_more_than_its_bullet_is_left_out_by_the_requirement_gate():
    spec = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour="- D9 must not chatter.\n- Relay on D9 holds its state.\n")
    limit = {"type": "max_toggles", "pin": "D9", "max_toggles": 0, "window_ms": 1000, "description": "Holds", "spec_quote": "Relay on D9 holds its state"}
    status, report, llm = go([CHATTER], [limit], spec=spec)
    added = report["coverage"]["added"]
    assert len(added) == 1
    assert [u["assertion_id"] for u in report["ungrounded"]] == added and report["ungrounded"][0]["rule"] == "rate_limit"
    assert next(a for a in report["assertions"] if a["id"] == added[0])["origin"] == "coverage"
    assert all(b["assertion_id"] != added[0] for b in report["bugs"])


def test_a_coverage_check_the_clean_rooms_fail_too_is_unconfirmed_and_never_a_bug():
    status, report, llm = go([CHATTER], [HEARTBEAT], rooms=[[SILENT_ROOM], [SILENT_ROOM]], firmware=SILENT_FW)
    added = report["coverage"]["added"]
    cross = report["cross_check"]
    assert cross["status"] == "ran"
    assert [a["id"] for a in report["assertions"] if a.get("unconfirmed")] == added
    assert all(b["assertion_id"] != added[0] for b in report["bugs"])


def test_the_coverage_check_goes_through_the_scenarios_and_the_baseline_matrix():
    status, report, llm = go([CHATTER], [HEARTBEAT], patches=[PERSIST_FIXED], firmware=SILENT_FW)
    aid = report["coverage"]["added"][0]
    row = report["matrix"]["0"]
    assert row and all(any(r["assertion_id"] == aid for r in results) for results in row.values())
