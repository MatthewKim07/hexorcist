"""Requirement grounding: a check may only ask for what the spec bullet it quotes asks for."""
from app.models import (
    DeviceSpec,
    MaxToggles,
    NoCrash,
    OutputFollows,
    PinSpec,
    Responsive,
    SafeStateOnFault,
    SerialPeriod,
    TimedPulse,
    TogglePerPress,
)
from app.requirements import bullet_of, check_requirement, counts, durations_ms, ungrounded_requirements


def spec(behaviour, *pins):
    return DeviceSpec(pins=list(pins), behaviour=behaviour)


FAN = PinSpec(pin="D5", type="digital_output")
TEMP = PinSpec(pin="A3", type="analog_input", scale="10 mV/°C")
BOOST = PinSpec(pin="D4", type="digital_input", active_low=True)
MODE = PinSpec(pin="D2", type="digital_input", active_low=True)
LAMP = PinSpec(pin="D7", type="digital_output")


def cond(pin, op, value):
    return {"pin": pin, "op": op, "value": value}


def follows(quote, high=None, low=None, pin="D5", **kw):
    return OutputFollows(pin=pin, high_when=high and cond(*high), low_when=low and cond(*low), spec_quote=quote, id="a1", **kw)


# ------------------------------------------------------------------ hysteresis band


def test_a_hysteresis_band_the_spec_states_passes():
    s = spec("- Turn the fan ON at 36.0 °C or above; turn it OFF at 32.0 °C or below.", FAN, TEMP)
    a = follows("Turn the fan ON at 36.0 °C or above; turn it OFF at 32.0 °C or below.", ("A3", ">=", 36.0), ("A3", "<=", 32.0))
    assert check_requirement(a, s) is None


def test_a_band_the_spec_never_states_is_marked():
    s = spec("- Turn the fan ON at 34.0 °C or above, otherwise OFF.", FAN, TEMP)
    a = follows("Turn the fan ON at 34.0 °C or above, otherwise OFF.", ("A3", ">=", 36.0), ("A3", "<=", 32.0))
    found = check_requirement(a, s)
    assert found is not None and found.rule == "hysteresis_band"
    assert "36" in found.reason and "32" in found.reason


def test_one_threshold_with_its_complement_is_not_a_band():
    s = spec("- Drive D5 HIGH when temperature is at or above 90.0 °C; otherwise LOW.", FAN, TEMP)
    a = follows("Drive D5 HIGH when temperature is at or above 90.0 °C; otherwise LOW.", ("A3", ">=", 90.0), ("A3", "<", 90.0))
    assert check_requirement(a, s) is None


def test_a_threshold_written_in_the_other_of_volts_and_millivolts_is_the_specs():
    s = spec("- Light D7 when the probe is above 1.5 V.", LAMP, PinSpec(pin="A0", type="analog_input"))
    a = follows("Light D7 when the probe is above 1.5 V.", ("A0", ">", 1500), ("A0", "<", 1000), pin="D7")
    assert check_requirement(a, s).rule == "hysteresis_band"  # 1000 is nowhere in the spec, 1500 is
    a = follows("Light D7 when the probe is above 1.5 V.", ("A0", ">", 1500), ("A0", "<=", 1500), pin="D7")
    assert check_requirement(a, s) is None


# ------------------------------------------------------------------ rate limit


RATE = "- Output must not change state more than 2 times in any 5000 ms window."


def test_a_toggle_limit_the_spec_states_passes_whatever_the_unit():
    quote = "Output must not change state more than 2 times in any 5000 ms window."
    assert check_requirement(MaxToggles(pin="D5", max_toggles=2, window_ms=5000, spec_quote=quote), spec(RATE, FAN)) is None
    in_seconds = spec("- Output may toggle at most twice in any 5 s.", FAN)
    assert check_requirement(MaxToggles(pin="D5", max_toggles=2, window_ms=5000, spec_quote="Output may toggle at most twice in any 5 s."), in_seconds) is None


def test_a_toggle_limit_for_a_spec_that_never_mentions_toggling_is_marked():
    s = spec("- Light D5 when the temperature is above 30 °C.", FAN, TEMP)
    a = MaxToggles(pin="D5", max_toggles=2, window_ms=5000, spec_quote="Light D5 when the temperature is above 30 °C.", id="a2")
    found = check_requirement(a, s)
    assert found is not None and found.rule == "rate_limit" and "toggling" in found.reason


def test_a_toggle_limit_with_numbers_the_bullet_does_not_give_is_marked():
    quote = "Output must not change state more than 2 times in any 5000 ms window."
    wrong_window = MaxToggles(pin="D5", max_toggles=2, window_ms=1000, spec_quote=quote)
    wrong_count = MaxToggles(pin="D5", max_toggles=5, window_ms=5000, spec_quote=quote)
    assert "1000" in check_requirement(wrong_window, spec(RATE, FAN)).reason
    assert "limit of 5" in check_requirement(wrong_count, spec(RATE, FAN)).reason


def test_a_toggle_bullet_without_numbers_leaves_the_numbers_to_the_model():
    s = spec("- The output must not chatter.", FAN)
    assert check_requirement(MaxToggles(pin="D5", max_toggles=4, window_ms=2000, spec_quote="The output must not chatter."), s) is None


# ------------------------------------------------------------------ debounce


DEBOUNCE = "- Each press toggles the lamp once. Use a 40 ms settle window before accepting a press."


def press(settle, quote="Each press toggles the lamp once.", **kw):
    return TogglePerPress(input_pin="D2", output_pin="D5", spec_quote=quote, id="a1", **({} if settle is None else {"settle_ms": settle}), **kw)


def test_a_debounce_time_that_matches_the_spec_passes():
    s = spec(DEBOUNCE, MODE, FAN)
    assert check_requirement(press(40), s) is None


def test_a_longer_settle_time_is_more_lenient_and_passes():
    assert check_requirement(press(60), spec(DEBOUNCE, MODE, FAN)) is None


def test_a_shorter_settle_time_than_the_spec_states_is_marked():
    found = check_requirement(press(20), spec(DEBOUNCE, MODE, FAN))
    assert found is not None and found.rule == "debounce" and "20 ms" in found.reason and "40 ms" in found.reason


def test_the_settle_time_is_only_compared_when_the_model_chose_it():
    # settle_ms left at its default (50) was not the model's claim, so a shorter spec window cannot contradict it.
    assert check_requirement(press(None), spec("- Each press toggles the lamp once. Settle for 60 ms.", MODE, FAN)) is None


def test_a_spec_with_no_settle_window_never_contradicts_the_settle_time():
    assert check_requirement(press(10), spec("- Each press toggles the lamp once.", MODE, FAN)) is None


def test_a_press_check_for_a_bullet_that_does_not_toggle_is_marked():
    s = spec("- The lamp is lit while D2 is pressed.", MODE, FAN)
    found = check_requirement(press(40, quote="The lamp is lit while D2 is pressed."), s)
    assert found is not None and found.rule == "debounce" and "toggles" in found.reason


# ------------------------------------------------------------------ range bound


RANGE = "Light D7 when the reading is outside -10.0 to 50.0 °C."


def test_half_of_a_two_sided_range_with_a_complement_on_the_far_side_is_marked():
    s = spec("- " + RANGE, LAMP, PinSpec(pin="A0", type="analog_input"))
    a = follows(RANGE, ("A0", "<", -10.0), ("A0", ">=", -10.0), pin="D7")
    found = check_requirement(a, s)
    assert found is not None and found.rule == "range_bound" and "50" in found.reason


def test_one_sided_claims_that_stay_outside_the_range_pass():
    s = spec("- " + RANGE, LAMP, PinSpec(pin="A0", type="analog_input"))
    assert check_requirement(follows(RANGE, ("A0", "<", -10.0), pin="D7"), s) is None
    assert check_requirement(follows(RANGE, ("A0", ">", 50.0), pin="D7"), s) is None


def test_a_range_written_with_a_dash_is_read_too():
    quote = "Drive D7 HIGH when pH is outside 6.50\u20138.50 inclusive; otherwise LOW."
    s = spec("- " + quote, LAMP, PinSpec(pin="A1", type="analog_input"))
    found = check_requirement(follows(quote, ("A1", ">", 8.5), ("A1", "<=", 8.5), pin="D7"), s)
    assert found is not None and found.rule == "range_bound"


def test_a_threshold_that_is_not_a_bound_of_the_range_is_left_alone():
    s = spec("- " + RANGE, LAMP, PinSpec(pin="A0", type="analog_input"))
    assert check_requirement(follows(RANGE, ("A0", ">", 70.0), pin="D7"), s) is None


# ------------------------------------------------------------------ invented converse


FORCE = "While D4 is held LOW, force the fan ON regardless of temperature."


def test_a_forced_state_does_not_demand_the_opposite_state_for_a_released_input():
    s = spec("- " + FORCE, FAN, BOOST)
    a = follows(FORCE, ("D4", "==", 0), ("D4", "==", 1))
    found = check_requirement(a, s)
    assert found is not None and found.rule == "invented_converse" and "D4" in found.reason


def test_the_forced_state_alone_passes():
    assert check_requirement(follows(FORCE, ("D4", "==", 0)), spec("- " + FORCE, FAN, BOOST)) is None


def test_a_bullet_that_says_what_a_release_does_passes():
    quote = "While D2 is pressed, light D7 HIGH; release turns D7 LOW."
    a = follows(quote, ("D2", "==", 0), ("D2", "==", 1), pin="D7")
    assert check_requirement(a, spec("- " + quote, MODE, LAMP)) is None


def test_a_plain_while_held_bullet_is_not_judged_by_the_converse_rule():
    quote = "The lamp is lit while D2 is held."
    a = follows(quote, ("D2", "==", 0), ("D2", "==", 1), pin="D7")
    assert check_requirement(a, spec("- " + quote, MODE, LAMP)) is None


# ------------------------------------------------------------------ a bullet that names two inputs


def test_a_bullet_naming_two_inputs_is_not_judged_for_the_input_it_leaves_out():
    # Tried as a rule and removed: the check below is sloppy, but on the dev runs it was also the only check that
    # caught a real wrong-pin bug, so marking it cost a detection.
    quote = "While D2 is pressed and D4 is released, light D7 HIGH."
    assert check_requirement(follows(quote, ("D2", "==", 0), pin="D7"), spec("- " + quote, MODE, BOOST, LAMP)) is None


# ------------------------------------------------------------------ what is never judged


def test_assertion_types_without_a_rule_are_untouched():
    s = spec("- Print `x` every 1000 ms.", FAN)
    untouched = [
        SerialPeriod(pattern="^x", period_ms=1000, tolerance_ms=50, spec_quote="Print `x` every 1000 ms."),
        TimedPulse(pin="D5", trigger=cond("D2", "==", 0), duration_ms=777, spec_quote="Print `x` every 1000 ms."),
        SafeStateOnFault(fault_when=cond("D2", "==", 0), output_pin="D5", safe_value=1, spec_quote="Print `x` every 1000 ms."),
        Responsive(max_gap_ms=33, spec_quote="Print `x` every 1000 ms."),
        NoCrash(),
    ]
    assert [check_requirement(a, s) for a in untouched] == [None] * 5


def test_an_assertion_without_a_quote_has_no_bullet_to_compare_with():
    s = spec("- Light D5 when the temperature is above 30 °C.", FAN, TEMP)
    assert check_requirement(MaxToggles(pin="D5", max_toggles=20, window_ms=1000), s) is None


def test_the_result_maps_assertion_ids_and_keeps_the_grounded_ones_out():
    s = spec("- Light D5 when the temperature is above 30 °C.\n" + RATE, FAN, TEMP)
    bad = MaxToggles(pin="D5", max_toggles=2, window_ms=5000, spec_quote="Light D5 when the temperature is above 30 °C.", id="a2")
    good = MaxToggles(pin="D5", max_toggles=2, window_ms=5000, spec_quote="Output must not change state more than 2 times in any 5000 ms window.", id="a3")
    out = ungrounded_requirements([bad, good], s)
    assert list(out) == ["a2"] and out["a2"].rule == "rate_limit"


# ------------------------------------------------------------------ helpers


def test_durations_and_counts_read_units_and_number_words():
    assert sorted(durations_ms("no more than 2 times in any 5 s, or 300 ms apart, once per minute")) == [300.0, 5000.0, 60000.0]
    assert sorted(counts("no more than 2 times in any 5 s, or 300 ms apart, once per minute")) == [1.0, 2.0]
    assert counts("at most twice") == [2.0]


def test_the_bullet_is_the_one_sharing_the_quotes_words():
    text = "- Pin map line.\n- Light D7 when the reading is outside -10.0 to 50.0 °C.\n- Print every second."
    assert bullet_of("Light D7 when the reading is outside -10.0 to 50.0", text).startswith("Light D7")


# ------------------------------------------------------------------ the quoted clause owns the numbers


def test_numbers_of_other_clauses_in_the_bullet_do_not_judge_the_limit():
    s = spec("- D9 must not chatter. Heartbeat every 250 ms.", PinSpec(pin="D9", type="digital_output"))
    a = MaxToggles(pin="D9", max_toggles=2, window_ms=1000, spec_quote="D9 must not chatter", id="a1")
    assert check_requirement(a, s) is None


# ------------------------------------------------------------------ the pipeline

import asyncio  # noqa: E402

from app.agent import Pipeline  # noqa: E402
from tests.test_api import settings  # noqa: E402
from tests.test_cross_check import CLEAN_OK, HEARTBEAT_ONLY, RoomLLM, RoomRunner  # noqa: E402
from tests.test_fix_loop import NullBus, NullStore, ORIGINAL  # noqa: E402

TWO_BULLETS = "- D9 must not chatter.\n- Heartbeat every 250 ms."
D9 = PinSpec(pin="D9", type="digital_output")
UNDERSTAND = {
    "assertions": [
        # Quotes the heartbeat bullet but demands a toggle limit the spec only states in the other bullet.
        {"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 1000, "description": "Limit toggles", "spec_quote": "Heartbeat every 250 ms"},
        {"type": "serial_period", "pattern": "^hb$", "period_ms": 250, "tolerance_ms": 50, "description": "Heartbeat", "spec_quote": "Heartbeat every 250 ms"},
    ]
}
CHATTERS_WITH_HEARTBEAT = "void setup() {}\nvoid loop() { heartbeat(); } // CHATTER\n"


class GateLLM(RoomLLM):
    async def json(self, system, user, schema, step):
        return schema.model_validate(UNDERSTAND if step == "understand" else {})


def run_gate(firmware, patches=(), **overrides):
    pipeline = Pipeline("r", settings(max_parallel=2, cross_check=True, **overrides), RoomRunner(), NullStore(), NullBus())
    pipeline.llm = GateLLM(list(patches), [[CLEAN_OK], [CLEAN_OK]])
    status, report = asyncio.run(pipeline.run_break(firmware, DeviceSpec(pins=[D9], behaviour=TWO_BULLETS)))
    return status, report, pipeline.llm


def test_an_ungrounded_check_is_marked_reported_and_counted_but_never_a_bug():
    status, report, llm = run_gate(ORIGINAL, [CHATTERS_WITH_HEARTBEAT])
    ungrounded = report["ungrounded"]
    assert [u["assertion_id"] for u in ungrounded] == ["a1"]
    u = ungrounded[0]
    assert u["rule"] == "rate_limit" and "toggling" in u["reason"] and u["failing_scenarios"] > 0 and u["your_firmware"]
    assert u["spec_quote"] == "Heartbeat every 250 ms" and u["assertion_type"] == "max_toggles"
    assert report["score"]["ungrounded_requirements"] == 1
    assert [a["id"] for a in report["assertions"] if a.get("ungrounded")] == ["a1"]
    assert [b["assertion_type"] for b in report["bugs"]] == ["serial_period"]
    assert any("Left out a1" in w for w in report["warnings"])


def test_an_ungrounded_check_is_neither_a_fix_target_nor_a_verification_blocker():
    # The patch fixes the heartbeat and still chatters. The chatter check is ungrounded, so the fix stands.
    status, report, llm = run_gate(ORIGINAL, [HEARTBEAT_ONLY])
    assert status == "fixed" and report["fix"]["all_passing"] is True
    assert "Limit toggles" not in llm.fix_prompts[0]
    assert all(r["assertion_id"] != "a1" for it in report["iterations"][1:] for r in it.get("regressions") or [])


def test_a_run_whose_only_failure_is_ungrounded_is_clean_and_asks_no_clean_room():
    status, report, llm = run_gate(CHATTERS_WITH_HEARTBEAT)
    assert status == "clean" and report["bugs"] == []
    assert [u["assertion_id"] for u in report["ungrounded"]] == ["a1"]
    assert report["cross_check"]["status"] == "not_needed"
    assert llm.room_prompts == {1: [], 2: []}
    assert llm.fix_prompts == []


def test_a_grounded_run_has_an_empty_ungrounded_list_and_a_zero_count():
    grounded = {"assertions": [{**UNDERSTAND["assertions"][0], "spec_quote": "D9 must not chatter"}, UNDERSTAND["assertions"][1]]}

    class Grounded(GateLLM):
        async def json(self, system, user, schema, step):
            return schema.model_validate(grounded if step == "understand" else {})

    pipeline = Pipeline("r", settings(max_parallel=2, cross_check=True), RoomRunner(), NullStore(), NullBus())
    pipeline.llm = Grounded([], [[CLEAN_OK], [CLEAN_OK]])
    status, report = asyncio.run(pipeline.run_break(CLEAN_OK, DeviceSpec(pins=[D9], behaviour=TWO_BULLETS)))
    assert status == "clean" and report["ungrounded"] == [] and report["score"]["ungrounded_requirements"] == 0
    assert not any(a.get("ungrounded") for a in report["assertions"])
