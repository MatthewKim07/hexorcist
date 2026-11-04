"""Deterministic assertion evaluation against emulator traces. No LLM in here.

A trace is the JSON hexharness writes. Every verdict and every evidence string
is computed from that trace, so the model can never talk a failure into a pass.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from typing import Optional

from .models import (
    AssertionResult,
    Condition,
    DeviceSpec,
    MaxToggles,
    NoCrash,
    OutputFollows,
    Responsive,
    SafeStateOnFault,
    Scenario,
    SerialPeriod,
    SerialValueMatches,
    TogglePerPress,
    Violation,
)

MAX_VIOLATIONS = 40
# A 10-bit ADC at 5 V cannot resolve better than 4.9 mV. A reading within two steps of a
# threshold is ambiguous, so correct firmware is never failed for rounding.
ADC_MARGIN_MV = 10.0
# An output that changes this soon after a brief glitch ended is treated as reacting to that glitch.
GLITCH_REACTION_MS = 250.0
# A hold this much of the way to a deadline is a real input change, not noise.
REAL_CHANGE_FRACTION = 0.75


def _fmt_ms(t: float) -> str:
    return f"{t / 1000:.2f} s" if t >= 1000 else f"{t:.0f} ms"


@dataclass
class OutputTimeline:
    """Effective level of one output pin over time, combining GPIO and PWM."""

    times: list[float] = field(default_factory=list)
    levels: list[int] = field(default_factory=list)

    def level_at(self, t: float) -> int:
        i = bisect.bisect_right(self.times, t) - 1
        return self.levels[i] if i >= 0 else 0

    def toggles(self) -> list[float]:
        return list(self.times)


def output_timeline(trace: dict, pin: str) -> OutputTimeline:
    events: list[tuple[float, str, int]] = []
    for e in trace.get("pin_events", []):
        if e["pin"] == pin and e.get("dir") == "out":
            events.append((e["t_ms"], "gpio", e["value"]))
    for e in trace.get("pwm_events", []):
        if e["pin"] == pin:
            events.append((e["t_ms"], "pwm", e["duty"]))
    events.sort(key=lambda x: x[0])

    timeline = OutputTimeline()
    gpio = 0
    duty = -1  # -1: compare output disconnected, GPIO decides the level
    level = 0
    for t, kind, value in events:
        if kind == "gpio":
            gpio = value
        else:
            duty = value
        new_level = (1 if duty > 0 else 0) if duty >= 0 else gpio
        if new_level != level:
            timeline.times.append(t)
            timeline.levels.append(new_level)
            level = new_level
    return timeline


@dataclass
class InputSeries:
    """An input's value over time, as (t_ms, min, last, max) in millivolts."""

    pin: str
    times: list[float]
    last: list[float]
    low: list[float]
    high: list[float]


def analog_series(trace: dict, pin: str) -> Optional[InputSeries]:
    points = [p for p in trace.get("input_trace", []) if p["pin"] == pin]
    if not points:
        return None
    return InputSeries(
        pin=pin,
        times=[p["t_ms"] for p in points],
        last=[p["mv"] for p in points],
        low=[p["min_mv"] for p in points],
        high=[p["max_mv"] for p in points],
    )


def digital_input_levels(trace: dict, scenario: Scenario, pin: str) -> tuple[int, list[tuple[float, int]]]:
    initial = 0
    for d in scenario.digital:
        if d.pin == pin:
            initial = d.initial
    events: list[tuple[float, int]] = []
    level = initial
    for e in trace.get("pin_events", []):
        if e["pin"] == pin and e.get("dir") == "in" and e["value"] != level:
            events.append((e["t_ms"], e["value"]))
            level = e["value"]
    return initial, events


def condition_intervals(
    cond: Condition, trace: dict, scenario: Scenario, spec: DeviceSpec, end_ms: float, may_hold: bool = False
) -> list[tuple[float, float]]:
    """Maximal intervals during which the condition holds on the injected input.

    Readings within the ADC margin of a threshold are ambiguous. By default the condition only
    counts once it clearly holds, which is what to use when demanding behaviour from firmware.
    With may_hold it counts as soon as firmware could fairly see it, which is what to use when
    excusing behaviour, because firmware may legitimately act anywhere inside the margin.
    """
    pin_spec = spec.pin(cond.pin)
    series = analog_series(trace, cond.pin) if (pin_spec is None or pin_spec.type == "analog_input") else None
    intervals: list[tuple[float, float]] = []

    if series is not None:
        start: Optional[float] = None
        margin = {">": -ADC_MARGIN_MV, ">=": -ADC_MARGIN_MV, "<": ADC_MARGIN_MV, "<=": ADC_MARGIN_MV}.get(cond.op, 0.0)
        if may_hold:
            margin = -margin
        for t, mv in zip(series.times, series.last):
            holds = cond.holds(spec.to_physical(cond.pin, mv + margin))
            if holds and start is None:
                start = t
            elif not holds and start is not None:
                intervals.append((start, t))
                start = None
        if start is not None:
            intervals.append((start, end_ms))
        return intervals

    initial, events = digital_input_levels(trace, scenario, cond.pin)
    level = initial
    start = 0.0 if cond.holds(level) else None
    for t, value in events:
        level = value
        holds = cond.holds(level)
        if holds and start is None:
            start = t
        elif not holds and start is not None:
            intervals.append((start, t))
            start = None
    if start is not None:
        intervals.append((start, end_ms))
    return intervals


def _subtract(interval: tuple[float, float], holes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Remove holes from an interval, returning the pieces that remain."""
    pieces = [interval]
    for hs, he in holes:
        next_pieces: list[tuple[float, float]] = []
        for s, e in pieces:
            if he <= s or hs >= e:
                next_pieces.append((s, e))
                continue
            if hs > s:
                next_pieces.append((s, hs))
            if he < e:
                next_pieces.append((he, e))
        pieces = next_pieces
    return pieces


def _floating_windows(scenario: Scenario, pins: set[str], end_ms: float) -> list[tuple[float, float]]:
    return [(w.from_ms, min(w.to_ms, end_ms)) for w in scenario.floating if w.pin in pins]


def _suspended(output_pin: str, cond_pins: set[str], assertions: list, trace: dict, scenario: Scenario, spec: DeviceSpec, end_ms: float) -> list[tuple[float, float]]:
    """When normal control rules do not apply to an output.

    A declared fault overrides normal control ("off below 27 C" does not apply to a
    disconnected sensor reading 0 C), and an open input carries no meaningful value,
    so it can only be judged by a safe_state_on_fault that names it.
    """
    holes = _floating_windows(scenario, cond_pins, end_ms)
    for other in assertions:
        if isinstance(other, SafeStateOnFault) and other.output_pin == output_pin and other.fault_when is not None:
            holes.extend(condition_intervals(other.fault_when, trace, scenario, spec, end_ms, may_hold=True))
    return holes


def _time_at_level(timeline: OutputTimeline, start: float, end: float, wanted: int) -> list[tuple[float, float]]:
    """Sub-intervals of [start, end] where the output is NOT at the wanted level."""
    if end <= start:
        return []
    bad: list[tuple[float, float]] = []
    cursor = start
    level = timeline.level_at(start)
    i = bisect.bisect_right(timeline.times, start)
    while i < len(timeline.times) and timeline.times[i] < end:
        t = timeline.times[i]
        if level != wanted:
            bad.append((cursor, t))
        cursor = t
        level = timeline.levels[i]
        i += 1
    if level != wanted:
        bad.append((cursor, end))
    return bad


def _edge_triggers(a: OutputFollows, trace: dict, scenario: Scenario, spec: DeviceSpec, holes: list[tuple[float, float]], end_ms: float) -> list[float]:
    """Start times of real triggers for an edge-mode assertion."""
    triggers: list[float] = []
    last = -1e12
    if a.high_when is None:
        return triggers
    for s, e in condition_intervals(a.high_when, trace, scenario, spec, end_ms):
        if e - s < a.min_trigger_ms or not _subtract((s, s + 0.001), holes):
            continue
        if s + a.within_ms > end_ms or s < last + a.within_ms:
            continue
        last = s
        triggers.append(s)
    return triggers


def _demanded_flips(pin: str, assertions: list, trace: dict, scenario: Scenario, spec: DeviceSpec, timeline: OutputTimeline, end_ms: float) -> list[float]:
    """Times when the input really called for this output to change, used to excuse legitimate toggles.

    This excuses rather than demands, so readings inside the ADC margin count. A hold counts as a
    real change once firmware that filters noise for most of its deadline could fairly react to it.
    """
    demands: list[tuple[float, int]] = []
    faults: list[tuple[float, float]] = []
    for other in assertions:
        if isinstance(other, SafeStateOnFault) and other.output_pin == pin and other.fault_when is not None:
            for s, e in condition_intervals(other.fault_when, trace, scenario, spec, end_ms, may_hold=True):
                if e - s >= other.within_ms * REAL_CHANGE_FRACTION:
                    demands.append((s, other.safe_value))
                    faults.append((s, e))

    flips: list[float] = []
    for other in assertions:
        if not isinstance(other, OutputFollows) or other.pin != pin:
            continue
        if other.mode == "edge":
            # The output falls by itself on a timer, so each trigger that finds it low is one demand.
            cond_pins = {other.high_when.pin} if other.high_when is not None else set()
            holes = _suspended(pin, cond_pins, assertions, trace, scenario, spec, end_ms)
            rises = [t for t, lv in zip(timeline.times, timeline.levels) if lv == 1]
            for t in _edge_triggers(other, trace, scenario, spec, holes, end_ms):
                # Firmware may react to the first bounce edge, just before the press settles.
                if timeline.level_at(t) == 0 or any(t - other.within_ms <= r <= t for r in rises):
                    flips.append(t)
            continue
        for cond, wanted in ((other.high_when, 1), (other.low_when, 0)):
            if cond is None:
                continue
            # A fault overrides normal control, so the two never both demand a state at once.
            for s, e in condition_intervals(cond, trace, scenario, spec, end_ms, may_hold=True):
                for ps, pe in _subtract((s, e), faults):
                    if pe - ps >= other.within_ms * REAL_CHANGE_FRACTION:
                        demands.append((ps, wanted))

    demands.sort()
    state = 0
    for t, wanted in demands:
        if wanted != state:
            flips.append(t)
            state = wanted
    return sorted(flips)


def _glitch_toggles(pin: str, toggles: list[float], assertions: list, trace: dict, scenario: Scenario, spec: DeviceSpec, end_ms: float) -> int:
    """How many toggles followed a fault-range excursion too brief to require the safe state."""
    count = 0
    seen: set[float] = set()
    for other in assertions:
        if not isinstance(other, SafeStateOnFault) or other.output_pin != pin or other.fault_when is None:
            continue
        for s, e in condition_intervals(other.fault_when, trace, scenario, spec, end_ms, may_hold=True):
            if e - s >= other.within_ms * REAL_CHANGE_FRACTION:
                continue
            for t in toggles:
                if s <= t <= e + GLITCH_REACTION_MS and t not in seen:
                    seen.add(t)
                    count += 1
    return count


def eval_output_follows(a: OutputFollows, trace: dict, scenario: Scenario, spec: DeviceSpec, assertions: list) -> AssertionResult:
    end_ms = trace.get("sim_ms", scenario.duration_ms)
    timeline = output_timeline(trace, a.pin)
    cond_pins = {c.pin for c in (a.high_when, a.low_when) if c is not None}
    holes = _suspended(a.pin, cond_pins, assertions, trace, scenario, spec, end_ms)
    violations: list[Violation] = []
    exercised = False
    checked = 0

    if a.mode == "edge":
        for s in _edge_triggers(a, trace, scenario, spec, holes, end_ms):
            deadline = s + a.within_ms
            exercised = True
            checked += 1
            ok = timeline.level_at(s) == 1 or any(s <= t <= deadline and lv == 1 for t, lv in zip(timeline.times, timeline.levels))
            if not ok:
                violations.append(
                    Violation(
                        t_start=s,
                        t_end=deadline,
                        detail=f"{a.pin} never went HIGH within {a.within_ms:.0f} ms of the trigger at {_fmt_ms(s)}",
                    )
                )

    def check(cond: Optional[Condition], wanted: int) -> None:
        nonlocal exercised, checked
        if cond is None:
            return
        word = "HIGH" if wanted else "LOW"
        for s, e in condition_intervals(cond, trace, scenario, spec, end_ms):
            for ps, pe in _subtract((s, e), holes):
                if pe - ps < a.within_ms:
                    continue
                exercised = True
                checked += 1
                for bs, be in _time_at_level(timeline, ps + a.within_ms, pe, wanted):
                    if be - bs < 1.0:
                        continue
                    violations.append(
                        Violation(
                            t_start=bs,
                            t_end=be,
                            detail=f"{a.pin} was not {word} for {be - bs:.0f} ms while required (grace {a.within_ms:.0f} ms)",
                        )
                    )

    if a.mode == "level":
        check(a.high_when, 1)
        check(a.low_when, 0)
    violations.sort(key=lambda v: v.t_start)

    if not exercised:
        return _result(a, scenario, "not_exercised", "The input never held the condition long enough to test this.")
    if not violations:
        return _result(a, scenario, "pass", f"{a.pin} followed the input through {checked} required interval(s).")
    first = violations[0]
    if a.mode == "edge":
        return _result(
            a,
            scenario,
            "fail",
            f"{a.pin} missed {len(violations)} of {checked} trigger(s): {first.detail}.",
            {"missed": len(violations), "triggers": checked},
            violations,
        )
    total = sum(v.t_end - v.t_start for v in violations)
    return _result(
        a,
        scenario,
        "fail",
        f"{a.pin} was in the wrong state for {total:.0f} ms across {len(violations)} interval(s), first at {_fmt_ms(first.t_start)}: {first.detail}.",
        {"wrong_ms": round(total, 1), "intervals": len(violations)},
        violations,
    )


def eval_max_toggles(a: MaxToggles, trace: dict, scenario: Scenario, spec: DeviceSpec, assertions: list) -> AssertionResult:
    end_ms = trace.get("sim_ms", scenario.duration_ms)
    timeline = output_timeline(trace, a.pin)
    toggles = timeline.toggles()
    excused = _demanded_flips(a.pin, assertions, trace, scenario, spec, timeline, end_ms)
    controlling: set[str] = set()
    for other in assertions:
        if isinstance(other, OutputFollows) and other.pin == a.pin:
            controlling.update(c.pin for c in (other.high_when, other.low_when) if c is not None)
        elif isinstance(other, TogglePerPress) and other.output_pin == a.pin:
            controlling.add(other.input_pin)
    floats = _floating_windows(scenario, controlling, end_ms)
    toggles = [t for t in toggles if not any(fs <= t <= fe for fs, fe in floats)]

    worst = 0
    worst_start = 0.0
    left = 0
    violations: list[Violation] = []
    for right, t in enumerate(toggles):
        while toggles[left] <= t - a.window_ms:
            left += 1
        count = right - left + 1
        w_start = t - a.window_ms
        legit = bisect.bisect_right(excused, t + a.window_ms * 0.25) - bisect.bisect_left(excused, w_start)
        effective = count - max(0, legit)
        if effective > a.max_toggles:
            if count > worst:
                worst = count
                worst_start = toggles[left]
            if not violations or toggles[left] > violations[-1].t_end:
                violations.append(Violation(t_start=toggles[left], t_end=t, detail=f"{count} toggles"))
            else:
                violations[-1].t_end = t
                violations[-1].detail = f"{max(count, int(violations[-1].detail.split()[0]))} toggles"
    if not violations:
        return _result(
            a,
            scenario,
            "pass",
            f"{a.pin} toggled {len(toggles)} time(s) in {_fmt_ms(end_ms)}, within the limit of {a.max_toggles} per {a.window_ms:.0f} ms.",
            {"total_toggles": len(toggles)},
        )
    glitched = _glitch_toggles(a.pin, toggles, assertions, trace, scenario, spec, end_ms)
    cause = f" {glitched} of those toggles followed a fault-range glitch too brief to require the safe state, so the firmware is reacting to noise." if glitched else ""
    return _result(
        a,
        scenario,
        "fail",
        f"{a.pin} toggled {worst} times in a {a.window_ms:.0f} ms window starting at {_fmt_ms(worst_start)} (limit {a.max_toggles}), and {len(toggles)} times over the whole {_fmt_ms(end_ms)} run.{cause}",
        {"worst_window_toggles": worst, "total_toggles": len(toggles), "limit": a.max_toggles, "glitch_toggles": glitched},
        violations[:MAX_VIOLATIONS],
    )


def eval_toggle_per_press(a: TogglePerPress, trace: dict, scenario: Scenario) -> AssertionResult:
    end_ms = trace.get("sim_ms", scenario.duration_ms)
    if _floating_windows(scenario, {a.input_pin}, end_ms):
        return _result(a, scenario, "not_exercised", f"{a.input_pin} floats in this scenario, so it has no real presses to count.")
    initial, events = digital_input_levels(trace, scenario, a.input_pin)
    toggles = output_timeline(trace, a.output_pin).toggles()

    # Group input edges into settle events: bounce is any edge within settle_ms of the last.
    # Count the times the contact stayed open long enough inside a group to be a real release,
    # since debounce times differ and firmware may fairly read that as a second press.
    groups: list[list] = []  # [start, end, final value, real gaps]
    level = initial
    last_edge = 0.0
    for t, value in events:
        if groups and t - groups[-1][1] <= a.settle_ms:
            if level != a.active_level and t - last_edge >= a.settle_ms / 2:
                groups[-1][3] += 1
            groups[-1][1] = t
            groups[-1][2] = value
        else:
            groups.append([t, t, value, 0])
        level = value
        last_edge = t

    # A press is a settled change from idle to active. A blip that returns to where it
    # started is not a press: it needs no toggle, and may not cause one if it is plainly noise.
    presses: list[tuple[float, float, int]] = []
    ambiguous: list[tuple[float, float]] = []
    settled = initial
    for start, end, value, gaps in groups:
        if value == a.active_level and settled != a.active_level:
            presses.append((start, end, gaps))
        if gaps or (value == settled and settled != a.active_level):
            # A real gap, or a short tap. The spec does not settle these, so firmware may go either way.
            ambiguous.append((start, end + a.within_ms))
        settled = value
    if not presses:
        return _result(a, scenario, "not_exercised", f"{a.input_pin} was never pressed in this scenario.")

    violations: list[Violation] = []
    counts: list[int] = []
    windows: list[tuple[float, float]] = []
    wrong = 0
    for i, (start, settled_at, gaps) in enumerate(presses):
        # The deadline runs from when the contact settles: firmware cannot know any sooner.
        deadline = settled_at + a.within_ms
        window_end = deadline
        if i + 1 < len(presses):
            window_end = min(window_end, presses[i + 1][0])
        windows.append((start, window_end))
        if deadline > end_ms:
            continue
        # A toggle inside a later ambiguous group may answer this press, since firmware may read the
        # whole burst as one press. It just cannot count as an extra toggle against this press.
        later = [w for w in ambiguous if w[0] > start]
        in_window = [t for t in toggles if start <= t <= window_end]
        own = [t for t in in_window if not any(s <= t <= e for s, e in later)]
        n = len(own) if own else len(in_window)
        counts.append(n)
        if not in_window or len(own) > 1 + gaps:
            wrong += 1
            violations.append(
                Violation(
                    t_start=start,
                    t_end=window_end,
                    detail=f"press at {_fmt_ms(start)} toggled {a.output_pin} {n} time(s), expected exactly 1",
                )
            )
    if not counts:
        return _result(a, scenario, "not_exercised", "No press finished inside the run.")

    # Toggles the input did not ask for: on release, on a glitch, or out of nowhere. Boot is exempt.
    allowed = windows + ambiguous
    first_input = events[0][0] if events else end_ms
    spurious = [t for t in toggles if t >= first_input and not any(s <= t <= e for s, e in allowed)]
    violations.extend(Violation(t_start=t, t_end=t, detail=f"{a.output_pin} toggled at {_fmt_ms(t)} with no press to explain it") for t in spurious)
    violations.sort(key=lambda v: v.t_start)

    if not violations:
        return _result(a, scenario, "pass", f"All {len(counts)} press(es) toggled {a.output_pin} exactly once.", {"presses": len(counts)})
    parts: list[str] = []
    if wrong:
        parts.append(f"{wrong} of {len(counts)} press(es) did not toggle {a.output_pin} exactly once; toggle counts per press were {counts}.")
    if spurious:
        parts.append(f"{a.output_pin} also toggled {len(spurious)} time(s) with no press to explain it, first at {_fmt_ms(spurious[0])}.")
    return _result(
        a,
        scenario,
        "fail",
        " ".join(parts),
        {"presses": len(counts), "toggles_per_press": counts, "spurious_toggles": len(spurious)},
        violations[:MAX_VIOLATIONS],
    )


def _compile_regex(pattern: str) -> Optional[re.Pattern]:
    try:
        return re.compile(pattern)
    except re.error:
        return None


def eval_serial_period(a: SerialPeriod, trace: dict, scenario: Scenario) -> AssertionResult:
    end_ms = trace.get("sim_ms", scenario.duration_ms)
    rx = _compile_regex(a.pattern)
    if rx is None:
        return _result(a, scenario, "not_exercised", f"Invalid regex {a.pattern!r}.")
    times = [line["t_ms"] for line in trace.get("serial_log", []) if rx.search(line["text"])]
    limit = a.period_ms + a.tolerance_ms
    if not times:
        return _result(
            a,
            scenario,
            "fail",
            f"No serial line matched /{a.pattern}/ in {_fmt_ms(end_ms)}; expected one every {a.period_ms:.0f} ms.",
            {"matches": 0},
            [Violation(t_start=0, t_end=end_ms, detail="no matching serial line")],
        )
    violations: list[Violation] = []
    gaps = [b - a_t for a_t, b in zip(times, times[1:])]
    if times[0] > limit:
        violations.append(Violation(t_start=0, t_end=times[0], detail=f"first line only at {_fmt_ms(times[0])}"))
    for t0, gap in zip(times, gaps):
        if gap > limit or gap < a.period_ms - a.tolerance_ms:
            violations.append(Violation(t_start=t0, t_end=t0 + gap, detail=f"gap of {gap:.0f} ms"))
    if end_ms - times[-1] > limit:
        violations.append(Violation(t_start=times[-1], t_end=end_ms, detail=f"silent for final {end_ms - times[-1]:.0f} ms"))
    if not violations:
        mean = sum(gaps) / len(gaps) if gaps else a.period_ms
        return _result(a, scenario, "pass", f"{len(times)} lines at a mean period of {mean:.0f} ms.", {"matches": len(times), "mean_gap_ms": round(mean, 1)})
    worst = max(gaps) if gaps else end_ms
    return _result(
        a,
        scenario,
        "fail",
        f"Expected /{a.pattern}/ every {a.period_ms:.0f} ± {a.tolerance_ms:.0f} ms; {len(violations)} of {len(times)} intervals were out of tolerance, worst gap {worst:.0f} ms.",
        {"matches": len(times), "worst_gap_ms": round(worst, 1)},
        violations[:MAX_VIOLATIONS],
    )


def eval_serial_value(a: SerialValueMatches, trace: dict, scenario: Scenario, spec: DeviceSpec) -> AssertionResult:
    rx = _compile_regex(a.pattern)
    series = analog_series(trace, a.input_pin)
    if rx is None:
        return _result(a, scenario, "not_exercised", f"Invalid regex {a.pattern!r}.")
    if series is None:
        return _result(a, scenario, "not_exercised", f"{a.input_pin} was not driven in this scenario.")

    _, _, unit = spec.pin(a.input_pin).parsed_scale() if spec.pin(a.input_pin) else (0, 0, "")
    checked = 0
    worst_err = 0.0
    worst: Optional[dict] = None
    violations: list[Violation] = []
    for line in trace.get("serial_log", []):
        m = rx.search(line["text"])
        if not m:
            continue
        try:
            printed = float(m.group(1))
        except (IndexError, ValueError):
            continue
        t = line["t_ms"]
        i_hi = bisect.bisect_right(series.times, t)
        i_lo = bisect.bisect_left(series.times, t - a.max_lag_ms - 10)
        i_lo = max(0, min(i_lo, max(i_hi - 1, 0)))
        lows = series.low[i_lo:i_hi] or series.low[:1]
        highs = series.high[i_lo:i_hi] or series.high[:1]
        lo = spec.to_physical(a.input_pin, min(lows))
        hi = spec.to_physical(a.input_pin, max(highs))
        if lo > hi:
            lo, hi = hi, lo
        # The firmware may have sampled any moment in the lag window, so the
        # printed value is correct if it is close to any value seen in that window.
        err = 0.0 if lo <= printed <= hi else min(abs(printed - lo), abs(printed - hi))
        checked += 1
        if err > worst_err:
            worst_err = err
            worst = {"printed": printed, "actual_low": round(lo, 2), "actual_high": round(hi, 2), "t_ms": t}
        if err > a.tolerance and len(violations) < MAX_VIOLATIONS:
            violations.append(
                Violation(
                    t_start=max(0.0, t - 5),
                    t_end=t + 5,
                    detail=f"printed {printed:g} {unit}, injected {lo:.1f} to {hi:.1f} {unit}",
                )
            )
    if checked == 0:
        return _result(
            a,
            scenario,
            "fail",
            f"No serial line matched /{a.pattern}/ so the printed value could not be compared with {a.input_pin}.",
            {"checked": 0},
            [Violation(t_start=0, t_end=trace.get("sim_ms", scenario.duration_ms), detail="no parsable serial value")],
        )
    if not violations:
        return _result(a, scenario, "pass", f"{checked} printed values within ±{a.tolerance:g} {unit} of the injected input.", {"checked": checked, "worst_error": round(worst_err, 2)})
    w = worst or {}
    return _result(
        a,
        scenario,
        "fail",
        f"Firmware printed {w.get('printed', 0):g} {unit} at {_fmt_ms(w.get('t_ms', 0))} while the injected input was {w.get('actual_low', 0)} to {w.get('actual_high', 0)} {unit}: off by {worst_err:.1f} {unit} (tolerance ±{a.tolerance:g}). {len(violations)} of {checked} values were wrong.",
        {"checked": checked, "wrong": len(violations), "worst_error": round(worst_err, 2)},
        violations,
    )


def eval_safe_state(a: SafeStateOnFault, trace: dict, scenario: Scenario, spec: DeviceSpec) -> AssertionResult:
    end_ms = trace.get("sim_ms", scenario.duration_ms)
    timeline = output_timeline(trace, a.output_pin)
    intervals: list[tuple[float, float]] = []
    if a.fault_when is not None:
        intervals.extend(condition_intervals(a.fault_when, trace, scenario, spec, end_ms))
    if a.floating_pin:
        for w in scenario.floating:
            if w.pin == a.floating_pin:
                intervals.append((w.from_ms, min(w.to_ms, end_ms)))

    word = "HIGH" if a.safe_value else "LOW"
    violations: list[Violation] = []
    exercised = 0
    for s, e in sorted(intervals):
        if e - s < a.within_ms:
            continue
        exercised += 1
        for bs, be in _time_at_level(timeline, s + a.within_ms, e, a.safe_value):
            if be - bs < 1.0:
                continue
            violations.append(Violation(t_start=bs, t_end=be, detail=f"{a.output_pin} not {word} for {be - bs:.0f} ms during fault"))
    if exercised == 0:
        return _result(a, scenario, "not_exercised", "This scenario did not inject that fault for long enough.")
    if not violations:
        return _result(a, scenario, "pass", f"{a.output_pin} reached safe state {word} within {a.within_ms:.0f} ms in {exercised} fault interval(s).")
    total = sum(v.t_end - v.t_start for v in violations)
    return _result(
        a,
        scenario,
        "fail",
        f"During the fault, {a.output_pin} was not in safe state {word} for {total:.0f} ms (allowed {a.within_ms:.0f} ms to react).",
        {"unsafe_ms": round(total, 1)},
        violations[:MAX_VIOLATIONS],
    )


def eval_responsive(a: Responsive, trace: dict, scenario: Scenario) -> AssertionResult:
    end_ms = trace.get("sim_ms", scenario.duration_ms)
    times = sorted(
        [line["t_ms"] for line in trace.get("serial_log", [])]
        + [e["t_ms"] for e in trace.get("pin_events", []) if e.get("dir") == "out"]
        + [e["t_ms"] for e in trace.get("pwm_events", [])]
    )
    times = [t for t in times if t >= a.start_ms]
    points = [a.start_ms] + times + [end_ms]
    violations: list[Violation] = []
    worst = 0.0
    for t0, t1 in zip(points, points[1:]):
        gap = t1 - t0
        worst = max(worst, gap)
        if gap > a.max_gap_ms:
            violations.append(Violation(t_start=t0, t_end=t1, detail=f"no activity for {gap:.0f} ms"))
    if not violations:
        return _result(a, scenario, "pass", f"Longest silent gap was {worst:.0f} ms (limit {a.max_gap_ms:.0f} ms).", {"worst_gap_ms": round(worst, 1)})
    return _result(
        a,
        scenario,
        "fail",
        f"Firmware went silent for {worst:.0f} ms with no serial output or pin activity (limit {a.max_gap_ms:.0f} ms); {len(violations)} such gap(s).",
        {"worst_gap_ms": round(worst, 1), "gaps": len(violations)},
        violations[:MAX_VIOLATIONS],
    )


def eval_no_crash(a: NoCrash, trace: dict, scenario: Scenario) -> AssertionResult:
    reason = trace.get("exit_reason", "unknown")
    if reason == "completed":
        return _result(a, scenario, "pass", f"Ran the full {_fmt_ms(trace.get('sim_ms', 0))} of simulated time.")
    t = trace.get("sim_ms", 0)
    return _result(
        a,
        scenario,
        "fail",
        f"Emulation ended with exit_reason={reason} at {_fmt_ms(t)} of simulated time.",
        {"exit_reason": reason},
        [Violation(t_start=t, t_end=scenario.duration_ms, detail=f"exit_reason={reason}")],
    )


def _result(a, scenario: Scenario, status: str, evidence: str, metrics: Optional[dict] = None, violations: Optional[list] = None) -> AssertionResult:
    return AssertionResult(
        assertion_id=a.id,
        scenario_id=scenario.id,
        type=a.type,
        status=status,
        evidence=evidence,
        metrics=metrics or {},
        violations=violations or [],
    )


def evaluate(assertion, trace: dict, scenario: Scenario, spec: DeviceSpec, assertions: list) -> AssertionResult:
    if trace.get("harness_error") or "exit_reason" not in trace:
        if isinstance(assertion, NoCrash):
            return _result(assertion, scenario, "fail", "The harness produced no trace for this run.", {}, [])
        return _result(assertion, scenario, "not_exercised", "The harness produced no trace for this run.")
    if isinstance(assertion, OutputFollows):
        return eval_output_follows(assertion, trace, scenario, spec, assertions)
    if isinstance(assertion, MaxToggles):
        return eval_max_toggles(assertion, trace, scenario, spec, assertions)
    if isinstance(assertion, TogglePerPress):
        return eval_toggle_per_press(assertion, trace, scenario)
    if isinstance(assertion, SerialPeriod):
        return eval_serial_period(assertion, trace, scenario)
    if isinstance(assertion, SerialValueMatches):
        return eval_serial_value(assertion, trace, scenario, spec)
    if isinstance(assertion, SafeStateOnFault):
        return eval_safe_state(assertion, trace, scenario, spec)
    if isinstance(assertion, Responsive):
        return eval_responsive(assertion, trace, scenario)
    return eval_no_crash(assertion, trace, scenario)


def evaluate_all(assertions: list, trace: dict, scenario: Scenario, spec: DeviceSpec) -> list[AssertionResult]:
    return [evaluate(a, trace, scenario, spec, assertions) for a in assertions]
