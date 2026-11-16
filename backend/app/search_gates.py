"""Acceptance gates for the stimulus search.

The search perturbs the scenarios and runs them on the uploaded firmware. A check that breaks on a variant is only
a finding if all three hold:

  (a) it fails on the user's sketch. The kept scenario is run on that sketch once more as a real result.
  (b) it passes on BOTH clean rooms in that same variant (and in the shrunk scenario that is finally kept). A room
      that fails it, or never exercised it, or a missing room, means no correct firmware is known to pass it.
  (c) the variant lies within the spec's stated ranges: no input level outside the range the spec states for the
      pin (the ADC's 0 to 5 V if it states none), and nothing harsher than the spec allows, or, where the spec says
      nothing, harsher than the scenarios the run already used: no shorter press, no longer or more bounce, no
      more noise.

Everything here is plain Python on the scenario JSON and the spec text. Nothing asks a model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .models import AssertionResult, DeviceSpec, Scenario
from .scenario_lib import VCC_MV

# Gate (b) needs this many clean rooms to have built and judged the variant.
REQUIRED_ROOMS = 2

_NUM = r"(-?\d+(?:\.\d+)?)"
_TIME = rf"{_NUM}\s*(ms|s)\b"
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+|\n+")

_MIN_PRESS = [
    re.compile(rf"(?:press(?:es|ed)?|held|hold(?:s|ing)?)[^.;\n]*?(?:at least|no shorter than|minimum(?: of)?|longer than|≥|>=)\s*{_TIME}", re.IGNORECASE),
    re.compile(rf"(?:shorter than|less than|under|below)\s*{_TIME}[^.;\n]*?(?:ignored?|is bounce|not (?:a )?press|does not count|is noise)", re.IGNORECASE),
]
_MAX_BOUNCE = re.compile(rf"bounc\w*[^.;\n]*?(?:up to|as long as|lasting|at most|no more than|under|within|less than|≤|<=)\s*{_TIME}", re.IGNORECASE)
_MAX_NOISE = re.compile(rf"noise[^.;\n]*?(?:up to|at most|within|under|less than|±|\+/-|≤|<=|of)\s*{_NUM}\s*mV\b", re.IGNORECASE)
_RANGE_WORDS = re.compile(r"\b(?:range|spans?|full[- ]scale|measures?|reads?|operating)\b", re.IGNORECASE)


@dataclass
class Limits:
    """What a variant may contain. `stated` records which numbers came from the spec text, the rest come from the run's own scenarios."""

    analog_mv: dict[str, tuple[float, float]] = field(default_factory=dict)  # per analog pin: the levels a variant may introduce
    min_press_ms: Optional[float] = None  # no shorter press than this (None: nothing stated and no press anywhere to compare with)
    max_bounce_ms: float = 0.0
    max_bounce_count: int = 0
    max_noise_mv: float = 0.0
    stated: list[str] = field(default_factory=list)

    def report(self) -> dict:
        return {
            "analog_mv": {pin: [round(lo, 1), round(hi, 1)] for pin, (lo, hi) in sorted(self.analog_mv.items())},
            "min_press_ms": self.min_press_ms,
            "max_bounce_ms": self.max_bounce_ms,
            "max_bounce_count": self.max_bounce_count,
            "max_noise_mv": self.max_noise_mv,
            "stated_in_spec": list(self.stated),
        }


def _ms(value: str, unit: str) -> float:
    return float(value) * (1000.0 if unit.lower() == "s" else 1.0)


def press_lengths(s: Scenario) -> list[float]:
    """Length of every settled press (an event away from the idle level, then the one back), in ms."""
    out: list[float] = []
    for d in s.digital:
        pressed_at: Optional[float] = None
        for e in sorted(d.events, key=lambda e: e.t_ms):
            if e.value != d.initial:
                pressed_at = e.t_ms
            elif pressed_at is not None:
                out.append(e.t_ms - pressed_at)
                pressed_at = None
    return out


def _bounces(s: Scenario) -> list[tuple[float, int]]:
    return [(e.bounce_ms, e.bounce_count) for d in s.digital for e in d.events if e.bounce_ms and e.bounce_count]


def _stated_ranges(spec: DeviceSpec) -> dict[str, tuple[float, float]]:
    """Physical ranges the spec states for an analog pin, in mV. Needs a range word in the sentence ("range", "spans", "measures")
    so that a threshold band such as "between 80 and 90 cm" is not mistaken for the sensor's range."""
    out: dict[str, tuple[float, float]] = {}
    sentences = _SENTENCE_SPLIT.split(spec.behaviour or "")
    for pin in spec.pins:
        if pin.type != "analog_input":
            continue
        _, _, unit = pin.parsed_scale()
        if unit == "mV" and "mV" not in pin.scale:
            continue
        unit_re = re.escape(unit)
        pair = re.compile(rf"{_NUM}\s*(?:to|–|—|-|and)\s*{_NUM}\s*{unit_re}(?![A-Za-z])", re.IGNORECASE)
        best: Optional[tuple[float, float]] = None
        for sentence in sentences:
            if not _RANGE_WORDS.search(sentence):
                continue
            for lo, hi in pair.findall(sentence):
                a, b = spec.to_mv(pin.pin, float(lo)), spec.to_mv(pin.pin, float(hi))
                a, b = max(0.0, min(a, b)), min(VCC_MV, max(a, b))
                if b > a and (best is None or b - a > best[1] - best[0]):
                    best = (a, b)
        if best is not None:
            out[pin.pin] = best
    return out


def stated_limits(spec: DeviceSpec, scenarios: list[Scenario]) -> Limits:
    """The limits for this run: the spec's stated numbers where it gives them, else what the run's own scenarios already use."""
    limits = Limits()
    text = spec.behaviour or ""

    ranges = _stated_ranges(spec)
    for pin in spec.inputs():
        if pin.type == "analog_input":
            limits.analog_mv[pin.pin] = ranges.get(pin.pin, (0.0, VCC_MV))
            if pin.pin in ranges:
                limits.stated.append(f"{pin.pin} range")

    presses = [length for s in scenarios for length in press_lengths(s)]
    stated_press = [_ms(v, u) for rx in _MIN_PRESS for v, u in rx.findall(text)]
    if stated_press:
        limits.min_press_ms = max(stated_press)
        limits.stated.append("minimum press")
    elif presses:
        limits.min_press_ms = min(presses)

    bounces = [b for s in scenarios for b in _bounces(s)]
    stated_bounce = [_ms(v, u) for v, u in _MAX_BOUNCE.findall(text)]
    if stated_bounce:
        limits.max_bounce_ms = min(stated_bounce)
        limits.stated.append("maximum bounce")
    elif bounces:
        limits.max_bounce_ms = max(ms for ms, _ in bounces)
    # The spec rarely counts bounces, so the count always comes from the scenarios the run already used.
    limits.max_bounce_count = max((n for _, n in bounces), default=0)

    stated_noise = [float(v) for v in _MAX_NOISE.findall(text)]
    if stated_noise:
        limits.max_noise_mv = min(stated_noise)
        limits.stated.append("maximum noise")
    else:
        limits.max_noise_mv = max((a.noise_mv for s in scenarios for a in s.analog), default=0.0)
    return limits


def out_of_range(variant: Scenario, parent: Optional[Scenario], limits: Limits) -> list[str]:
    """Reasons a variant is not within the spec's stated ranges. Empty means gate (c) passes.

    A variant may not be harsher than the limit, but whatever the parent scenario already did is allowed, because
    the parent is the agent's own scenario. Levels the parent already had are not checked against the range either.
    """
    why: list[str] = []
    parent_analog = {a.pin: a for a in (parent.analog if parent else [])}
    for a in variant.analog:
        lo, hi = limits.analog_mv.get(a.pin, (0.0, VCC_MV))
        old = parent_analog.get(a.pin)
        known = {round(p.mv, 3) for p in old.segments} | {round(sp.mv, 3) for sp in old.spikes} if old else set()
        for mv in sorted({p.mv for p in a.segments} | {sp.mv for sp in a.spikes}):
            if round(mv, 3) not in known and not lo <= mv <= hi:
                why.append(f"{a.pin} goes to {mv:.0f} mV, outside the {lo:.0f} to {hi:.0f} mV range")
                break
        allowed_noise = max(limits.max_noise_mv, old.noise_mv if old else 0.0)
        if a.noise_mv > allowed_noise:
            why.append(f"{a.pin} noise of {a.noise_mv:.0f} mV is more than the {allowed_noise:.0f} mV the spec or the other scenarios allow")

    parent_press = press_lengths(parent) if parent else []
    shortest = min([x for x in (limits.min_press_ms, min(parent_press, default=None)) if x is not None], default=None)
    for length in press_lengths(variant):
        if shortest is None:
            why.append("a press has no stated or observed length to compare with")
            break
        if length < shortest - 1e-6:
            why.append(f"a press of {length:.0f} ms is shorter than the {shortest:.0f} ms the spec or the other scenarios use")
            break

    parent_bounce = _bounces(parent) if parent else []
    allowed_ms = max(limits.max_bounce_ms, max((ms for ms, _ in parent_bounce), default=0.0))
    allowed_n = max(limits.max_bounce_count, max((n for _, n in parent_bounce), default=0))
    for ms, n in _bounces(variant):
        if ms > allowed_ms + 1e-6:
            why.append(f"contact bounce of {ms:.0f} ms is longer than the {allowed_ms:.0f} ms the spec or the other scenarios use")
            break
        if n > allowed_n:
            why.append(f"{n} bounces are more than the {allowed_n} the other scenarios use")
            break
    return why


def passes_in_every_room(assertion_id: str, scenario_id: str, rooms: list[dict[str, list[AssertionResult]]]) -> tuple[bool, str]:
    """Gate (b): the check passed in this scenario in every clean room, and there are at least REQUIRED_ROOMS of them."""
    if len(rooms) < REQUIRED_ROOMS:
        return False, f"only {len(rooms)} clean room{'s' if len(rooms) != 1 else ''} built, and the search needs {REQUIRED_ROOMS}"
    for number, room in enumerate(rooms, 1):
        result = next((r for r in room.get(scenario_id, []) if r.assertion_id == assertion_id), None)
        if result is None:
            return False, f"clean room {number} did not run this scenario"
        if result.status == "fail":
            return False, f"clean room {number} fails it too: {result.evidence[:160]}"
        if result.status != "pass":
            return False, f"clean room {number} did not exercise the check in this scenario"
    return True, ""
