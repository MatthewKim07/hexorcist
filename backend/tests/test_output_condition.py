"""A condition may name an output pin: the level then comes from what the firmware drove, not from an injected input.

Regression for the benchmark v2 class C bug: digital_input_levels read only dir == 'in' events, so an
output pin used as a condition read as constant 0 and output_follows demanded the wrong level.
"""
from app.assertions import condition_intervals, evaluate_all
from app.models import Condition, DeviceSpec, DigitalInput, OutputFollows, PinSpec, Scenario

SPEC = DeviceSpec(
    pins=[
        PinSpec(pin="D2", role="trigger", type="digital_input", active_low=True),
        PinSpec(pin="D8", role="solenoid", type="digital_output"),
        PinSpec(pin="D11", role="armed lamp", type="digital_output"),
        PinSpec(pin="D5", role="dimmer", type="pwm_output"),
    ]
)
SCENARIO = Scenario(id="s", name="s", duration_ms=5000, digital=[DigitalInput(pin="D2", initial=1)])


def trace(events, pwm=None):
    return {
        "exit_reason": "completed",
        "sim_ms": 5000.0,
        "input_trace": [],
        "pin_events": sorted(({"t_ms": t, "pin": p, "value": v, "dir": d} for t, p, v, d in events), key=lambda e: e["t_ms"]),
        "pwm_events": [{"t_ms": t, "pin": p, "duty": d} for t, p, d in (pwm or [])],
        "serial_log": [],
    }


# D8 pulses HIGH from 1000 to 3000 ms. D11 is the armed lamp: HIGH when idle, LOW during the pulse.
LAMP_RULE = OutputFollows(
    id="a1",
    pin="D11",
    high_when=Condition(pin="D8", op="==", value=0),
    low_when=Condition(pin="D8", op="==", value=1),
    within_ms=120,
)


def lamp_trace(lamp_events):
    events = [(0, "D11", 1, "out"), (1000, "D8", 1, "out"), (3000, "D8", 0, "out")]
    return trace(events + [(t, "D11", v, "out") for t, v in lamp_events])


def judge(rule, tr):
    return next(r for r in evaluate_all([rule], tr, SCENARIO, SPEC) if r.assertion_id == rule.id)


def test_a_correct_lamp_passes_when_the_condition_is_an_output_pin():
    r = judge(LAMP_RULE, lamp_trace([(1000, 0), (3000, 1)]))
    assert r.status == "pass", r.evidence


def test_a_lamp_that_ignores_the_output_condition_fails():
    r = judge(LAMP_RULE, lamp_trace([]))
    assert r.status == "fail"
    assert "D11" in r.evidence


def test_condition_intervals_follow_the_output_level():
    tr = lamp_trace([])
    cond = Condition(pin="D8", op="==", value=1)
    assert condition_intervals(cond, tr, SCENARIO, SPEC, 5000.0) == [(1000, 3000)]
    idle = Condition(pin="D8", op="==", value=0)
    assert condition_intervals(idle, tr, SCENARIO, SPEC, 5000.0) == [(0.0, 1000), (3000, 5000.0)]


def test_a_pwm_output_counts_as_high_while_its_duty_is_above_zero():
    tr = trace([], pwm=[(500, "D5", 128), (2500, "D5", 0)])
    cond = Condition(pin="D5", op="==", value=1)
    assert condition_intervals(cond, tr, SCENARIO, SPEC, 5000.0) == [(500, 2500)]


def test_an_input_pin_is_still_read_from_the_injected_events():
    tr = trace([(1200, "D2", 0, "in"), (1800, "D2", 1, "in")])
    pressed = Condition(pin="D2", op="==", value=0)
    assert condition_intervals(pressed, tr, SCENARIO, SPEC, 5000.0) == [(1200, 1800)]


def test_output_events_on_an_input_pin_do_not_leak_into_the_condition():
    # Firmware briefly driving an input pin must not change what the scenario injected.
    tr = trace([(300, "D2", 0, "out"), (1200, "D2", 0, "in"), (1800, "D2", 1, "in")])
    pressed = Condition(pin="D2", op="==", value=0)
    assert condition_intervals(pressed, tr, SCENARIO, SPEC, 5000.0) == [(1200, 1800)]
