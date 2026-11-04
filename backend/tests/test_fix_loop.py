"""The fix loop, with a scripted model and a fake sandbox. No Docker, no LLM.

Firmware behaviour is faked from markers in its source: CHATTER makes the output toggle too often,
SILENT stops the heartbeat. The real assertion engine judges the resulting traces.
"""
import asyncio

from app import prompts
from app.agent import Pipeline
from app.approach import Attempt, find_code_reversion, find_measured_reversion
from app.models import DeviceSpec, PinSpec
from app.sandbox import CompileResult, ContainmentRecord, RunResult
from tests.test_api import settings

ORIGINAL = "void setup() {}\nvoid loop() { read(); } // CHATTER SILENT\n"

DWELL = """const unsigned long MIN_DWELL_MS = 3000;
unsigned long lastSwitchMs = 0;
void setup() {}
void loop()
{
    if (millis() - lastSwitchMs >= MIN_DWELL_MS)
    {
        lastSwitchMs = millis();
        read();
    }
} // SILENT
"""

PERSIST = """const int SWITCH_SAMPLES = 4;
int stableCount = 0;
void setup() {}
void loop()
{
    stableCount = read() ? stableCount + 1 : 0;
    if (stableCount >= SWITCH_SAMPLES)
    {
        act();
    }
} // SILENT
"""

PERSIST_FIXED = PERSIST.replace("} // SILENT", "    heartbeat();\n} // fixed")

DWELL_AGAIN = PERSIST.replace("void setup() {}", "const unsigned long MIN_DWELL_MS = 2500;\nunsigned long lastSwitchMs = 0;\nvoid setup() {}")

UNDERSTAND = {
    "assertions": [
        {"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 1000, "description": "No chatter"},
        {"type": "serial_period", "pattern": "^hb$", "period_ms": 250, "tolerance_ms": 50, "description": "Heartbeat"},
    ]
}


def fake_trace(code: str) -> dict:
    beats = [] if "SILENT" in code else [{"t_ms": float(t), "text": "hb"} for t in range(250, 2000, 250)]
    toggles = [{"t_ms": float(t), "pin": "D9", "value": (t // 20) % 2, "dir": "out"} for t in range(20, 400, 20)] if "CHATTER" in code else []
    return {"exit_reason": "completed", "sim_ms": 2000.0, "input_trace": [], "pin_events": toggles, "pwm_events": [], "serial_log": beats}


class FakeRunner:
    def __init__(self):
        self.compiled: list[str] = []

    def compile(self, sketch, label="compile"):
        self.compiled.append(sketch)
        return CompileResult(ok=True, log="", elf=sketch.encode(), record=ContainmentRecord(kind="compile", label=label))

    def run(self, elf, scenario, label, no_sim_cap=False):
        return RunResult(trace=fake_trace(elf.decode()), record=ContainmentRecord(kind="emulate", label=label))


class FakeLLM:
    def __init__(self, patches):
        self.patches = list(patches)
        self.calls = []
        self.fix_prompts: list[str] = []

    async def json(self, system, user, schema, step):
        return schema.model_validate(UNDERSTAND if step == "understand" else {})

    async def code(self, system, user, step):
        self.fix_prompts.append(user)
        code = self.patches.pop(0)
        return code, f"Patch.\n```cpp\n{code}```"


class NullStore:
    def add_trace(self, *args):
        pass


class NullBus:
    async def emit(self, *args, **kwargs):
        pass

    async def step(self, *args, **kwargs):
        pass


def run(patches):
    spec = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour="x")
    runner = FakeRunner()
    pipeline = Pipeline("r", settings(max_parallel=2), runner, NullStore(), NullBus())
    pipeline.llm = FakeLLM(patches)
    status, report = asyncio.run(pipeline.run_break(ORIGINAL, spec))
    return status, report, runner, pipeline.llm


def test_a_patch_going_back_to_a_disproven_approach_is_sent_back_without_testing():
    # Attempt 1 chatters. Attempt 2 is better, so attempt 1 is disproven. The revert is then refused.
    status, report, runner, llm = run([DWELL + "// CHATTER\n", PERSIST, DWELL_AGAIN, PERSIST_FIXED])
    assert status == "fixed"
    assert report["fix"]["iteration"] == 3
    assert DWELL_AGAIN not in runner.compiled
    assert any("sent back without testing" in w for w in report["warnings"])
    assert "rejected_without_testing" in llm.fix_prompts[3]
    assert report["score"]["fix_attempts"] == 3


def test_a_model_that_insists_on_reverting_loses_the_attempt():
    status, report, runner, llm = run([DWELL + "// CHATTER\n", PERSIST, DWELL_AGAIN, DWELL_AGAIN])
    row = report["iterations"][3]
    assert row["rejected"] is True
    assert row["reverted_to"] == 1
    assert row["failing"] is None
    assert DWELL_AGAIN not in runner.compiled
    assert status == "partial"
    assert report["fix"]["iteration"] == 2


def test_a_worse_patch_is_not_the_base_for_the_next_attempt():
    status, report, runner, llm = run([PERSIST, PERSIST + "// CHATTER\n", PERSIST_FIXED])
    assert status == "fixed"
    assert "CHATTER" not in llm.fix_prompts[2].split("ALL ASSERTIONS")[0]
    assert "discarded" in llm.fix_prompts[2]


def test_the_model_is_told_which_attempts_were_disproven():
    _, _, _, llm = run([DWELL + "// CHATTER\n", PERSIST, PERSIST_FIXED])
    assert '"status": "disproven"' in llm.fix_prompts[2]
    assert '"status": "your best patch so far"' in llm.fix_prompts[2]
    assert "No chatter" in llm.fix_prompts[2]


def test_repeating_measured_failures_is_rejected_even_under_new_names():
    renamed = DWELL.replace("MIN_DWELL_MS", "HOLD_TIME").replace("lastSwitchMs", "stampMs").replace("3000", "2000") + "// CHATTER\n"
    # Attempt 1 fails both checks, attempt 2 one, attempt 3 is a renamed attempt 1 with different shape names.
    status, report, runner, llm = run([DWELL + "// CHATTER\n", PERSIST, renamed])
    assert renamed in runner.compiled
    assert report["iterations"][3]["rejected"] is True
    assert report["iterations"][3]["reverted_to"] == 1
    assert report["fix"]["iteration"] == 2
    assert status == "partial"


def test_refining_the_best_patch_is_allowed():
    status, report, runner, _ = run([DWELL + "// CHATTER\n", PERSIST, PERSIST_FIXED])
    assert status == "fixed"
    assert PERSIST_FIXED in runner.compiled
    assert not any("rejected" in w or "sent back" in w for w in report["warnings"])


def test_a_new_mechanism_is_not_mistaken_for_a_revert():
    disproven = [Attempt(n=1, code=DWELL)]
    assert find_code_reversion(PERSIST, disproven, None, ORIGINAL) is None


def test_machinery_the_best_patch_still_uses_is_not_disproven():
    disproven = [Attempt(n=1, code=PERSIST)]
    refined = PERSIST.replace("SWITCH_SAMPLES = 4", "SWITCH_SAMPLES = 3")
    assert find_code_reversion(refined, disproven, PERSIST_FIXED, ORIGINAL) is None


def test_identical_code_is_a_revert_whatever_its_comments_or_spacing():
    disproven = [Attempt(n=1, code=PERSIST)]
    respaced = "// a new comment\n" + PERSIST.replace("    ", "  ")
    reverted = find_code_reversion(respaced, disproven, PERSIST_FIXED + "extra();", ORIGINAL)
    assert reverted is not None and reverted.attempt == 1


def test_comments_do_not_count_as_machinery():
    disproven = [Attempt(n=1, code=DWELL)]
    commented = PERSIST + "// no MIN_DWELL_MS or lastSwitchMs here\n"
    assert find_code_reversion(commented, disproven, None, ORIGINAL) is None


def test_measured_reversion_on_the_real_thermostat_failures():
    # Attempts 1 and 3 from a real run, and attempt 2, which was a different approach.
    a1 = {("a1", s) for s in ("ramp", "spike", "llm-1", "llm-10", "llm-4", "llm-5", "llm-6")} | {("a2", "spike")}
    a2 = {("a2", "spike"), ("a1", "llm-4"), ("a2", "llm-7")}
    disproven = [Attempt(n=1, code="", failing=a1)]
    assert find_measured_reversion(set(a1), disproven).attempt == 1
    assert find_measured_reversion(a2, disproven) is None
    assert find_measured_reversion(set(), disproven) is None


def test_fix_prompt_carries_history_only_when_there_is_some():
    spec = DeviceSpec()
    assert "EARLIER ATTEMPTS" not in prompts.fix_user("x", spec, [], [])
    assert "EARLIER ATTEMPTS" in prompts.fix_user("x", spec, [], [], None, [{"attempt": 1}])
