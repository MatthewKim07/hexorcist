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


def test_text_checks_have_no_shared_timing_so_failing_the_same_kind_of_way_is_enough():
    user = result("a2", "s", kind="serial_period", spans=((0, 100),))
    clean = result("a2", "s", kind="serial_period", spans=((9000, 9100),))
    assert same_way(user, clean)


def test_printing_nothing_is_not_the_way_a_slow_printer_fails():
    # nav_beacon_byte_timer: the uploaded firmware prints the line at the wrong period (the real bug), while the clean-room
    # sketch never printed it. That says nothing about whether the period check is fair.
    slow = result("a2", "s", kind="serial_period")
    slow.metrics = {"matches": 22, "worst_gap_ms": 1631}
    silent = result("a2", "s", kind="serial_period")
    silent.metrics = {"matches": 0}
    assert not same_way(slow, silent)
    assert not same_way(silent, slow)
    assert same_way(silent, silent)


def test_a_crash_and_a_deadlock_are_different_failures():
    a = result("a9", "s", kind="no_crash")
    a.metrics = {"exit_reason": "crash"}
    b = result("a9", "s", kind="no_crash")
    b.metrics = {"exit_reason": "sleep_deadlock"}
    assert not same_way(a, b) and same_way(a, a)


def run_classify(user_failing, rooms_failing, total=10, kind="output_follows", clean_spans=((100, 600),)):
    """Classify one assertion. rooms_failing has one set of failing scenarios per clean room."""
    scenarios = [f"s{i}" for i in range(total)]
    user = {s: [result("a1", s, "fail" if s in user_failing else "pass", kind)] for s in scenarios}
    rooms = [{s: [result("a1", s, "fail" if s in failing else "pass", kind, clean_spans, evidence=f"room {k + 1} in {s}")] for s in scenarios} for k, failing in enumerate(rooms_failing)]
    return classify(user, rooms, scenarios)["a1"]


def ids(n):
    return {f"s{i}" for i in range(n)}


def test_a_check_both_clean_rooms_fail_everywhere_is_unconfirmed():
    v = run_classify(ids(10), [ids(10), ids(10)])
    assert v.unconfirmed
    assert [r["shared"] for r in v.rooms] == [10, 10]
    assert v.user_evidence and v.cleanroom_evidence and v.rooms[1]["evidence"]


def test_a_check_only_the_uploaded_firmware_fails_is_confirmed():
    assert not run_classify(ids(4), [set(), set()]).unconfirmed


def test_each_room_must_fail_at_least_80_percent_of_the_scenarios():
    assert run_classify(ids(10), [ids(8), ids(8)]).unconfirmed  # exactly 80%
    assert not run_classify(ids(10), [ids(7), ids(10)]).unconfirmed  # 70% in one room
    assert not run_classify(ids(10), [ids(10), ids(7)]).unconfirmed


def test_a_single_room_needs_the_same_80_percent():
    assert run_classify(ids(5), [ids(4)]).unconfirmed
    assert not run_classify(ids(5), [ids(3)]).unconfirmed  # the old rule (a majority) would have dropped this one
    assert not run_classify(ids(4), [{"s0", "s1"}]).unconfirmed


def test_with_no_clean_room_nothing_is_unconfirmed():
    assert not run_classify(ids(4), []).unconfirmed


def test_a_room_failing_elsewhere_does_not_excuse_the_uploaded_firmware():
    # It fails the same assertion, but at other times: a different problem, so the uploaded failure stands.
    assert not run_classify(ids(4), [ids(4), ids(4)], clean_spans=((5000, 6000),)).unconfirmed


def test_only_assertions_that_fail_get_a_verdict():
    scenarios = ["s0"]
    user = {"s0": [result("a1", "s0", "pass"), result("a2", "s0", "fail")]}
    clean = {"s0": [result("a1", "s0", "fail"), result("a2", "s0", "pass")]}
    assert set(classify(user, [clean, clean], scenarios)) == {"a2"}


def test_glue_solenoid_short_pattern_one_flawed_clean_room_must_not_hide_a_real_bug():
    # The uploaded sketch ends the pulse after 1000 ms instead of 2500 (the real bug). Clean room 1 never ends the pulse,
    # a different failure of the same check at the same times. Clean room 2 is right, so it passes.
    def pulse(status, ms, evidence):
        r = result("a1", "s", status, "timed_pulse", ((1030, 1030 + ms),), evidence=evidence)
        return r

    scenarios = [f"s{i}" for i in range(14)]
    user = {s: [pulse("fail", 1000, "4 of 4 pulse(s) had the wrong length: lasted 1000 ms, expected 2500")] for s in scenarios}
    flawed = {s: [pulse("fail", 6900, "still on after 6968 ms, expected 2500")] for s in scenarios[:12]} | {s: [pulse("pass", 0, "ok")] for s in scenarios[12:]}
    right = {s: [pulse("pass", 0, "ok")] for s in scenarios}
    one_room = classify(user, [flawed], scenarios)["a1"]
    assert one_room.unconfirmed  # with only the flawed room (12 of 14 is 86%) the real bug would have been dropped
    both = classify(user, [flawed, right], scenarios)["a1"]
    assert not both.unconfirmed
    assert [r["shared"] for r in both.rooms] == [12, 0]


def test_rail_limit_invert_pattern_the_flawed_room_shares_17_of_18_and_the_good_room_none():
    scenarios = [f"s{i}" for i in range(18)]
    user = {s: [result("a1", s, "fail", "output_follows", ((100, 4800),))] for s in scenarios}
    flawed = {s: [result("a1", s, "fail" if i < 17 else "pass", "output_follows", ((100, 4100),))] for i, s in enumerate(scenarios)}
    right = {s: [result("a1", s, "pass")] for s in scenarios}
    assert not classify(user, [flawed, right], scenarios)["a1"].unconfirmed
    assert not classify(user, [right, flawed], scenarios)["a1"].unconfirmed
    assert classify(user, [flawed, flawed], scenarios)["a1"].unconfirmed  # two rooms that agree really are two opinions


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
    """Scripted model. `rooms` holds one list of sketches per clean-room sample: the first reply, then any repair."""

    def __init__(self, patches, rooms=None):
        super().__init__(patches)
        self.rooms = [list(r) for r in (rooms if rooms is not None else [[CLEAN_OK], [CLEAN_OK]])]
        self.room_prompts: dict[int, list[str]] = {1: [], 2: []}
        self.room_sampling: dict[int, dict] = {}

    async def code(self, system, user, step, temperature=None, seed=None):
        if step.startswith("cleanroom"):
            n = int(step[len("cleanroom"):])
            self.room_prompts[n].append(user)
            self.room_sampling[n] = {"temperature": temperature, "seed": seed}
            code = self.rooms[n - 1].pop(0)
            self.calls.append(LLMCall(step=step, duration_ms=1500, prompt_tokens=100, completion_tokens=50))
            return code, f"```cpp\n{code}```"
        return await super().code(system, user, step)


def run(patches, rooms=None, **overrides):
    runner = RoomRunner()
    pipeline = Pipeline("r", settings(**{"max_parallel": 2, "cross_check": True, **overrides}), runner, NullStore(), NullBus())
    pipeline.llm = RoomLLM(patches, rooms)
    status, report = asyncio.run(pipeline.run_break(ORIGINAL, SPEC))
    return status, report, runner, pipeline.llm


BOTH_CHATTER = [[CLEAN_CHATTERS], [CLEAN_CHATTERS]]


def test_a_check_both_clean_rooms_fail_too_is_not_reported_as_a_bug():
    status, report, _, llm = run([HEARTBEAT_ONLY], rooms=BOTH_CHATTER)
    cross = report["cross_check"]
    assert cross["status"] == "ran" and cross["rule"] == "both"
    assert [u["assertion_type"] for u in cross["unconfirmed"]] == ["max_toggles"]
    assert [b["assertion_type"] for b in report["bugs"]] == ["serial_period"]
    # The patch still chatters, but the chatter check is unconfirmed, so it is not a fix target and does not block "fixed".
    assert status == "fixed"
    assert report["score"]["possible_ambiguities"] == 1
    assert any(a.get("unconfirmed") for a in report["assertions"])


def test_one_flawed_clean_room_does_not_hide_a_real_bug():
    # Room 1 repeats the bug (it chatters too), room 2 is right. The chatter check stays a bug and gets fixed.
    status, report, _, llm = run([PERSIST_FIXED], rooms=[[CLEAN_CHATTERS], [CLEAN_OK]])
    assert report["cross_check"]["unconfirmed"] == []
    assert {b["assertion_type"] for b in report["bugs"]} == {"max_toggles", "serial_period"}
    assert status == "fixed" and "No chatter" in llm.fix_prompts[0]
    assert run([PERSIST_FIXED], rooms=[[CLEAN_OK], [CLEAN_CHATTERS]])[1]["cross_check"]["unconfirmed"] == []


def test_the_fix_prompt_carries_confirmed_checks_only():
    _, _, _, llm = run([HEARTBEAT_ONLY], rooms=BOTH_CHATTER)
    assert "Heartbeat" in llm.fix_prompts[0]
    assert "No chatter" not in llm.fix_prompts[0]


def test_an_unconfirmed_failure_is_shown_with_every_measurement():
    _, report, _, _ = run([HEARTBEAT_ONLY], rooms=BOTH_CHATTER)
    item = report["cross_check"]["unconfirmed"][0]
    assert "toggled" in item["your_firmware"] and "toggled" in item["clean_room"]
    assert len(item["clean_rooms"]) == 2 and all("toggled" in r["evidence"] for r in item["clean_rooms"])
    assert item["failing_scenarios"] >= 1 and item["shared_scenarios"] >= 1


def test_a_clean_implementation_leaves_every_failure_a_bug():
    status, report, _, _ = run([PERSIST_FIXED], rooms=[[CLEAN_OK], [CLEAN_OK]])
    assert report["cross_check"]["unconfirmed"] == []
    assert {b["assertion_type"] for b in report["bugs"]} == {"max_toggles", "serial_period"}
    assert status == "fixed"


def test_the_clean_room_prompts_never_contain_the_uploaded_sketch_and_the_samples_differ_only_in_sampling():
    _, _, _, llm = run([PERSIST_FIXED])
    for n in (1, 2):
        assert llm.room_prompts[n] and "CHATTER" not in llm.room_prompts[n][0]
        assert "Heartbeat every 250 ms" in llm.room_prompts[n][0]
        assert llm.room_sampling[n]["temperature"] == 0.7
    assert llm.room_prompts[1][0] == llm.room_prompts[2][0]
    assert llm.room_sampling[1]["seed"] != llm.room_sampling[2]["seed"]


def test_if_one_clean_room_never_compiles_the_other_decides_alone_at_80_percent():
    status, report, _, _ = run([HEARTBEAT_ONLY], rooms=[["NOCOMPILE one\n", "NOCOMPILE two\n"], [CLEAN_CHATTERS]])
    cross = report["cross_check"]
    assert cross["status"] == "ran" and cross["rule"] == "single"
    assert [r["status"] for r in cross["rooms"]] == ["skipped", "ready"]
    assert "one repair" in cross["rooms"][0]["reason"]
    assert [u["assertion_type"] for u in cross["unconfirmed"]] == ["max_toggles"]
    assert any("Falling back" in w for w in report["warnings"])


def test_the_single_remaining_room_still_cannot_drop_a_check_it_passes():
    _, report, _, _ = run([PERSIST_FIXED], rooms=[[CLEAN_OK], ["NOCOMPILE\n", "NOCOMPILE\n"]])
    assert report["cross_check"]["rule"] == "single" and report["cross_check"]["unconfirmed"] == []


def test_when_neither_clean_room_compiles_the_cross_check_is_skipped_and_recorded():
    status, report, _, _ = run([PERSIST_FIXED], rooms=[["NOCOMPILE one\n", "NOCOMPILE two\n"], ["NOCOMPILE three\n", "NOCOMPILE four\n"]])
    cross = report["cross_check"]
    assert cross["status"] == "skipped" and cross["rule"] == "none"
    assert "one repair" in cross["reason"]
    assert cross["unconfirmed"] == []
    assert any("cross-check skipped" in w for w in report["warnings"])
    # Without a cross-check every failure stays a bug, exactly as before.
    assert {b["assertion_type"] for b in report["bugs"]} == {"max_toggles", "serial_period"}
    assert status == "fixed"


def test_one_repair_attempt_rescues_a_clean_room_that_did_not_compile():
    _, report, _, llm = run([PERSIST_FIXED], rooms=[["NOCOMPILE\n", CLEAN_CHATTERS], [CLEAN_CHATTERS]])
    cross = report["cross_check"]
    assert cross["status"] == "ran" and cross["rule"] == "both" and cross["usage"]["repaired"] is True
    assert "Compiler output" in llm.room_prompts[1][1]


def test_one_sample_can_be_asked_for_and_then_the_single_room_rule_applies():
    _, report, _, llm = run([HEARTBEAT_ONLY], rooms=[[CLEAN_CHATTERS]], cleanroom_samples=1)
    assert report["cross_check"]["rule"] == "single" and len(report["cross_check"]["rooms"]) == 1
    assert llm.room_prompts[2] == []


def test_the_cross_check_can_be_switched_off():
    _, report, runner, llm = run([PERSIST_FIXED], cross_check=False)
    assert report["cross_check"]["status"] == "disabled"
    assert llm.room_prompts == {1: [], 2: []}


def test_both_clean_rooms_cost_and_time_are_recorded():
    _, report, _, _ = run([HEARTBEAT_ONLY], rooms=BOTH_CHATTER)
    cross = report["cross_check"]
    usage = cross["usage"]
    assert usage["llm_calls"] == 2 and usage["prompt_tokens"] == 200 and usage["completion_tokens"] == 100
    assert usage["sandbox_runs"] >= 2 and usage["sandbox_s"] >= 0
    assert [r["llm_calls"] for r in cross["rooms"]] == [1, 1]
    assert all(r["prompt_tokens"] == 100 and r["firmware"] for r in cross["rooms"])
    assert report["llm"]["by_step"]["cleanroom1"]["calls"] == 1 and report["llm"]["by_step"]["cleanroom2"]["calls"] == 1


def test_no_failures_means_no_clean_room_run():
    # Nothing failed on the uploaded firmware, so there is nothing to classify.
    runner = RoomRunner()
    pipeline = Pipeline("r", settings(max_parallel=2, cross_check=True), runner, NullStore(), NullBus())
    pipeline.llm = RoomLLM([], [[CLEAN_OK], [CLEAN_OK]])
    status, report = asyncio.run(pipeline.run_break(CLEAN_OK, SPEC))
    assert status == "clean"
    assert report["cross_check"]["status"] == "not_needed"
    assert crosscheck.unconfirmed_ids({}) == set()


def test_a_run_where_nothing_fails_never_calls_either_clean_room_model():
    # Billing: the clean rooms used to be written before anyone knew whether a check would fail.
    runner = RoomRunner()
    pipeline = Pipeline("r", settings(max_parallel=2, cross_check=True), runner, NullStore(), NullBus())
    pipeline.llm = RoomLLM([], [[CLEAN_OK], [CLEAN_OK]])
    status, report = asyncio.run(pipeline.run_break(CLEAN_OK, SPEC))
    assert status == "clean"
    cross = report["cross_check"]
    assert cross["status"] == "not_needed"
    assert pipeline.llm.room_prompts == {1: [], 2: []}
    assert pipeline.llm.calls == [c for c in pipeline.llm.calls if not c.step.startswith("cleanroom")]
    assert cross["rooms"] == [] and cross["usage"]["llm_calls"] == 0 and cross["usage"]["sandbox_runs"] == 0
    assert not any(k.startswith("cleanroom") for k in report["llm"]["by_step"])
    assert pipeline._room_tasks == []


def test_the_first_failing_check_starts_the_clean_rooms_once():
    status, report, _, llm = run([PERSIST_FIXED], rooms=[[CLEAN_OK], [CLEAN_OK]])
    assert report["cross_check"]["status"] == "ran"
    assert [len(llm.room_prompts[1]), len(llm.room_prompts[2])] == [1, 1]
