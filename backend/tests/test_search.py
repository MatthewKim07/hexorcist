"""Stimulus search: seeded variants, shrinking, and the pipeline with a scripted sandbox."""
import asyncio

from app.agent import Pipeline
from app.llm import LLMCall
from app.models import AnalogInput, AnalogPoint, Condition, DeviceSpec, DigitalEvent, DigitalInput, FloatingWindow, NoCrash, OutputFollows, PinSpec, Scenario, Spike
from app.sandbox import CompileResult, ContainmentRecord, RunResult
from app.scenario_lib import builtin_scenarios
from app.search import complexity, fingerprint, make_variants, removals, reproduction_point, shrink, simplifications
from tests.test_api import settings
from tests.test_cross_check import CLEAN_OK, RoomLLM
from tests.test_fix_loop import NullBus, NullStore, fake_trace

SPEC = DeviceSpec(
    pins=[
        PinSpec(pin="A0", role="temp", type="analog_input", scale="10 mV/°C"),
        PinSpec(pin="D2", role="button", type="digital_input", active_low=True),
        PinSpec(pin="D9", role="fan", type="digital_output"),
    ],
    behaviour="The fan must not change state more than 2 times in any 1000 ms window.",
)
ASSERTIONS = [
    OutputFollows(id="a1", pin="D9", high_when=Condition(pin="A0", op=">=", value=30), low_when=Condition(pin="A0", op="<=", value=27)),
    NoCrash(id="a2"),
]


def scenarios():
    return builtin_scenarios(SPEC, ASSERTIONS)


# ------------------------------------------------------------------ variants


def test_the_same_seed_makes_the_same_variants():
    a = make_variants(scenarios(), SPEC, ASSERTIONS, 30, 1337)
    b = make_variants(scenarios(), SPEC, ASSERTIONS, 30, 1337)
    assert [fingerprint(v) for v in a] == [fingerprint(v) for v in b]
    assert [v.name for v in a] == [v.name for v in b]


def test_another_seed_makes_other_variants():
    a = make_variants(scenarios(), SPEC, ASSERTIONS, 30, 1)
    b = make_variants(scenarios(), SPEC, ASSERTIONS, 30, 2)
    assert [fingerprint(v) for v in a] != [fingerprint(v) for v in b]


def test_the_count_is_honoured_and_zero_means_none():
    assert len(make_variants(scenarios(), SPEC, ASSERTIONS, 30, 7)) == 30
    assert len(make_variants(scenarios(), SPEC, ASSERTIONS, 5, 7)) == 5
    assert make_variants(scenarios(), SPEC, ASSERTIONS, 0, 7) == []


def test_variants_are_distinct_valid_and_traceable_to_a_parent():
    base = scenarios()
    ids = {s.id for s in base}
    variants = make_variants(base, SPEC, ASSERTIONS, 30, 1337)
    assert len({fingerprint(v) for v in variants}) == len(variants)
    assert not {fingerprint(v) for v in variants} & {fingerprint(s) for s in base}
    for v in variants:
        assert v.source == "search" and v.parent in ids and v.variant
        Scenario.model_validate(v.model_dump())  # still a legal scenario
        assert 0 < v.duration_ms <= 15000


def test_every_kind_of_change_is_used_across_a_run():
    kinds: dict[str, str] = {}
    make_variants(scenarios(), SPEC, ASSERTIONS, 60, 1337, kinds)
    assert set(kinds.values()) == {"threshold", "timing", "bounce", "noise", "press", "order"}


def test_scenarios_on_a_rail_or_on_noise_are_not_searched():
    parents = {v.parent for v in make_variants(scenarios(), SPEC, ASSERTIONS, 60, 1337)}
    assert not any(p.startswith(("builtin-floating-", "builtin-extremes-")) for p in parents)


def only(kind, count=40):
    kinds: dict[str, str] = {}
    made = make_variants(scenarios(), SPEC, ASSERTIONS, count, 1337, kinds)
    return [(v, next(s for s in scenarios() if s.id == v.parent)) for v in made if kinds[v.id] == kind]


def test_a_press_change_only_changes_press_lengths():
    for variant, parent in only("press"):
        d = next(x for x in variant.digital if x.events and x.pin == variant.variant.split()[0])
        p = next(x for x in parent.digital if x.pin == d.pin)
        assert len(d.events) == len(p.events)
        lengths = {round(b.t_ms - a.t_ms) for a, b in zip(d.events[::2], d.events[1::2])}
        assert len(lengths) == 1


def test_timing_shifts_keep_the_events_in_order_and_inside_the_run():
    for variant, _ in only("timing"):
        for a in variant.analog:
            times = [p.t_ms for p in a.segments]
            assert times == sorted(times) and times[-1] < variant.duration_ms
        for d in variant.digital:
            times = [e.t_ms for e in d.events]
            assert times == sorted(times) and all(0 <= t < variant.duration_ms for t in times)


def test_bounce_changes_only_bounce():
    for variant, parent in only("bounce"):
        for d, p in zip(variant.digital, parent.digital):
            assert [e.t_ms for e in d.events] == [e.t_ms for e in p.events]


# ------------------------------------------------------------------ shrinking


def rich():
    return Scenario(
        id="v",
        name="rich",
        duration_ms=8000,
        analog=[AnalogInput(pin="A0", segments=[AnalogPoint(t_ms=0, mv=200), AnalogPoint(t_ms=2000, mv=300), AnalogPoint(t_ms=6000, mv=400)], noise_mv=20, spikes=[Spike(t_ms=1000, width_ms=10, mv=4000)])],
        digital=[DigitalInput(pin="D2", initial=1, events=[DigitalEvent(t_ms=t, value=v, bounce_ms=8, bounce_count=4) for t, v in ((1000, 0), (1200, 1), (3000, 0), (3200, 1), (5000, 0), (5200, 1))])],
        floating=[FloatingWindow(pin="A0", from_ms=500, to_ms=900)],
    )


def run_shrink(needs, first_end=2000.0, max_runs=18):
    """Shrink with a check that breaks whenever `needs(scenario)` holds. Returns the result and the runs it took."""
    calls = []

    async def still_fails(cands):
        calls.append(len(cands))
        return [needs(c) for c in cands]

    return asyncio.run(shrink(rich(), first_end, still_fails, max_runs=max_runs)), calls


def test_shrinking_removes_everything_the_failure_does_not_need():
    # Breaks only on the press at 3000 ms.
    result, _ = run_shrink(lambda s: any(abs(e.t_ms - 3000) < 1 for d in s.digital for e in d.events), first_end=3300.0)
    s = result.scenario
    # A press and its release go together: dropping only the release would change what the press means.
    assert [e.t_ms for d in s.digital for e in d.events] == [3000, 3200]
    assert s.duration_ms < 8000 and not s.floating and not s.analog[0].spikes and s.analog[0].noise_mv == 0
    assert result.events_after < result.events_before and result.duration_after_ms < result.duration_before_ms


def test_shrinking_keeps_what_the_failure_needs():
    result, _ = run_shrink(lambda s: s.analog[0].noise_mv >= 20 and bool(s.analog[0].spikes))
    s = result.scenario
    assert s.analog[0].noise_mv == 20 and len(s.analog[0].spikes) == 1


def test_shrinking_never_returns_a_scenario_that_stopped_failing():
    needs = lambda s: any(abs(e.t_ms - 5000) < 1 for d in s.digital for e in d.events)  # noqa: E731
    result, _ = run_shrink(needs)
    assert needs(result.scenario)


def test_shrinking_stays_inside_its_run_budget():
    result, calls = run_shrink(lambda s: True, max_runs=6)
    assert sum(calls) <= 6 and result.runs == sum(calls)


def test_a_scenario_that_cannot_shrink_comes_back_unchanged():
    result, _ = run_shrink(lambda s: s is not None and complexity(s) == complexity(rich()))
    assert complexity(result.scenario) == complexity(rich())


def test_shrinking_stops_at_the_deadline():
    async def still_fails(cands):
        return [True] * len(cands)

    result = asyncio.run(shrink(rich(), 2000.0, still_fails, deadline=0.0))
    assert result.runs == 0 and result.scenario.duration_ms == 8000


def test_cutting_the_run_short_keeps_a_tail_after_the_first_violation():
    cuts = [s for s, note in simplifications(rich(), 2000.0) if s.duration_ms < 8000]
    assert cuts and all(s.duration_ms >= 2500 for s in cuts)


def test_removals_never_leave_a_scenario_with_no_input():
    for s, _ in removals(rich()):
        assert s.analog or s.digital or s.floating


# ------------------------------------------------------------------ the pipeline


class NoisySandbox:
    """Firmware marked NOISY chatters once an input has 20 mV of noise or more. Nothing else misbehaves."""

    def __init__(self):
        self.compiled: list[str] = []
        self.ran: list[dict] = []

    def compile(self, sketch, label="compile"):
        self.compiled.append(sketch)
        ok = "NOCOMPILE" not in sketch
        return CompileResult(ok=ok, log="" if ok else "error: boom", elf=sketch.encode() if ok else None, record=ContainmentRecord(kind="compile", label=label))

    def run(self, elf, scenario, label, no_sim_cap=False):
        self.ran.append(scenario)
        noisy = any(a["noise_mv"] >= 20 for a in scenario["analog"])
        code = elf.decode()
        # NOISY chatters on any noisy run. SHORT only on a noisy run shorter than 8 s, which is what shrinking makes.
        chatters = noisy and ("NOISY" in code or ("SHORT" in code and scenario["duration_ms"] < 8000))
        trace = fake_trace(code + (" CHATTER" if chatters else ""))
        trace["sim_ms"] = scenario["duration_ms"]
        return RunResult(trace=trace, record=ContainmentRecord(kind="emulate", label=label, duration_ms=100.0))


UPLOADED = "void setup() {}\nvoid loop() { heartbeat(); } // NOISY\n"
FIXED = "void setup() {}\nvoid loop() { heartbeat(); } // calm\n"
SPEC2 = DeviceSpec(
    pins=[PinSpec(pin="A0", role="temp", type="analog_input", scale="10 mV/°C"), PinSpec(pin="D9", role="fan", type="digital_output")],
    behaviour="D9 must not chatter. Heartbeat every 250 ms. The sensor output carries noise of up to 40 mV.",
)
SPEC_QUIET = DeviceSpec(pins=SPEC2.pins, behaviour="D9 must not chatter. Heartbeat every 250 ms.")
UNDERSTAND = {
    "assertions": [
        {"type": "max_toggles", "pin": "D9", "max_toggles": 2, "window_ms": 1000, "description": "No chatter", "spec_quote": "D9 must not chatter"},
    ]
}


class SearchLLM(RoomLLM):
    async def json(self, system, user, schema, step):
        return schema.model_validate(UNDERSTAND if step == "understand" else {})


def run(patches=(FIXED,), rooms=((CLEAN_OK,), (CLEAN_OK,)), **overrides):
    sandbox = NoisySandbox()
    config = {"max_parallel": 4, "cross_check": True, "search_variants": 40, "search_budget_s": 60, **overrides}
    pipeline = Pipeline("r", settings(**config), sandbox, NullStore(), NullBus())
    pipeline.llm = SearchLLM(list(patches), [list(r) for r in rooms])
    status, report = asyncio.run(pipeline.run_break(UPLOADED, SPEC2))
    return status, report, sandbox, pipeline


def test_the_search_finds_a_failure_the_planned_scenarios_miss():
    status, report, _, _ = run()
    search = report["search"]
    assert search["variants_planned"] == 40 and search["variants_run"] == 40
    assert search["failing_variants"] >= 1 and search["new_failing_checks"] == 1
    assert [b["assertion_type"] for b in report["bugs"]] == ["max_toggles"]
    bug = report["bugs"][0]
    assert bug["found_by_search"] is True
    repro = bug["reproduction"]
    assert repro["events_after"] <= repro["events_before"] and repro["duration_after_ms"] <= repro["duration_before_ms"]
    assert repro["scenario_id"] in {s["id"] for s in report["scenarios"]}
    assert status == "fixed"


def test_a_search_finding_is_a_scenario_in_the_report_and_is_verified_again():
    _, report, sandbox, _ = run()
    found = [s for s in report["scenarios"] if s["source"] == "search"]
    assert len(found) == 1 and found[0]["name"].startswith("Found by search")
    assert found[0]["parent"] and found[0]["variant"]
    # The patch run covers every scenario, the finding included.
    assert found[0]["id"] in report["matrix"]["0"] and found[0]["id"] in report["matrix"][str(report["fix"]["iteration"])]
    # The shrunk scenario really lost its noise only if it did not need it: here the noise is what breaks it.
    scenario = next(s for s in report["scenarios"] if s["id"] == found[0]["id"])
    assert any(a["noise_mv"] >= 20 for a in scenario["analog"])


def test_the_search_is_repeatable():
    first = run()[1]["search"]
    second = run()[1]["search"]
    assert [k["name"] for k in first["kept"]] == [k["name"] for k in second["kept"]]


def test_a_check_a_clean_implementation_also_fails_is_not_a_search_finding():
    status, report, _, _ = run(patches=(), rooms=((UPLOADED,), (UPLOADED,)))
    assert report["bugs"] == []
    assert report["search"]["discarded_by_clean_room"] == ["a1"]
    assert report["search"]["gates"]["b"] >= 1 and report["search"]["kept"] == []
    assert status == "clean"


def test_extra_sandbox_time_is_recorded():
    _, report, _, _ = run()
    search = report["search"]
    assert search["sandbox_runs"] >= 40 and search["sandbox_s"] > 0 and search["wall_s"] >= 0
    assert search["unsupported"] and "fast-forward" in search["unsupported"][0]


def test_the_search_can_be_switched_off():
    status, report, sandbox, _ = run(search_variants=0, patches=())
    assert report["search"]["enabled"] is False
    assert status == "clean"
    assert not any(a["noise_mv"] >= 20 for s in sandbox.ran for a in s["analog"])


def test_a_search_that_runs_out_of_time_skips_variants_instead_of_hanging():
    _, report, _, _ = run(patches=(), search_budget_s=0)
    assert report["search"]["variants_over_budget"] == 40 and report["search"]["variants_run"] == 0


# ------------------------------------------------------------------ shrinking, round two


def oscillation():
    points = [AnalogPoint(t_ms=0, mv=250)] + [AnalogPoint(t_ms=500 + 150 * k, mv=300 + (12 if k % 2 else -12)) for k in range(48)]
    return Scenario(id="o", name="osc", duration_ms=8000, analog=[AnalogInput(pin="A0", segments=points, noise_mv=20)])


def test_a_long_sequence_shrinks_in_halves_so_few_rounds_reach_its_core():
    async def still_fails(cands):
        return [c.analog[0].noise_mv >= 20 for c in cands]  # the noise breaks it, the oscillation is incidental

    result = asyncio.run(shrink(oscillation(), 1500.0, still_fails))
    assert len(result.scenario.analog[0].segments) <= 10
    assert result.scenario.analog[0].noise_mv == 20
    assert result.runs <= 18


def test_the_reproduction_point_uses_the_checks_window_not_a_violation_that_runs_to_the_end():
    from app.models import MaxToggles, Violation

    a = MaxToggles(id="m", pin="D9", max_toggles=2, window_ms=5000)
    chatter_to_the_end = [Violation(t_start=1200, t_end=7900)]
    assert reproduction_point(a, chatter_to_the_end, 8000) == 6200
    short = [Violation(t_start=1200, t_end=1500)]
    assert reproduction_point(a, short, 8000) == 1500
    assert reproduction_point(a, [], 8000) == 8000


# ------------------------------------------------------------------ the acceptance gates


def gate_run(spec=None, **kw):
    """Like run(), but returns the pipeline's report together with the rooms' recorded results."""
    sandbox = kw.get("sandbox") or NoisySandbox()
    config = {"max_parallel": 4, "cross_check": True, "search_variants": 40, "search_budget_s": 60, **kw.pop("config", {})}
    pipeline = Pipeline("r", settings(**config), sandbox, NullStore(), NullBus())
    pipeline.llm = SearchLLM(list(kw.get("patches", (FIXED,))), [list(r) for r in kw.get("rooms", ((CLEAN_OK,), (CLEAN_OK,)))])
    status, report = asyncio.run(pipeline.run_break(UPLOADED, spec or SPEC2))
    return status, report, sandbox, pipeline


def test_search_is_off_unless_asked_for():
    status, report, sandbox, _ = gate_run(config={"search_variants": 0}, patches=())
    assert report["search"]["enabled"] is False and status == "clean"
    assert not any(a["noise_mv"] >= 20 for s in sandbox.ran for a in s["analog"])


class NotReproducible(NoisySandbox):
    """The uploaded firmware chatters during the search and its shrinking, but not when the kept scenario is run again."""

    def run(self, elf, scenario, label, no_sim_cap=False):
        result = super().run(elf, scenario, label, no_sim_cap)
        if label.startswith("search finding") and "NOISY" in elf.decode():
            result.trace = fake_trace(elf.decode())
            result.trace["sim_ms"] = scenario["duration_ms"]
        return result


def test_gate_a_a_kept_finding_fails_again_on_the_uploaded_firmware():
    status, report, _, _ = gate_run()
    kept = report["search"]["kept"]
    assert len(kept) == 1 and report["search"]["gates"]["a"] == 0
    # The kept scenario is a real result of iteration 0 and the check fails in it.
    scenario_id = kept[0]["scenario_id"]
    failing = report["bugs"][0]["failing_scenarios"]
    assert report["bugs"][0]["found_by_search"] is True and [f["id"] for f in failing] == [scenario_id]
    assert "toggled" in failing[0]["evidence"]
    assert status == "fixed"


def test_gate_a_a_finding_that_does_not_fail_again_is_dropped():
    status, report, _, _ = gate_run(patches=(), sandbox=NotReproducible())
    search = report["search"]
    assert search["kept"] == [] and search["gates"]["a"] == 1 and report["bugs"] == [] and status == "clean"
    assert any(r["gate"] == "a" for r in search["rejected"])
    assert any("did not reproduce" in w for w in report["warnings"])


def test_gate_b_both_clean_rooms_must_pass_the_same_variant():
    _, report, _, pipeline = gate_run()
    kept = report["search"]["kept"][0]
    # The variant that was kept, and the shrunk scenario that is finally reported, both ran on both rooms.
    for room in pipeline.rooms:
        assert kept["scenario_id"] in room.results
        if kept["events_after"] != kept["events_before"] or kept["duration_after_ms"] != kept["duration_before_ms"]:
            assert f"{kept['scenario_id']}-shrunk" in room.results
        assert all(r.status == "pass" for r in room.results[kept["scenario_id"]] if r.assertion_id == kept["assertion_id"])


def test_gate_b_one_room_failing_the_variant_rejects_the_finding():
    status, report, _, _ = gate_run(patches=(), rooms=((UPLOADED,), (CLEAN_OK,)))
    search = report["search"]
    assert search["kept"] == [] and report["bugs"] == [] and status == "clean"
    assert search["gates"]["b"] >= 1 and search["discarded_by_clean_room"] == ["a1"]
    assert all(r["gate"] == "b" and "clean room 1 fails it too" in r["reason"] for r in search["rejected"] if r["gate"] == "b")
    # The other room failing instead is rejected just the same.
    assert gate_run(patches=(), rooms=((CLEAN_OK,), (UPLOADED,)))[1]["search"]["kept"] == []


def test_gate_b_needs_both_rooms_to_have_built():
    status, report, _, _ = gate_run(patches=(), rooms=((CLEAN_OK,), ("NOCOMPILE one", "NOCOMPILE two")))
    search = report["search"]
    assert search["kept"] == [] and status == "clean" and search["gates"]["b"] >= 1
    assert any("only 1 clean room built" in r["reason"] for r in search["rejected"])


def test_gate_b_without_any_clean_room_nothing_is_kept():
    status, report, _, _ = gate_run(patches=(), config={"cross_check": False})
    search = report["search"]
    assert search["kept"] == [] and status == "clean"
    assert any("only 0 clean rooms built" in r["reason"] for r in search["rejected"])


def test_gate_b_applies_again_to_the_shrunk_scenario_and_falls_back_to_the_unshrunk_variant():
    # SHORT rooms pass the full 8 s variant but chatter on the 1.5 s scenario shrinking makes, so the shrunk one is refused.
    short = "void setup() {}\nvoid loop() { heartbeat(); } // SHORT\n"
    status, report, _, _ = gate_run(rooms=((short,), (short,)))
    search = report["search"]
    kept = search["kept"][0]
    assert kept["duration_after_ms"] == kept["duration_before_ms"] == 8000
    assert any(r["gate"] == "b" and r["reason"].startswith("after shrinking") for r in search["rejected"])
    assert kept["steps"] == ["kept unshrunk: the smaller scenario failed a gate"]
    assert status == "fixed"


def test_gate_c_a_variant_outside_the_spec_ranges_is_not_a_finding():
    # The spec states no noise, and the run's own scenarios use at most 12 mV, so the 20 and 30 mV variants are out of range.
    status, report, _, _ = gate_run(spec=SPEC_QUIET, patches=())
    search = report["search"]
    assert search["kept"] == [] and report["bugs"] == [] and status == "clean"
    assert search["gates"]["c"] >= 1 and search["gates"]["b"] == 0
    assert all("noise" in r["reason"] for r in search["rejected"])
    assert search["limits"]["max_noise_mv"] == 12.0 and search["limits"]["stated_in_spec"] == []


def test_gate_c_the_same_variant_is_a_finding_once_the_spec_states_the_noise():
    status, report, _, _ = gate_run()
    assert report["search"]["limits"]["max_noise_mv"] == 40.0 and report["search"]["limits"]["stated_in_spec"] == ["maximum noise"]
    assert report["search"]["gates"]["c"] == 0 and len(report["search"]["kept"]) == 1


def test_gate_c_rejected_variants_never_reach_the_clean_rooms():
    _, _, _, pipeline = gate_run(spec=SPEC_QUIET, patches=())
    assert all(not any(k.startswith("search-") for k in room.results) for room in pipeline.rooms or [])
