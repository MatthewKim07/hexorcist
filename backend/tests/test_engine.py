"""Fast engine tests on synthetic traces. No Docker, no LLM."""
from app.assertions import evaluate_all, output_timeline
from app.guard import screen_request
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


def test_guard_flags_containment_preset_and_passes_the_others():
    for preset in PRESETS:
        verdict = screen_request(preset["firmware"], preset["behaviour"])
        assert verdict["allowed"] == (preset["id"] != "containment"), (preset["id"], verdict)


def test_guard_allows_normal_library_includes():
    assert screen_request('#include <Servo.h>\n#include "config.h"\n', "Move a servo")["allowed"]
