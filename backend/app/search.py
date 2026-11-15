"""Stimulus search: bounded, seeded variants of the scenarios that already ran, and shrinking of the ones that break something.

The model's scenarios and the built-in library probe a handful of inputs. Real bugs often sit a little off those: a
threshold hit 8 mV lower, a press 30 ms long instead of 60, a bounce twice as long. This module perturbs the numbers
of each scenario in small, physically plausible steps (threshold offsets, timing shifts, bounce duration and count,
noise amplitude, press length, input ordering). It is plain Python with a fixed seed, so the same run makes the same
variants. The orchestrator (agent.py) runs them in the sandbox and judges them with the usual assertion engine.

Not supported: long-uptime fast-forward (millis() near its 32-bit rollover, hours of runtime). The harness starts every
scenario at power-on and caps a scenario at 15 s of simulated time, with no way to set the clock, so a rollover cannot
be reached. UNSUPPORTED says so in every report.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from .models import AnalogPoint, DeviceSpec, DigitalEvent, FloatingWindow, Scenario
from .scenario_lib import VCC_MV, _thresholds_mv

UNSUPPORTED = ["uptime fast-forward (millis() near rollover, hours of runtime): the harness cannot set the clock and caps a scenario at 15 s"]

MUTATIONS = ("threshold", "timing", "bounce", "noise", "press", "order")

THRESHOLD_OFFSETS_MV = (-60, -30, -15, -8, -4, 4, 8, 15, 30, 60)
NEAR_THRESHOLD_MV = (-12, -6, -3, 0, 3, 6, 12)
TIMING_SHIFTS_MS = (-600, -250, -120, -40, 40, 120, 250, 600)
BOUNCE_MS = (2, 5, 10, 20, 40, 80)
BOUNCE_COUNTS = (2, 4, 8, 16, 24)
NOISE_MV = (0, 3, 6, 12, 20, 30)
PRESS_MS = (15, 30, 50, 80, 150, 300, 800, 1500)
ORDER_SHIFTS_MS = (-700, -300, -100, 100, 300, 700)

# Shrinking: never spend more than this many sandbox runs on one scenario, and look at this many removals per round.
SHRINK_MAX_RUNS = 18
SHRINK_MAX_ROUNDS = 4
SHRINK_CANDIDATES_PER_ROUND = 8
# Keep the run going this long after the first violation ends when cutting a scenario short, so a check that needs a
# little context (a window, a grace period) still sees it.
SHRINK_TAIL_MS = 500.0
MIN_SHRUNK_MS = 1500.0


# Scenarios that sit on a supply rail or on random noise have no neighbourhood worth searching.
SKIP_PARENTS = ("containment-", "builtin-floating-", "builtin-extremes-")


def fingerprint(s: Scenario) -> str:
    return hashlib.sha1(json.dumps(s.harness_json(), sort_keys=True).encode()).hexdigest()


def complexity(s: Scenario) -> tuple[int, float]:
    """(how many separate things the scenario does, how long it runs). Smaller is a cleaner reproduction."""
    n = sum(max(0, len(a.segments) - 1) + len(a.spikes) + (1 if a.noise_mv > 0 else 0) for a in s.analog)
    n += sum(len(d.events) + sum(1 for e in d.events if e.bounce_count and e.bounce_ms) for d in s.digital)
    n += len(s.floating)
    return n, s.duration_ms


# ------------------------------------------------------------------ variants


def _clamp_mv(mv: float) -> float:
    return max(0.0, min(VCC_MV, mv))


def _increasing(values: list[float]) -> list[float]:
    """Keep times strictly increasing, nudging a tie forward by 1 ms."""
    out: list[float] = []
    for v in values:
        if out and v <= out[-1]:
            v = out[-1] + 1.0
        out.append(v)
    return out


def _clone(s: Scenario) -> Scenario:
    return s.model_copy(deep=True)


@dataclass
class Context:
    spec: DeviceSpec
    assertions: list


def m_threshold(s: Scenario, rng: random.Random, ctx: Context) -> Optional[tuple[Scenario, str]]:
    pins = [a for a in s.analog if a.segments]
    if not pins:
        return None
    out = _clone(s)
    a = rng.choice(out.analog)
    high, low = _thresholds_mv(a.pin, ctx.spec, ctx.assertions)
    targets = [t for t in (high, low) if t is not None]
    if targets and rng.random() < 0.5:
        thr = rng.choice(targets)
        off = rng.choice(NEAR_THRESHOLD_MV)
        # Move the scenario so the level it ends on sits just beside a threshold the checks name.
        delta = max(-1500.0, min(1500.0, thr + off - a.segments[-1].mv))
        desc = f"{a.pin} level moved to {off:+d} mV from the {thr:.0f} mV threshold"
    else:
        delta = float(rng.choice(THRESHOLD_OFFSETS_MV))
        desc = f"{a.pin} level shifted by {delta:+.0f} mV"
    if not delta:
        return None
    for p in a.segments:
        p.mv = _clamp_mv(p.mv + delta)
    return out, desc


def m_timing(s: Scenario, rng: random.Random, ctx: Context) -> Optional[tuple[Scenario, str]]:
    if not (s.analog or s.digital or s.floating):
        return None
    dt = float(rng.choice(TIMING_SHIFTS_MS))
    out = _clone(s)
    _shift(out, dt, None)
    return out, f"events shifted by {dt:+.0f} ms"


def _shift(s: Scenario, dt: float, pins: Optional[set[str]]) -> None:
    """Move the events of some inputs (all, if pins is None) by dt ms. Whatever would leave the run is dropped."""
    end = s.duration_ms
    for a in s.analog:
        if pins is not None and a.pin not in pins:
            continue
        pts = sorted(a.segments, key=lambda p: p.t_ms)
        start_mv = pts[0].mv
        later = []
        for p in pts[1:]:
            t = p.t_ms + dt
            if t <= 0:
                start_mv = p.mv  # it happened before power-on, so it is the level the run starts at
            elif t < end - 1:
                later.append((t, p.mv))
        pts[0].mv = start_mv
        pts[0].t_ms = 0.0
        a.segments = [pts[0]] + [AnalogPoint(t_ms=t, mv=mv) for t, mv in zip(_increasing([t for t, _ in later]), [mv for _, mv in later])]
        a.spikes = [sp for sp in a.spikes if 0 <= sp.t_ms + dt < end - 1]
        for sp in a.spikes:
            sp.t_ms += dt
    for d in s.digital:
        if pins is not None and d.pin not in pins:
            continue
        events = sorted(d.events, key=lambda e: e.t_ms)
        kept = [e for e in events if 1 <= e.t_ms + dt < end - 1]
        for e, t in zip(kept, _increasing([e.t_ms + dt for e in kept])):
            e.t_ms = t
        d.events = kept
    moved: list[FloatingWindow] = []
    for f in s.floating:
        if pins is not None and f.pin not in pins:
            moved.append(f)
            continue
        start = max(0.0, f.from_ms + dt)
        if start >= end - 1:
            continue
        f.from_ms = start
        f.to_ms = f.to_ms if f.to_ms >= end else max(start + 1.0, min(end, f.to_ms + dt))
        moved.append(f)
    s.floating = moved


def m_bounce(s: Scenario, rng: random.Random, ctx: Context) -> Optional[tuple[Scenario, str]]:
    if not any(d.events for d in s.digital):
        return None
    ms, count = rng.choice(BOUNCE_MS), rng.choice(BOUNCE_COUNTS)
    out = _clone(s)
    for d in out.digital:
        for e in d.events:
            e.bounce_ms, e.bounce_count = float(ms), count
    return out, f"contact bounce {ms} ms x {count}"


def m_noise(s: Scenario, rng: random.Random, ctx: Context) -> Optional[tuple[Scenario, str]]:
    if not s.analog:
        return None
    out = _clone(s)
    a = rng.choice(out.analog)
    choices = [v for v in NOISE_MV if v != a.noise_mv]
    a.noise_mv = float(rng.choice(choices))
    return out, f"{a.pin} noise {a.noise_mv:.0f} mV"


def m_press(s: Scenario, rng: random.Random, ctx: Context) -> Optional[tuple[Scenario, str]]:
    pins = [d for d in s.digital if len(d.events) >= 2]
    if not pins:
        return None
    out = _clone(s)
    d = rng.choice([x for x in out.digital if len(x.events) >= 2])
    length = float(rng.choice(PRESS_MS))
    d.events.sort(key=lambda e: e.t_ms)
    shift = 0.0
    pressed_at: Optional[float] = None
    for e in d.events:
        e.t_ms += shift
        if e.value != d.initial:
            pressed_at = e.t_ms
        elif pressed_at is not None:
            # Later events keep their gap to this release, so only the press itself gets longer or shorter.
            shift += pressed_at + length - e.t_ms
            e.t_ms = pressed_at + length
            pressed_at = None
    if d.events[-1].t_ms >= out.duration_ms - 1:
        return None
    return out, f"{d.pin} presses lasting {length:.0f} ms"


def m_order(s: Scenario, rng: random.Random, ctx: Context) -> Optional[tuple[Scenario, str]]:
    """Change which input moves first. Two moving inputs: slide one against the other. One: make a still input change beside it."""
    moving = sorted({a.pin for a in s.analog if len(a.segments) > 1} | {d.pin for d in s.digital if d.events})
    out = _clone(s)
    if len(moving) >= 2:
        pin = rng.choice(moving)
        dt = float(rng.choice(ORDER_SHIFTS_MS))
        _shift(out, dt, {pin})
        return out, f"{pin} events moved {dt:+.0f} ms against the other inputs"
    if len(moving) == 1:
        anchors = sorted({e.t_ms for d in out.digital if d.pin == moving[0] for e in d.events} | {p.t_ms for a in out.analog if a.pin == moving[0] for p in a.segments[1:]})
        still_analog = [a for a in out.analog if len(a.segments) == 1 and not a.spikes]
        still_digital = [d for d in out.digital if not d.events]
        if anchors and (still_analog or still_digital):
            anchor = rng.choice(anchors)
            dt = float(rng.choice(ORDER_SHIFTS_MS))
            at = max(100.0, min(out.duration_ms - 400.0, anchor + dt))
            if still_analog and (not still_digital or rng.random() < 0.5):
                a = rng.choice(still_analog)
                level = a.segments[0].mv
                step = float(rng.choice((-300, -150, 150, 300)))
                a.segments = [a.segments[0], AnalogPoint(t_ms=at - 1.0, mv=level), AnalogPoint(t_ms=at, mv=_clamp_mv(level + step))]
                return out, f"{a.pin} steps {step:+.0f} mV at {at:.0f} ms, {dt:+.0f} ms from the {moving[0]} event at {anchor:.0f} ms"
            d = rng.choice(still_digital)
            d.events = [_event(at, 1 - d.initial), _event(at + 300.0, d.initial)]
            return out, f"{d.pin} pressed at {at:.0f} ms, {dt:+.0f} ms from the {moving[0]} event at {anchor:.0f} ms"
    return None


def _event(t_ms: float, value: int) -> DigitalEvent:
    return DigitalEvent(t_ms=t_ms, value=value)


MUTATE: dict[str, Callable[[Scenario, random.Random, Context], Optional[tuple[Scenario, str]]]] = {
    "threshold": m_threshold,
    "timing": m_timing,
    "bounce": m_bounce,
    "noise": m_noise,
    "press": m_press,
    "order": m_order,
}


def make_variants(scenarios: list[Scenario], spec: DeviceSpec, assertions: list, count: int, seed: int, kinds: Optional[dict[str, str]] = None) -> list[Scenario]:
    """Up to `count` distinct variants, spread over the parents. The same inputs and seed give the same variants.

    `kinds`, if given, is filled with each variant's mutation kind by id.
    """
    if count <= 0:
        return []
    rng = random.Random(seed)
    ctx = Context(spec, assertions)
    parents = [s for s in scenarios if s.source in ("builtin", "llm") and not s.id.startswith(SKIP_PARENTS)]
    if not parents:
        return []
    order = list(parents)
    rng.shuffle(order)
    seen = {fingerprint(s) for s in scenarios}
    used: dict[str, set[str]] = {s.id: set() for s in parents}
    variants: list[Scenario] = []
    for attempt in range(count * 25):
        if len(variants) >= count:
            break
        parent = order[attempt % len(order)]
        left = [k for k in MUTATIONS if k not in used[parent.id]]
        if not left:
            used[parent.id].clear()
            left = list(MUTATIONS)
        kind = rng.choice(left)
        used[parent.id].add(kind)
        made = MUTATE[kind](parent, rng, ctx)
        if made is None:
            continue
        variant, desc = made
        fp = fingerprint(variant)
        if fp in seen:
            continue
        seen.add(fp)
        variant.id = f"search-{len(variants) + 1}"
        if kinds is not None:
            kinds[variant.id] = kind
        variant.source = "search"
        variant.parent = parent.id
        variant.variant = desc
        variant.name = f"{parent.name}: {desc}"[:140]
        variant.hypothesis = f"A small change to {parent.name!r} ({desc}) may expose behaviour the original input does not reach."
        variants.append(variant)
    return variants


# ------------------------------------------------------------------- shrink


def _cut(s: Scenario, end_ms: float) -> Scenario:
    """The scenario with everything after end_ms removed."""
    out = _clone(s)
    out.duration_ms = end_ms
    for a in out.analog:
        keep = [p for p in a.segments if p.t_ms < end_ms]
        a.segments = keep or a.segments[:1]
        a.spikes = [sp for sp in a.spikes if sp.t_ms < end_ms]
    for d in out.digital:
        d.events = [e for e in d.events if e.t_ms < end_ms]
    out.floating = [f for f in out.floating if f.from_ms < end_ms]
    return out


def reproduction_point(assertion, violations: list, duration_ms: float) -> float:
    """When the failure is already established, so that cutting the run a little after it still reproduces it.

    A violation can run to the end of the scenario (chatter that never stops), so its end says little.
    The check's own window (a toggle window, a response deadline) says how long it needs to see.
    """
    if not violations:
        return duration_ms
    first = min(violations, key=lambda v: v.t_start)
    span = max(float(getattr(assertion, "window_ms", 0.0) or 0.0), 2 * float(getattr(assertion, "within_ms", 0.0) or 0.0), 1000.0)
    return first.t_start + min(first.t_end - first.t_start, span)


def simplifications(s: Scenario, first_end_ms: float) -> list[tuple[Scenario, str]]:
    """Whole-scenario reductions to try first: end the run early, silence noise, drop bounce, and all three together."""
    cut_at = max(MIN_SHRUNK_MS, math.ceil((first_end_ms + SHRINK_TAIL_MS) / 100.0) * 100.0)
    out: list[tuple[Scenario, str]] = []

    def quiet(x: Scenario) -> Scenario:
        y = _clone(x)
        for a in y.analog:
            a.noise_mv = 0.0
        for d in y.digital:
            for e in d.events:
                e.bounce_ms, e.bounce_count = 0.0, 0
        return y

    cuttable = cut_at < s.duration_ms
    noisy = any(a.noise_mv > 0 for a in s.analog) or any(e.bounce_count for d in s.digital for e in d.events)
    if cuttable and noisy:
        out.append((quiet(_cut(s, cut_at)), "shorter and without noise or bounce"))
    if cuttable:
        out.append((_cut(s, cut_at), f"ended at {cut_at:.0f} ms"))
    if noisy:
        out.append((quiet(s), "without noise or bounce"))
    return out


def _units(d) -> list[list[int]]:
    """A digital input's events as removable units: a press with its release, or a lone event. Indices into the time-sorted events."""
    events = sorted(d.events, key=lambda e: e.t_ms)
    units: list[list[int]] = []
    j = 0
    while j < len(events):
        if events[j].value != d.initial and j + 1 < len(events) and events[j + 1].value == d.initial:
            units.append([j, j + 1])
            j += 2
        else:
            units.append([j])
            j += 1
    return units


def removals(s: Scenario) -> list[tuple[Scenario, str]]:
    """Ways to take things out of the scenario: halves of long sequences first, then single items, latest first."""
    out: list[tuple[Scenario, str]] = []
    # Long sequences (a rapid oscillation has dozens of points) shrink in halves, so a few rounds reach the core.
    for i, a in enumerate(s.analog):
        interior = list(range(1, len(a.segments) - 1))
        if len(interior) >= 6:
            half = len(interior) // 2
            for label, drop in (("later half", interior[half:]), ("earlier half", interior[:half])):
                y = _clone(s)
                y.analog[i].segments = [p for k, p in enumerate(a.segments) if k not in drop]
                out.append((y, f"{a.pin}: dropped the {label} of its points"))
    for i, d in enumerate(s.digital):
        pairs = _units(d)
        if len(pairs) >= 4:
            half = len(pairs) // 2
            for label, drop in (("later half", pairs[half:]), ("earlier half", pairs[:half])):
                y = _clone(s)
                gone = {k for unit in drop for k in unit}
                ordered = sorted(d.events, key=lambda e: e.t_ms)
                y.digital[i].events = [e for k, e in enumerate(ordered) if k not in gone]
                out.append((y, f"{d.pin}: dropped the {label} of its presses"))
    for i, d in enumerate(s.digital):
        events = sorted(d.events, key=lambda e: e.t_ms)
        for unit in reversed(_units(d)):
            y = _clone(s)
            y.digital[i].events = [e for k, e in enumerate(events) if k not in unit]
            out.append((y, f"{d.pin}: dropped the event at {events[unit[0]].t_ms:.0f} ms"))
    for i, a in enumerate(s.analog):
        for k in range(len(a.segments) - 2, 0, -1):
            y = _clone(s)
            del y.analog[i].segments[k]
            out.append((y, f"{a.pin}: dropped the point at {a.segments[k].t_ms:.0f} ms"))
        for k, sp in enumerate(a.spikes):
            y = _clone(s)
            del y.analog[i].spikes[k]
            out.append((y, f"{a.pin}: dropped the spike at {sp.t_ms:.0f} ms"))
    for k, f in enumerate(s.floating):
        y = _clone(s)
        del y.floating[k]
        out.append((y, f"{f.pin}: dropped the floating window at {f.from_ms:.0f} ms"))
    return [(y, d) for y, d in out if y.analog or y.digital or y.floating]


@dataclass
class Shrunk:
    scenario: Scenario
    runs: int
    events_before: int
    events_after: int
    duration_before_ms: float
    duration_after_ms: float
    steps: list[str]


async def shrink(
    scenario: Scenario,
    first_end_ms: float,
    still_fails: Callable[[list[Scenario]], Awaitable[list[bool]]],
    max_runs: int = SHRINK_MAX_RUNS,
    deadline: Optional[float] = None,
) -> Shrunk:
    """Greedy reduction. `still_fails` runs candidates (in parallel, if it likes) and says which still break the same check.

    Round 0 tries the whole-scenario simplifications. Each later round tries single removals and keeps the
    reproducing candidate with the least in it. Stops at the run budget, the deadline, or when nothing more can go.
    """
    current = scenario
    runs = 0
    steps: list[str] = []
    before = complexity(scenario)

    def late() -> bool:
        return deadline is not None and time.monotonic() > deadline

    cands = simplifications(current, first_end_ms)[:max_runs]
    if cands and not late():
        ok = await still_fails([c for c, _ in cands])
        runs += len(cands)
        wins = [(c, d) for (c, d), k in zip(cands, ok) if k]
        if wins:
            current, note = min(wins, key=lambda w: complexity(w[0]))
            steps.append(note)
    for _ in range(SHRINK_MAX_ROUNDS):
        if runs >= max_runs or late():
            break
        cands = removals(current)[: min(SHRINK_CANDIDATES_PER_ROUND, max_runs - runs)]
        if not cands:
            break
        ok = await still_fails([c for c, _ in cands])
        runs += len(cands)
        wins = [(c, d) for (c, d), k in zip(cands, ok) if k]
        if not wins:
            break
        current, note = min(wins, key=lambda w: complexity(w[0]))
        steps.append(note)
    after = complexity(current)
    return Shrunk(current, runs, before[0], after[0], before[1], after[1], steps)
