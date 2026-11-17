"""Clock fast-forward in the attack plan and the stimulus search, and the per-run search switch."""
import asyncio

from app import prompts
from app.agent import Pipeline, normalize_scenarios
from app.clock import HOURS_IN_MS, MAX_START_MS, WRAPS, clamp_start, start_before_wrap, uses_elapsed_time
from app.models import DeviceSpec, PinSpec, Scenario
from app.scenario_lib import builtin_scenarios
from app.search import UNSUPPORTED, fingerprint, make_variants
from tests.test_api import settings
from tests.test_cross_check import CLEAN_OK, RoomLLM, RoomRunner
from tests.test_fix_loop import NullBus, NullStore, ORIGINAL
from tests.test_search import ASSERTIONS, SPEC, scenarios

# ------------------------------------------------------------------ when the clock matters


def test_code_that_reads_the_clock_has_elapsed_time_logic():
    assert uses_elapsed_time("void loop() { if (millis() - last > 5) {} }", "")
    assert uses_elapsed_time("unsigned long t = micros ();", "")


def test_a_spec_about_time_passing_has_elapsed_time_logic_even_when_the_code_only_waits():
    assert uses_elapsed_time("void loop() { delay(100); }", "Run the pump for 400 ms every 5 s.")
    assert uses_elapsed_time("void loop() { delay(100); }", "Count the uptime.")


def test_a_sketch_and_spec_with_no_notion_of_time_do_not():
    assert not uses_elapsed_time("void loop() { digitalWrite(9, digitalRead(2)); }", "D9 follows D2.")
    assert not uses_elapsed_time("void loop() { delay(100); }", "D9 follows D2.")


def test_a_start_a_fraction_of_the_run_before_a_wrap_puts_the_wrap_inside_the_run():
    for _, wrap in WRAPS:
        start = start_before_wrap(wrap, 8000, 0.4)
        assert 0 <= start < wrap < start + 8000
    assert start_before_wrap(2**32, 8000, 0.4) == 2**32 - 3200


def test_a_model_given_start_is_forced_into_the_counter_range():
    assert clamp_start(-5) == 0
    assert clamp_start(10**15) == MAX_START_MS
    assert clamp_start("4294965296") == 4294965296
    assert clamp_start(3.9e6) == 3_900_000
    assert clamp_start(None) == 0 and clamp_start("soon") == 0 and clamp_start(float("inf")) == 0


# ------------------------------------------------------------------ the attack prompt


def test_the_attack_prompt_offers_start_millis_only_when_the_clock_matters():
    spec = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour="x")
    plain = prompts.attack_user("void loop() {}", spec, [], ["Nominal ramp"])
    offered = prompts.attack_user("void loop() { millis(); }", spec, [], ["Nominal ramp"], clock=True)
    assert "start_millis" not in plain and "CLOCK FAST-FORWARD" not in plain
    assert "start_millis" in offered and "4294967296" in offered and "196608" in offered and "32768000" in offered


def test_scenarios_from_the_model_keep_a_start_and_a_bad_one_does_not_drop_the_scenario():
    spec = DeviceSpec(pins=[PinSpec(pin="D2", type="digital_input", active_low=True)], behaviour="x")
    raw = [
        {"name": "wrap", "duration_ms": 6000, "start_millis": 4294963296, "digital": [{"pin": "D2", "initial": 1, "events": [{"t_ms": 1000, "value": 0}]}]},
        {"name": "negative", "duration_ms": 6000, "start_millis": -40, "digital": [{"pin": "D2", "initial": 1, "events": []}]},
        {"name": "huge", "duration_ms": 6000, "start_millis": 99999999999999, "digital": [{"pin": "D2", "initial": 1, "events": []}]},
        {"name": "text", "duration_ms": 6000, "start_millis": "a while", "digital": [{"pin": "D2", "initial": 1, "events": []}]},
        {"name": "none", "duration_ms": 6000, "digital": [{"pin": "D2", "initial": 1, "events": []}]},
    ]
    kept, warnings = normalize_scenarios(raw, spec, [])
    assert [s.start_millis for s in kept] == [4294963296, 0, MAX_START_MS, 0, 0]
    assert not warnings


class RecordingLLM(RoomLLM):
    """Scripted model that keeps the user message of every JSON step."""

    def __init__(self):
        super().__init__([], [[CLEAN_OK], [CLEAN_OK]])
        self.asked: dict[str, str] = {}

    async def json(self, system, user, schema, step):
        self.asked[step] = user
        return await super().json(system, user, schema, step)


def attack_prompt(firmware, behaviour):
    pipeline = Pipeline("r", settings(max_parallel=2, cross_check=False), RoomRunner(), NullStore(), NullBus())
    pipeline.llm = RecordingLLM()
    asyncio.run(pipeline.run_break(firmware, DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour=behaviour)))
    return pipeline.llm.asked["attack"]


def test_the_pipeline_offers_the_clock_for_code_that_reads_millis():
    assert "CLOCK FAST-FORWARD" in attack_prompt(CLEAN_OK + "unsigned long t = millis();\n", "D9 must not chatter. Heartbeat every 250 ms.")


def test_the_pipeline_keeps_the_offer_out_when_nothing_depends_on_time():
    assert "CLOCK FAST-FORWARD" not in attack_prompt(CLEAN_OK, "D9 must not chatter.")


# ------------------------------------------------------------------ the search


def uptime_variants(count=60, seed=1337):
    kinds: dict[str, str] = {}
    made = make_variants(scenarios(), SPEC, ASSERTIONS, count, seed, kinds, uptime=True)
    return [v for v in made if kinds[v.id] == "uptime"]


def test_the_search_varies_the_clock_only_when_asked_to():
    kinds: dict[str, str] = {}
    off = make_variants(scenarios(), SPEC, ASSERTIONS, 60, 1337, kinds)
    assert "uptime" not in kinds.values() and all(v.start_millis == 0 for v in off)
    assert uptime_variants()


def test_an_uptime_variant_changes_nothing_but_the_clock_and_a_wrap_falls_inside_the_run():
    base = {s.id: s for s in scenarios()}
    wraps = [w for _, w in WRAPS]
    for v in uptime_variants():
        parent = base[v.parent]
        assert v.start_millis != parent.start_millis and v.variant.startswith("clock started at")
        assert v.model_dump(exclude={"id", "name", "hypothesis", "source", "parent", "variant", "start_millis"}) == parent.model_dump(exclude={"id", "name", "hypothesis", "source", "parent", "variant", "start_millis"})
        hit = any(v.start_millis < w < v.start_millis + v.duration_ms for w in wraps)
        assert hit or v.start_millis == HOURS_IN_MS
        Scenario.model_validate(v.model_dump())


def test_the_clock_variants_are_the_same_for_the_same_seed():
    a = [fingerprint(v) for v in uptime_variants()]
    assert a == [fingerprint(v) for v in uptime_variants()] and len(set(a)) == len(a)


def test_the_search_notes_what_it_does_not_cover():
    assert "elapsed-time logic" in UNSUPPORTED[0]


# ------------------------------------------------------------------ search on per run, with its gates


def run_with(search_variants, firmware, behaviour="D9 must not chatter. Heartbeat every 250 ms."):
    pipeline = Pipeline("r", settings(max_parallel=4, cross_check=True, search_variants=search_variants, search_budget_s=60), RoomRunner(), NullStore(), NullBus())
    pipeline.llm = RecordingLLM()
    spec = DeviceSpec(pins=[PinSpec(pin="D9", type="digital_output")], behaviour=behaviour)
    status, report = asyncio.run(pipeline.run_break(firmware, spec))
    return report


def test_search_is_off_by_default_and_on_when_the_run_asks_for_variants():
    assert settings().search_variants == 0
    off = run_with(0, CLEAN_OK)
    on = run_with(6, CLEAN_OK + "unsigned long t = millis();\n")
    assert off["search"]["enabled"] is False
    assert on["search"]["enabled"] is True and on["search"]["variants_planned"] == 6


def test_a_search_run_carries_its_three_gates_and_tries_the_clock_for_code_that_reads_it():
    on = run_with(40, CLEAN_OK + "unsigned long t = millis();\n")
    assert set(on["search"]["gates"]) == {"a", "b", "c"}
    assert on["search"]["unsupported"] == UNSUPPORTED
    assert on["search"]["mutations"].get("uptime", 0) >= 1


def test_a_search_run_leaves_the_clock_alone_when_nothing_depends_on_time():
    on = run_with(40, CLEAN_OK, behaviour="D9 must not chatter.")
    assert on["search"]["enabled"] is True and "uptime" not in on["search"]["mutations"]
