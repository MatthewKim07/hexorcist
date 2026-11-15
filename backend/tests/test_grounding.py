"""Spec grounding: assertions must quote a sentence the spec really contains."""
import asyncio

from app.agent import Pipeline, normalize_assertions
from app.grounding import find_quote
from app.models import DeviceSpec, PinSpec
from tests.test_api import settings
from tests.test_fix_loop import FakeLLM, FakeRunner, NullBus, NullStore, ORIGINAL, PERSIST_FIXED

SPEC_TEXT = """- Turn the fan ON at 30.0 °C or above and OFF at 27.0 °C or below.
- The fan must not change state more than 2 times in any 5000 ms window.
- If the sensor reads below 0.2 V, treat it as disconnected and switch the fan ON within 1 s.
"""
SPEC = DeviceSpec(
    pins=[PinSpec(pin="A0", type="analog_input", scale="10 mV/°C"), PinSpec(pin="D9", type="digital_output")],
    behaviour=SPEC_TEXT,
)


def toggles(quote, **extra):
    return {"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 5000, "description": "Fan limit", "spec_quote": quote, **extra}


def test_an_exact_quote_is_found():
    assert find_quote("The fan must not change state more than 2 times in any 5000 ms window.", SPEC_TEXT) == (True, "")


def test_case_markdown_and_punctuation_do_not_matter():
    assert find_quote("**the FAN must not change state** more than 2 times in any 5000 ms window", SPEC_TEXT)[0]
    assert find_quote("Turn the fan ON at 30.0 °C or above, and OFF at 27.0 °C or below", SPEC_TEXT)[0]


def test_a_quote_may_start_or_end_mid_sentence():
    assert find_quote("must not change state more than 2 times", SPEC_TEXT)[0]


def test_one_dropped_word_in_a_long_quote_is_tolerated():
    # 15 of 16 words, in two runs, is 94%.
    assert find_quote("Turn the fan ON at 30.0 °C or above and OFF at 27.0 or below", SPEC_TEXT)[0]


def test_a_sentence_the_spec_does_not_contain_is_refused():
    found, reason = find_quote("The fan must keep running until the operator presses the reset button.", SPEC_TEXT)
    assert not found and "not found" in reason


def test_scattered_common_words_do_not_make_a_quote_real():
    assert not find_quote("the fan must be at or above 30.0 and the sensor must be off", SPEC_TEXT)[0]


def test_a_wrong_number_is_refused_inside_an_otherwise_real_quote():
    found, reason = find_quote("The fan must not change state more than 9 times in any 5000 ms window", SPEC_TEXT)
    assert not found and "9" in reason


def test_a_missing_or_tiny_quote_is_refused():
    assert find_quote("", SPEC_TEXT)[1] == "it has no spec_quote"
    assert "too short" in find_quote("the fan", SPEC_TEXT)[1]


def test_grounded_normalization_drops_and_logs_what_it_cannot_cite():
    raw = [
        toggles("The fan must not change state more than 2 times in any 5000 ms window"),
        toggles("The fan must never switch more than twice", description="Invented"),
        {"type": "max_toggles", "pin": "D9", "max_toggles": 5, "window_ms": 1000, "description": "No quote at all"},
    ]
    drops: list[dict] = []
    kept, warnings = normalize_assertions(raw, SPEC, ground=True, drops=drops)
    assert [a.type for a in kept] == ["max_toggles", "no_crash"]
    assert [d["description"] for d in drops] == ["Invented", "No quote at all"]
    assert "not found in the spec" in drops[0]["reason"] and drops[1]["reason"] == "it has no spec_quote"
    assert sum("Dropped max_toggles" in w for w in warnings) == 2


def test_without_grounding_nothing_is_dropped_for_its_quote():
    kept, _ = normalize_assertions([toggles("made up words that are nowhere")], SPEC)
    assert [a.type for a in kept] == ["max_toggles", "no_crash"]


def test_the_quote_does_not_make_two_equal_checks_different():
    raw = [toggles("The fan must not change state more than 2 times in any 5000 ms window"), toggles("must not change state more than 2 times in any 5000 ms window")]
    kept, _ = normalize_assertions(raw, SPEC, ground=True)
    assert [a.type for a in kept] == ["max_toggles", "no_crash"]


def test_no_crash_needs_no_quote():
    kept, _ = normalize_assertions([{"type": "no_crash"}], SPEC, ground=True)
    assert [a.type for a in kept] == ["no_crash"]


class QuotingLLM(FakeLLM):
    def __init__(self, patches, assertions):
        super().__init__(patches)
        self.assertions = assertions

    async def json(self, system, user, schema, step):
        if step == "understand":
            return schema.model_validate({"assertions": self.assertions})
        return schema.model_validate({})


def test_a_run_reports_the_citations_it_dropped():
    spec = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour="D9 must not chatter. Heartbeat every 250 ms.")
    good = {"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 1000, "description": "No chatter", "spec_quote": "D9 must not chatter"}
    bad = {"type": "serial_period", "pattern": "^hb$", "period_ms": 250, "tolerance_ms": 50, "description": "Heartbeat", "spec_quote": "A heartbeat is printed twice a second"}
    pipeline = Pipeline("r", settings(max_parallel=2), FakeRunner(), NullStore(), NullBus())
    pipeline.llm = QuotingLLM([PERSIST_FIXED], [good, bad])
    status, report = asyncio.run(pipeline.run_break(ORIGINAL, spec))
    assert [a["type"] for a in report["assertions"]] == ["max_toggles", "no_crash"]
    grounding = report["grounding"]
    assert grounding["checked"] == 2 and [d["type"] for d in grounding["dropped"]] == ["serial_period"]
    assert any("not found in the spec" in w for w in report["warnings"])


def test_checks_the_user_already_saw_are_not_grounded_again():
    from app.checks import CheckSet

    spec = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour="D9 must not chatter.")
    shown = CheckSet(assertions=[{"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 1000, "description": "No chatter"}], source="example")
    pipeline = Pipeline("r", settings(max_parallel=2), FakeRunner(), NullStore(), NullBus())
    pipeline.llm = QuotingLLM([PERSIST_FIXED], [])
    _, report = asyncio.run(pipeline.run_break(ORIGINAL, spec, checks=shown))
    assert [a["type"] for a in report["assertions"]] == ["max_toggles", "no_crash"]
    assert "grounding" not in report
