"""Search acceptance gates: the spec's stated ranges (c) and the clean-room check on the same variant (b)."""
from app.models import AnalogInput, AnalogPoint, AssertionResult, DeviceSpec, DigitalEvent, DigitalInput, PinSpec, Scenario, Spike
from app.search_gates import passes_in_every_room, press_lengths, stated_limits, out_of_range

PINS = [
    PinSpec(pin="A1", role="Sump level", type="analog_input", scale="10 mV/cm"),
    PinSpec(pin="D4", role="Silence", type="digital_input", active_low=True),
    PinSpec(pin="D7", role="Pump", type="digital_output"),
]


def spec(text):
    return DeviceSpec(pins=PINS, behaviour=text)


def analog(levels, noise=0.0, spikes=()):
    return AnalogInput(pin="A1", segments=[AnalogPoint(t_ms=1000.0 * i, mv=mv) for i, mv in enumerate(levels)], noise_mv=noise, spikes=[Spike(t_ms=t, mv=mv) for t, mv in spikes])


def presses(*lengths, bounce=(0, 0)):
    events = []
    t = 500.0
    for n in lengths:
        events += [DigitalEvent(t_ms=t, value=0, bounce_ms=bounce[0], bounce_count=bounce[1]), DigitalEvent(t_ms=t + n, value=1)]
        t += n + 400
    return DigitalInput(pin="D4", initial=1, events=events)


def scenario(sid="s", a=None, d=None):
    return Scenario(id=sid, name=sid, duration_ms=8000, analog=[a] if a else [], digital=[d] if d else [])


# ------------------------------------------------------------------ (c) stated limits


def test_a_stated_sensor_range_limits_the_levels_a_variant_may_introduce():
    s = spec("The sump level sensor range is 0 to 100 cm. Start the pump at 45 cm.")
    limits = stated_limits(s, [])
    assert limits.analog_mv["A1"] == (0.0, 1000.0)
    assert "A1 range" in limits.stated


def test_without_a_stated_range_the_adc_range_is_the_limit():
    assert stated_limits(spec("Start the pump at 45 cm."), []).analog_mv["A1"] == (0.0, 5000.0)


def test_a_threshold_band_is_not_mistaken_for_the_sensor_range():
    # No range word in the sentence, so "between 30 and 45 cm" is the pump's band, not what the sensor can read.
    assert stated_limits(spec("Run the pump between 30 and 45 cm."), []).analog_mv["A1"] == (0.0, 5000.0)


def test_a_level_beyond_the_stated_range_is_out_of_range_and_one_inside_is_not():
    limits = stated_limits(spec("The sensor measures 0 to 100 cm."), [])
    parent = scenario("p", analog([300, 400]))
    assert out_of_range(scenario("v", analog([300, 1400])), parent, limits) == ["A1 goes to 1400 mV, outside the 0 to 1000 mV range"]
    assert out_of_range(scenario("v", analog([330, 430])), parent, limits) == []


def test_a_level_the_parent_scenario_already_used_is_not_checked_against_the_range():
    limits = stated_limits(spec("The sensor measures 0 to 100 cm."), [])
    parent = scenario("p", analog([300, 4750], spikes=[(500, 4750)]))
    assert out_of_range(scenario("v", analog([300, 4750], spikes=[(500, 4750)])), parent, limits) == []


def test_a_stated_minimum_press_sets_the_shortest_press_a_variant_may_use():
    limits = stated_limits(spec("A press of at least 50 ms counts as a press."), [scenario("p", d=presses(120))])
    assert limits.min_press_ms == 50.0 and "minimum press" in limits.stated
    parent = scenario("p", d=presses(120))
    assert out_of_range(scenario("v", d=presses(30)), parent, limits)[0].startswith("a press of 30 ms is shorter than the 50 ms")
    assert out_of_range(scenario("v", d=presses(60)), parent, limits) == []


def test_without_a_stated_press_length_a_variant_may_not_press_shorter_than_the_run_already_did():
    limits = stated_limits(spec("Silence mutes the pump."), [scenario("p", d=presses(80, 200))])
    assert limits.min_press_ms == 80.0 and "minimum press" not in limits.stated
    parent = scenario("p", d=presses(80, 200))
    assert out_of_range(scenario("v", d=presses(30)), parent, limits)
    assert out_of_range(scenario("v", d=presses(80)), parent, limits) == []
    assert out_of_range(scenario("v", d=presses(800)), parent, limits) == []


def test_a_press_with_nothing_to_compare_it_with_is_refused():
    limits = stated_limits(spec("Silence mutes the pump."), [scenario("p", analog([300]))])
    assert limits.min_press_ms is None
    assert out_of_range(scenario("v", d=presses(300)), scenario("p", analog([300])), limits) == ["a press has no stated or observed length to compare with"]


def test_bounce_longer_than_the_spec_states_is_out_of_range():
    limits = stated_limits(spec("The button contacts bounce for up to 20 ms."), [scenario("p", d=presses(100, bounce=(5, 6)))])
    assert limits.max_bounce_ms == 20.0 and limits.max_bounce_count == 6 and "maximum bounce" in limits.stated
    parent = scenario("p", d=presses(100, bounce=(5, 6)))
    assert out_of_range(scenario("v", d=presses(100, bounce=(40, 4))), parent, limits)[0].startswith("contact bounce of 40 ms is longer than the 20 ms")
    assert out_of_range(scenario("v", d=presses(100, bounce=(10, 4))), parent, limits) == []
    assert "24 bounces are more than the 6" in out_of_range(scenario("v", d=presses(100, bounce=(10, 24))), parent, limits)[0]


def test_bounce_with_none_stated_or_used_is_refused():
    limits = stated_limits(spec("Silence mutes the pump."), [scenario("p", d=presses(100))])
    assert out_of_range(scenario("v", d=presses(100, bounce=(5, 2))), scenario("p", d=presses(100)), limits)


def test_noise_beyond_what_is_stated_or_already_used_is_out_of_range():
    stated = stated_limits(spec("The sensor reading carries noise of up to 15 mV."), [])
    parent = scenario("p", analog([300], noise=5))
    assert stated.max_noise_mv == 15.0
    assert out_of_range(scenario("v", analog([300], noise=30)), parent, stated)
    assert out_of_range(scenario("v", analog([300], noise=12)), parent, stated) == []
    quiet = stated_limits(spec("Silence mutes the pump."), [scenario("p", analog([300], noise=12))])
    assert quiet.max_noise_mv == 12.0 and out_of_range(scenario("v", analog([300], noise=20)), parent, quiet)


def test_whatever_the_parent_scenario_already_did_stays_allowed():
    limits = stated_limits(spec("The button contacts bounce for up to 10 ms. Noise of up to 5 mV."), [])
    parent = scenario("p", analog([300], noise=40), d=presses(100, bounce=(30, 8)))
    variant = scenario("v", analog([310], noise=40), d=presses(100, bounce=(30, 8)))
    assert out_of_range(variant, parent, limits) == []


def test_the_limits_are_reported_for_the_user():
    limits = stated_limits(spec("The sensor range is 0 to 100 cm. Bounce for up to 20 ms."), [scenario("p", d=presses(100, bounce=(5, 6)), a=analog([300], noise=4))])
    report = limits.report()
    assert report["analog_mv"] == {"A1": [0.0, 1000.0]} and report["max_bounce_ms"] == 20.0 and report["stated_in_spec"] == ["A1 range", "maximum bounce"]


def test_press_lengths_pair_each_press_with_its_release():
    assert press_lengths(scenario("s", d=presses(80, 200))) == [80.0, 200.0]


# ------------------------------------------------------------------ (b) both clean rooms, same variant


def res(status, evidence="D7 toggled 9 times"):
    return AssertionResult(assertion_id="a1", scenario_id="v", type="max_toggles", status=status, evidence=evidence)


def room(status, sid="v"):
    return {sid: [res(status)]}


def test_a_check_that_passes_in_both_rooms_in_this_variant_is_accepted():
    assert passes_in_every_room("a1", "v", [room("pass"), room("pass")]) == (True, "")


def test_a_room_that_fails_the_check_in_the_variant_rejects_it():
    ok, why = passes_in_every_room("a1", "v", [room("pass"), room("fail")])
    assert not ok and why.startswith("clean room 2 fails it too")
    assert passes_in_every_room("a1", "v", [room("fail"), room("pass")])[1].startswith("clean room 1")


def test_a_room_that_never_exercised_the_check_or_never_ran_the_variant_rejects_it():
    assert "did not exercise" in passes_in_every_room("a1", "v", [room("pass"), room("not_exercised")])[1]
    assert "did not run this scenario" in passes_in_every_room("a1", "v", [room("pass"), room("pass", sid="other")])[1]


def test_both_rooms_are_required():
    ok, why = passes_in_every_room("a1", "v", [room("pass")])
    assert not ok and "only 1 clean room built" in why
    assert not passes_in_every_room("a1", "v", [])[0]


def test_passing_in_another_variant_does_not_count():
    # Both rooms passed some other variant of the same check, but this one is the finding.
    rooms = [{"v": [res("fail")], "w": [res("pass")]}, {"v": [res("pass")], "w": [res("pass")]}]
    assert not passes_in_every_room("a1", "v", rooms)[0]
    assert passes_in_every_room("a1", "w", rooms)[0]
