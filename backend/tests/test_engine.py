"""Fast engine tests on synthetic traces. No Docker, no LLM."""
from app.agent import normalize_scenarios
from app.assertions import evaluate_all, output_timeline
from app.guard import screen_request
from app.llm import extract_code
from app.models import (
    Condition,
    DeviceSpec,
    DigitalInput,
    MaxToggles,
    NoCrash,
    OutputFollows,
    PinSpec,
    SafeStateOnFault,
    Scenario,
    SerialValueMatches,
    TogglePerPress,
    normalize_pin,
)
from app.presets import PRESETS

SPEC = DeviceSpec(
    pins=[
        PinSpec(pin="A0", role="temp", type="analog_input", scale="10 mV/°C"),
        PinSpec(pin="D9", role="fan", type="digital_output"),
        PinSpec(pin="D2", role="button", type="digital_input", active_low=True),
    ]
)
SCENARIO = Scenario(id="s", name="s", duration_ms=1000)
BUTTON_SCENARIO = Scenario(id="b", name="b", duration_ms=1000, digital=[DigitalInput(pin="D2", initial=1)])


def trace(mv=None, out=None, serial=None, inp=None, exit_reason="completed"):
    points = [{"t_ms": float(t), "pin": "A0", "mv": v, "min_mv": v, "max_mv": v} for t, v in (mv or [])]
    pins = [{"t_ms": t, "pin": "D9", "value": v, "dir": "out"} for t, v in (out or [])]
    pins += [{"t_ms": t, "pin": "D2", "value": v, "dir": "in"} for t, v in (inp or [])]
    return {
        "exit_reason": exit_reason,
        "sim_ms": 1000.0,
        "input_trace": points,
        "pin_events": sorted(pins, key=lambda e: e["t_ms"]),
        "pwm_events": [],
        "serial_log": [{"t_ms": t, "text": x} for t, x in (serial or [])],
    }


def one(assertion, tr, assertions=None):
    assertion.id = assertion.id or "a"
    all_a = assertions or [assertion]
    return next(r for r in evaluate_all(all_a, tr, SCENARIO, SPEC) if r.assertion_id == assertion.id)


def test_scale_parsing_and_conversion():
    assert PinSpec(pin="A0", type="analog_input", scale="10 mV/°C + 500 mV").parsed_scale() == (10.0, 500.0, "°C")
    assert SPEC.to_physical("A0", 300) == 30


def test_normalize_pin():
    assert normalize_pin("9") == "D9"
    assert normalize_pin("a0") == "A0"


def test_max_toggles_reports_worst_window():
    a = MaxToggles(id="m", pin="D9", max_toggles=2, window_ms=100)
    r = one(a, trace(out=[(10, 1), (20, 0), (30, 1), (40, 0)]))
    assert r.status == "fail"
    assert r.metrics["worst_window_toggles"] == 4


def test_max_toggles_excuses_toggles_the_input_demanded():
    follows = OutputFollows(id="f", pin="D9", high_when=Condition(pin="A0", op=">=", value=30), low_when=Condition(pin="A0", op="<=", value=27), within_ms=50)
    limit = MaxToggles(id="m", pin="D9", max_toggles=1, window_ms=1000)
    mv = [(t, 400 if (t // 200) % 2 else 100) for t in range(0, 1000, 10)]
    out = [(t, 1 if (t // 200) % 2 else 0) for t in range(200, 1000, 200)]
    r = one(limit, trace(mv=mv, out=out), [follows, limit])
    assert r.status == "pass", r.evidence


THERMOSTAT_RULES = [
    OutputFollows(id="f", pin="D9", high_when=Condition(pin="A0", op=">=", value=30), low_when=Condition(pin="A0", op="<=", value=27), within_ms=500),
    MaxToggles(id="m", pin="D9", max_toggles=2, window_ms=5000),
    SafeStateOnFault(id="s", fault_when=Condition(pin="A0", op="<", value=2), output_pin="D9", safe_value=1, within_ms=100),
]


def test_max_toggles_excuses_the_flip_into_a_fail_safe():
    # A brief 35 C reading, a fall through 27 C, then a disconnected sensor. Every switch is required.
    mv = [(t, 350 if t < 100 else (200 if t < 400 else 0)) for t in range(0, 1000, 10)]
    r = one(THERMOSTAT_RULES[1], trace(mv=mv, out=[(50, 1), (200, 0), (420, 1)]), THERMOSTAT_RULES)
    assert r.status == "pass", r.evidence


def test_same_toggles_with_no_fault_are_not_excused():
    mv = [(t, 350 if t < 100 else 200) for t in range(0, 1000, 10)]
    r = one(THERMOSTAT_RULES[1], trace(mv=mv, out=[(50, 1), (200, 0), (420, 1)]), THERMOSTAT_RULES)
    assert r.status == "fail"


def test_chatter_during_a_fault_is_not_excused():
    mv = [(t, 0) for t in range(0, 1000, 10)]
    r = one(THERMOSTAT_RULES[1], trace(mv=mv, out=[(50, 1), (200, 0), (420, 1), (500, 0), (600, 1)]), THERMOSTAT_RULES)
    assert r.status == "fail"


FOLLOW_AND_LIMIT = [
    OutputFollows(id="f", pin="D9", high_when=Condition(pin="A0", op=">=", value=30), low_when=Condition(pin="A0", op="<=", value=27), within_ms=100),
    MaxToggles(id="m", pin="D9", max_toggles=1, window_ms=1000),
]


def swing(hold_ms):
    """Alternate between 35 C and 20 C, starting cold. Returns the input and an output that follows it."""
    mv = [(t, 350 if (t // hold_ms) % 2 else 200) for t in range(0, 1000, 5)]
    out = [(t + 5, 1 if (t // hold_ms) % 2 else 0) for t in range(hold_ms, 1000, hold_ms)]
    return mv, out


def test_following_holds_near_the_deadline_is_a_real_change():
    mv, out = swing(80)
    r = one(FOLLOW_AND_LIMIT[1], trace(mv=mv, out=out), FOLLOW_AND_LIMIT)
    assert r.status == "pass", r.evidence


def test_following_holds_well_short_of_the_deadline_is_short_cycling():
    mv, out = swing(50)
    r = one(FOLLOW_AND_LIMIT[1], trace(mv=mv, out=out), FOLLOW_AND_LIMIT)
    assert r.status == "fail"


def test_brownout_inside_the_adc_margin_still_excuses_the_fail_safe():
    # 31 C, down through 27 C, a real fault at 1.5 C (inside the 10 mV margin of 2 C), then recovery to 28 C.
    rules = [
        OutputFollows(id="f", pin="D9", high_when=Condition(pin="A0", op=">=", value=30), low_when=Condition(pin="A0", op="<=", value=27), within_ms=100),
        MaxToggles(id="m", pin="D9", max_toggles=2, window_ms=1000),
        SafeStateOnFault(id="s", fault_when=Condition(pin="A0", op="<", value=2), output_pin="D9", safe_value=1, within_ms=100),
    ]
    mv = [(t, 310 if t < 200 else (200 if t < 400 else (15 if t < 700 else 200))) for t in range(0, 1000, 5)]
    r = one(rules[1], trace(mv=mv, out=[(50, 1), (250, 0), (450, 1), (750, 0)]), rules)
    assert r.status == "pass", r.evidence
    assert r.metrics["total_toggles"] == 4


def falling_ramp():
    """35 C falling to 0 C at 1 mV every 2 ms, so 2 C (20 mV) is crossed at 660 ms."""
    return [(t, max(0.0, 350 - t / 2)) for t in range(0, 1000, 2)]


def test_fail_safe_entered_inside_the_adc_margin_is_not_a_follow_failure():
    # The firmware sees 2 C at 24 mV, which is correct, before the reading is clearly below 2 C.
    rules = [OutputFollows(id="f", pin="D9", low_when=Condition(pin="A0", op="<=", value=27), within_ms=50), THERMOSTAT_RULES[2]]
    r = one(rules[0], trace(mv=falling_ramp(), out=[(10, 1), (150, 0), (652, 1)]), rules)
    assert r.status == "pass", r.evidence


def test_fail_safe_entered_well_above_the_threshold_is_still_a_follow_failure():
    # 50 mV is 5 C: well outside the margin, so normal control still applies and the fan must be off.
    rules = [OutputFollows(id="f", pin="D9", low_when=Condition(pin="A0", op="<=", value=27), within_ms=50), THERMOSTAT_RULES[2]]
    r = one(rules[0], trace(mv=falling_ramp(), out=[(10, 1), (150, 0), (600, 1)]), rules)
    assert r.status == "fail"
    assert r.metrics["intervals"] == 1


def test_fail_safe_is_still_demanded_only_once_the_fault_is_clear():
    # Never going safe is a failure, so widening the excuse did not widen the demand.
    r = one(THERMOSTAT_RULES[2], trace(mv=[(t, 0) for t in range(0, 1000, 10)]), THERMOSTAT_RULES)
    assert r.status == "fail"


GLITCH_RULES = [THERMOSTAT_RULES[1], SafeStateOnFault(id="h", fault_when=Condition(pin="A0", op=">", value=120), output_pin="D9", safe_value=1, within_ms=500)]


def spike_train():
    """20 C with 30 ms spikes to 475 mV (47.5 C) is not a fault here, so spikes go to 4750 mV."""
    return [(t, 4750 if 100 <= t % 300 < 130 else 200) for t in range(0, 1000, 10)]


def test_switching_on_a_glitch_too_short_to_require_the_fail_safe_still_fails():
    out = [(100, 1), (200, 0), (400, 1), (500, 0), (700, 1), (800, 0)]
    r = one(GLITCH_RULES[0], trace(mv=spike_train(), out=out), GLITCH_RULES)
    assert r.status == "fail"
    assert r.metrics["glitch_toggles"] == 6
    assert "reacting to noise" in r.evidence


def test_firmware_that_ignores_the_glitch_passes():
    assert one(GLITCH_RULES[0], trace(mv=spike_train(), out=[]), GLITCH_RULES).status == "pass"


def test_chatter_with_no_glitch_does_not_blame_a_glitch():
    mv = [(t, 200) for t in range(0, 1000, 10)]
    r = one(GLITCH_RULES[0], trace(mv=mv, out=[(100, 1), (200, 0), (400, 1), (500, 0)]), GLITCH_RULES)
    assert r.status == "fail"
    assert r.metrics["glitch_toggles"] == 0
    assert "reacting to noise" not in r.evidence


SIREN = OutputFollows(id="e", pin="D9", high_when=Condition(pin="D2", op="==", value=0), within_ms=100, mode="edge")


def siren_result(rule, inp, out):
    rules = [SIREN] if rule is SIREN else [SIREN, rule]
    return next(r for r in evaluate_all(rules, trace(inp=inp, out=out), BUTTON_SCENARIO, SPEC) if r.assertion_id == rule.id)


def test_release_bounce_is_not_an_edge_trigger():
    press_then_bouncy_release = [(100, 0), (500, 1), (501, 0), (502, 1), (503, 0), (504, 1)]
    r = siren_result(SIREN, press_then_bouncy_release, [(120, 1), (300, 0)])
    assert r.status == "pass", r.evidence
    assert r.metrics == {} and "1 required" in r.evidence


def test_a_real_short_press_must_still_trigger():
    r = siren_result(SIREN, [(100, 0), (150, 1), (600, 0), (650, 1)], [(120, 1), (300, 0)])
    assert r.status == "fail"
    assert r.metrics == {"missed": 1, "triggers": 2}


def test_max_toggles_excuses_a_timed_output_retriggered_by_a_press():
    limit = MaxToggles(id="m", pin="D9", max_toggles=2, window_ms=5000)
    r = siren_result(limit, [(100, 0), (150, 1), (600, 0), (650, 1)], [(120, 1), (300, 0), (620, 1)])
    assert r.status == "pass", r.evidence


def test_max_toggles_excuses_a_reaction_to_the_first_bounce_edge():
    # The output rises on the first edge at 100, before the press settles at 106.
    limit = MaxToggles(id="m", pin="D9", max_toggles=2, window_ms=5000)
    press = [(100, 0), (102, 1), (104, 0), (500, 1), (600, 0), (602, 1), (604, 0), (900, 1)]
    r = siren_result(limit, press, [(100, 1), (400, 0), (600, 1)])
    assert r.status == "pass", r.evidence


def test_max_toggles_still_catches_chatter_on_one_press():
    limit = MaxToggles(id="m", pin="D9", max_toggles=2, window_ms=5000)
    r = siren_result(limit, [(100, 0), (500, 1)], [(120, 1), (130, 0), (140, 1), (150, 0)])
    assert r.status == "fail"


def test_output_follows_fails_when_output_stays_low():
    a = OutputFollows(id="f", pin="D9", high_when=Condition(pin="A0", op=">=", value=30), within_ms=50)
    r = one(a, trace(mv=[(t, 400) for t in range(0, 1000, 10)]))
    assert r.status == "fail"


def test_adc_rounding_at_exact_threshold_is_not_a_failure():
    a = OutputFollows(id="f", pin="D9", high_when=Condition(pin="A0", op=">=", value=30), within_ms=50)
    assert one(a, trace(mv=[(t, 300) for t in range(0, 1000, 10)])).status == "not_exercised"


def test_fault_overrides_normal_control():
    follows = OutputFollows(id="f", pin="D9", low_when=Condition(pin="A0", op="<=", value=27), within_ms=50)
    fault = SafeStateOnFault(id="s", fault_when=Condition(pin="A0", op="<", value=2), output_pin="D9", safe_value=1, within_ms=50)
    tr = trace(mv=[(t, 0) for t in range(0, 1000, 10)], out=[(10, 1)])
    assert one(fault, tr, [follows, fault]).status == "pass"
    assert one(follows, tr, [follows, fault]).status != "fail"


def press_result(inp, out):
    a = TogglePerPress(id="t", input_pin="D2", output_pin="D9", settle_ms=20, within_ms=100)
    return next(r for r in evaluate_all([a], trace(inp=inp, out=out), BUTTON_SCENARIO, SPEC) if r.assertion_id == "t")


def test_toggle_per_press_groups_bounce():
    bounce = [(100, 0), (102, 1), (104, 0)]
    r = press_result(bounce, [(110, 1), (112, 0), (114, 1)])
    assert r.status == "fail"
    assert r.metrics["toggles_per_press"] == [3]
    assert press_result(bounce, [(130, 1)]).status == "pass"


def test_glitch_during_a_hold_is_not_a_new_press():
    hold = [(100, 0), (500, 1), (502, 0), (800, 1)]
    r = press_result(hold, [(130, 1)])
    assert r.status == "pass", r.evidence
    assert r.metrics["presses"] == 1


def test_toggling_on_a_glitch_during_a_hold_fails():
    hold = [(100, 0), (500, 1), (502, 0), (800, 1)]
    r = press_result(hold, [(130, 1), (503, 0)])
    assert r.status == "fail"
    assert r.metrics["spurious_toggles"] == 1


def test_toggling_on_release_fails():
    r = press_result([(100, 0), (500, 1)], [(130, 1), (510, 0)])
    assert r.status == "fail"
    assert r.metrics["toggles_per_press"] == [1]
    assert r.metrics["spurious_toggles"] == 1


def test_missing_a_press_still_fails():
    r = press_result([(100, 0), (300, 1), (500, 0), (700, 1)], [(130, 1)])
    assert r.status == "fail"
    assert r.metrics["toggles_per_press"] == [1, 0]


# Press, a clean 15 ms open gap (more than half of the 20 ms settle time), then press again.
DOUBLE_PRESS = [(100, 0), (150, 1), (165, 0), (500, 1)]


def test_a_real_gap_may_be_read_as_one_press():
    assert press_result(DOUBLE_PRESS, [(125, 1)]).status == "pass"


def test_a_real_gap_may_be_read_as_two_presses():
    r = press_result(DOUBLE_PRESS, [(125, 1), (190, 0)])
    assert r.status == "pass", r.evidence
    assert press_result(DOUBLE_PRESS, [(125, 1), (260, 0)]).status == "pass"


def test_a_real_gap_does_not_excuse_more_toggles_than_it_explains():
    assert press_result(DOUBLE_PRESS, [(125, 1), (130, 0), (135, 1)]).status == "fail"


def test_a_real_gap_still_needs_a_toggle():
    assert press_result(DOUBLE_PRESS, []).status == "fail"


def test_bounce_blips_are_not_real_gaps():
    # Open for 8 ms at a time, and each is under half of the 20 ms settle time.
    bounce = [(100, 0), (150, 1), (158, 0), (170, 1), (178, 0), (500, 1)]
    r = press_result(bounce, [(125, 1), (215, 0)])
    assert r.status == "fail"
    assert r.metrics["spurious_toggles"] == 1


def test_a_real_gap_inside_one_bounce_group_may_be_two_presses():
    # The shape a real model scenario produced: every edge is within settle time of the last,
    # but the contact stayed open for 15 ms in the middle.
    burst = [(100, 0), (105, 1), (108, 0), (120, 1), (135, 0), (140, 1), (143, 0), (400, 1)]
    assert press_result(burst, [(125, 1)]).status == "pass"
    r = press_result(burst, [(125, 1), (200, 0)])
    assert r.status == "pass", r.evidence
    assert press_result(burst, [(125, 1), (240, 0)]).status == "pass"
    assert press_result(burst, [(125, 1), (130, 0), (135, 1)]).status == "fail"


def test_toggle_set_at_boot_is_not_spurious():
    assert press_result([(100, 0), (500, 1)], [(5, 1), (130, 0)]).status == "pass"


def test_serial_value_matches_detects_wrong_unit():
    a = SerialValueMatches(id="v", pattern=r"T=(\d+)", input_pin="A0", tolerance=1)
    mv = [(t, 250) for t in range(0, 1000, 10)]
    assert one(a, trace(mv=mv, serial=[(500, "T=25")])).status == "pass"
    assert one(a, trace(mv=mv, serial=[(500, "T=77")])).status == "fail"


def test_no_crash():
    a = NoCrash(id="n")
    assert one(a, trace()).status == "pass"
    assert one(a, trace(exit_reason="sleep_deadlock")).status == "fail"


def test_pwm_counts_as_high_then_returns_to_gpio():
    tr = trace(out=[])
    tr["pwm_events"] = [{"t_ms": 10.0, "pin": "D9", "duty": 128}, {"t_ms": 20.0, "pin": "D9", "duty": -1}]
    timeline = output_timeline(tr, "D9")
    assert timeline.level_at(15) == 1
    assert timeline.level_at(25) == 0


def test_extract_code_prefers_the_last_whole_sketch():
    old = "void setup() {}\nvoid loop() { /* a long, long, long, long comment */ }"
    new = "void setup() {}\nvoid loop() { fixed(); }"
    assert extract_code(f"Before:\n```cpp\n{old}\n```\nAfter:\n```cpp\n{new}\n```") == new + "\n"
    assert extract_code(f"```cpp\n{new}\n```\nThe key line:\n```cpp\nfixed();\n```") == new + "\n"
    assert extract_code("no code here") is None


def test_llm_scenario_button_idles_at_its_rest_level_unless_stated():
    spec = DeviceSpec(pins=[PinSpec(pin="D2", type="digital_input", active_low=True), PinSpec(pin="D9", type="digital_output")])
    raw = [
        {"name": "no initial", "digital": [{"pin": "D2", "events": [{"t_ms": 100, "value": 0}]}]},
        {"name": "held at boot", "digital": [{"pin": "D2", "initial": 0, "events": [{"t_ms": 100, "value": 1}]}]},
    ]
    kept, warnings = normalize_scenarios(raw, spec, [])
    assert not warnings
    assert [s.digital[0].initial for s in kept] == [1, 0]


def test_guard_flags_containment_preset_and_passes_the_others():
    for preset in PRESETS:
        verdict = screen_request(preset["firmware"], preset["behaviour"])
        assert verdict["allowed"] == (preset["id"] != "containment"), (preset["id"], verdict)


def test_guard_allows_normal_library_includes():
    assert screen_request('#include <Servo.h>\n#include "config.h"\n', "Move a servo")["allowed"]
