"""Clean-room cross-check: classification, and the pipeline with a scripted model and a fake sandbox."""
import asyncio

from app import crosscheck
from app.agent import Pipeline
from app.crosscheck import classify, same_way
from app.llm import LLMCall
from app.models import AssertionResult, DeviceSpec, PinSpec, Violation
from app.sandbox import CompileResult, ContainmentRecord
from tests.test_api import settings
from tests.test_fix_loop import FakeLLM, FakeRunner, NullBus, NullStore, ORIGINAL, PERSIST_FIXED, SPEC_TEXT


def result(aid, sid, status="fail", kind="output_follows", spans=((100, 600),), evidence=""):
    return AssertionResult(
        assertion_id=aid,
        scenario_id=sid,
        type=kind,
        status=status,
        evidence=evidence or f"{aid} in {sid}",
        violations=[Violation(t_start=s, t_end=e) for s, e in spans] if status == "fail" else [],
    )


# ------------------------------------------------------------------ pure classification


def test_same_stretches_of_time_count_as_the_same_way():
    assert same_way(result("a1", "s", spans=((100, 600),)), result("a1", "s", spans=((150, 700),)))


def test_disjoint_stretches_are_a_different_failure():
    assert not same_way(result("a1", "s", spans=((100, 600),)), result("a1", "s", spans=((3000, 4000),)))


def test_a_pass_or_an_unmeasured_assertion_is_not_the_same_way():
    user = result("a1", "s")
    assert not same_way(user, result("a1", "s", status="pass"))
    assert not same_way(user, result("a1", "s", status="not_exercised"))
    assert not same_way(user, None)


def test_text_and_crash_checks_have_no_shared_timing_so_both_failing_is_enough():
    user = result("a2", "s", kind="serial_period", spans=((0, 100),))
    clean = result("a2", "s", kind="serial_period", spans=((9000, 9100),))
    assert same_way(user, clean)


def run_classify(user_failing, clean_failing, total=4, kind="output_follows", clean_spans=((100, 600),)):
    scenarios = [f"s{i}" for i in range(total)]
    user = {s: [result("a1", s, "fail" if s in user_failing else "pass", kind)] for s in scenarios}
    clean = {s: [result("a1", s, "fail" if s in clean_failing else "pass", kind, clean_spans)] for s in scenarios}
    return classify(user, clean, scenarios)["a1"]


def test_a_check_the_clean_room_firmware_also_fails_is_unconfirmed():
    v = run_classify({"s0", "s1", "s2", "s3"}, {"s0", "s1", "s2", "s3"})
    assert v.unconfirmed and v.shared == ["s0", "s1", "s2", "s3"]
    assert v.user_evidence and v.cleanroom_evidence


def test_a_check_only_the_uploaded_firmware_fails_is_confirmed():
    v = run_classify({"s0", "s1"}, set())
    assert not v.unconfirmed and v.shared == []


def test_a_majority_of_shared_failures_is_needed():
    assert run_classify({"s0", "s1", "s2", "s3"}, {"s0", "s1"}).unconfirmed
    assert not run_classify({"s0", "s1", "s2", "s3"}, {"s0"}).unconfirmed


def test_the_clean_room_failing_elsewhere_does_not_excuse_the_uploaded_firmware():
    # It fails the same assertion, but at other times: a different problem, so the uploaded failure stands.
    v = run_classify({"s0", "s1"}, {"s0", "s1"}, clean_spans=((5000, 6000),))
    assert not v.unconfirmed


def test_only_assertions_that_fail_get_a_verdict():
    scenarios = ["s0"]
    user = {"s0": [result("a1", "s0", "pass"), result("a2", "s0", "fail")]}
    clean = {"s0": [result("a1", "s0", "fail"), result("a2", "s0", "pass")]}
    assert set(classify(user, clean, scenarios)) == {"a2"}


# ------------------------------------------------------------------ the pipeline

SPEC = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour=SPEC_TEXT)
CLEAN_OK = "void setup() {}\nvoid loop() { heartbeat(); }\n"
CLEAN_CHATTERS = "void setup() {}\nvoid loop() { heartbeat(); } // CHATTER\n"
# Fixes the silent heartbeat but still chatters.
HEARTBEAT_ONLY = "void setup() {}\nvoid loop() { heartbeat(); } // CHATTER\n"


class RoomRunner(FakeRunner):
    """A fake sandbox that can refuse to compile marked sketches."""

    def compile(self, sketch, label="compile"):
        self.compiled.append(sketch)
        ok = "NOCOMPILE" not in sketch
        return CompileResult(ok=ok, log="" if ok else "error: boom", elf=sketch.encode() if ok else None, record=ContainmentRecord(kind="compile", label=label))


class RoomLLM(FakeLLM):
    def __init__(self, patches, room=None):
        super().__init__(patches)
        self.room = list(room if room is not None else [CLEAN_OK])
        self.room_prompts: list[str] = []

    async def code(self, system, user, step):
        if step == "cleanroom":
            self.room_prompts.append(user)
            code = self.room.pop(0)
            self.calls.append(LLMCall(step="cleanroom", duration_ms=1500, prompt_tokens=100, completion_tokens=50))
            return code, f"```cpp\n{code}```"
        return await super().code(system, user, step)


def run(patches, room=None, **overrides):
    runner = RoomRunner()
    pipeline = Pipeline("r", settings(**{"max_parallel": 2, "cross_check": True, **overrides}), runner, NullStore(), NullBus())
    pipeline.llm = RoomLLM(patches, room)
    status, report = asyncio.run(pipeline.run_break(ORIGINAL, SPEC))
    return status, report, runner, pipeline.llm


def test_a_check_a_clean_implementation_fails_too_is_not_reported_as_a_bug():
    status, report, _, llm = run([HEARTBEAT_ONLY], room=[CLEAN_CHATTERS])
    cross = report["cross_check"]
    assert cross["status"] == "ran"
    assert [u["assertion_type"] for u in cross["unconfirmed"]] == ["max_toggles"]
    assert [b["assertion_type"] for b in report["bugs"]] == ["serial_period"]
    # The patch still chatters, but the chatter check is unconfirmed, so it is not a fix target and does not block "fixed".
    assert status == "fixed"
    assert report["score"]["possible_ambiguities"] == 1
    assert any(a.get("unconfirmed") for a in report["assertions"])


def test_the_fix_prompt_carries_confirmed_checks_only():
    _, _, _, llm = run([HEARTBEAT_ONLY], room=[CLEAN_CHATTERS])
    assert "Heartbeat" in llm.fix_prompts[0]
    assert "No chatter" not in llm.fix_prompts[0]


def test_an_unconfirmed_failure_is_shown_with_both_measurements():
    _, report, _, _ = run([HEARTBEAT_ONLY], room=[CLEAN_CHATTERS])
    item = report["cross_check"]["unconfirmed"][0]
    assert "toggled" in item["your_firmware"]
    assert "toggled" in item["clean_room"]
    assert item["failing_scenarios"] >= 1 and item["shared_scenarios"] >= 1


def test_a_clean_implementation_leaves_every_failure_a_bug():
    status, report, _, _ = run([PERSIST_FIXED], room=[CLEAN_OK])
    assert report["cross_check"]["unconfirmed"] == []
    assert {b["assertion_type"] for b in report["bugs"]} == {"max_toggles", "serial_period"}
    assert status == "fixed"


def test_the_clean_room_prompt_never_contains_the_uploaded_sketch():
    _, _, _, llm = run([PERSIST_FIXED])
    assert llm.room_prompts and "CHATTER" not in llm.room_prompts[0]
    assert "Heartbeat every 250 ms" in llm.room_prompts[0]


def test_a_clean_room_that_never_compiles_is_skipped_and_recorded():
    status, report, _, _ = run([PERSIST_FIXED], room=["NOCOMPILE one\n", "NOCOMPILE two\n"])
    cross = report["cross_check"]
    assert cross["status"] == "skipped"
    assert "one repair" in cross["reason"]
    assert cross["unconfirmed"] == []
    assert any("cross-check skipped" in w for w in report["warnings"])
    # Without a cross-check every failure stays a bug, exactly as before.
    assert {b["assertion_type"] for b in report["bugs"]} == {"max_toggles", "serial_period"}
    assert status == "fixed"


def test_one_repair_attempt_rescues_a_clean_room_that_did_not_compile():
    _, report, _, llm = run([PERSIST_FIXED], room=["NOCOMPILE\n", CLEAN_CHATTERS])
    cross = report["cross_check"]
    assert cross["status"] == "ran" and cross["usage"]["repaired"] is True
    assert "Compiler output" in llm.room_prompts[1]


def test_the_cross_check_can_be_switched_off():
    _, report, runner, llm = run([PERSIST_FIXED], cross_check=False)
    assert report["cross_check"]["status"] == "disabled"
    assert llm.room_prompts == []


def test_clean_room_cost_and_time_are_recorded():
    _, report, _, _ = run([HEARTBEAT_ONLY], room=[CLEAN_CHATTERS])
    usage = report["cross_check"]["usage"]
    assert usage["llm_calls"] == 1 and usage["prompt_tokens"] == 100 and usage["completion_tokens"] == 50
    assert usage["sandbox_runs"] >= 1
    assert report["llm"]["by_step"]["cleanroom"]["calls"] == 1


def test_no_failures_means_no_clean_room_run():
    # Nothing failed on the uploaded firmware, so there is nothing to classify.
    runner = RoomRunner()
    pipeline = Pipeline("r", settings(max_parallel=2, cross_check=True), runner, NullStore(), NullBus())
    pipeline.llm = RoomLLM([], [CLEAN_OK])
    status, report = asyncio.run(pipeline.run_break(CLEAN_OK, SPEC))
    assert status == "clean"
    assert report["cross_check"]["status"] == "not_needed"
    assert crosscheck.unconfirmed_ids({}) == set()
