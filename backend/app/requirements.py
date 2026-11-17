"""Requirement grounding: an assertion may only demand what the spec bullet it quotes actually asks for.

grounding.py proves that an assertion's `spec_quote` occurs in the spec. This module asks the next question, with plain
string matching and arithmetic and no model: does the check ask for more, or for something other, than that bullet?
The benchmark shows the model does this in a few repeatable ways, so each is a named rule (a rule for a bullet that
names two inputs while the check uses one was tried and left out: on the dev runs it removed one real detection):

  rate_limit          a toggle limit (max_toggles) needs a bullet about toggling, chatter or a rate, and the count and
                      window it states must be the spec's.
  hysteresis_band     a check with two different thresholds on one analog input needs both numbers in the spec.
  debounce            "each press toggles once" needs a bullet about toggling, and its settle time may not be shorter
                      than the debounce window the spec states (a longer one only makes the check more lenient).
  range_bound         "outside A to B": a condition that keeps one bound and covers the far side of the other one
                      (`>= A` must be LOW) contradicts the bullet above B.
  invented_converse   "while D2 is held LOW, force the heater ON" says nothing about the released button, so a state
                      demanded for the released button is invented unless the bullet mentions a release or "otherwise".
                      Only a bullet that forces or overrides is judged: "lit while held" does imply "dark when not".

An assertion that fails a rule is not deleted. The agent marks it "ungrounded requirement", keeps it out of the bugs,
the fix loop and the verification, and shows it with its reason. An assertion without a spec_quote (the weak fallback
checks, or checks a user supplied) is not judged: there is no bullet to compare with.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .grounding import words
from .models import DeviceSpec, MaxToggles, OutputFollows, TogglePerPress

_SIMPLE = str.maketrans({"\u2212": "-", "\u2013": "-", "\u2014": "-", "\u00a0": " "})
_NUM = r"[-+]?\d+(?:\.\d+)?"
_UNIT = r"(?:ms|msec|milliseconds?|s|sec|secs|seconds?|min|mins|minutes?)"
_DURATION = re.compile(rf"(?<![\w.])({_NUM})\s*({_UNIT})\b", re.IGNORECASE)
_PER_UNIT = re.compile(r"\b(?:per|each|every|a)\s+(second|minute)\b", re.IGNORECASE)
_NUMBER_WORDS = {"once": 1, "twice": 2, "thrice": 3, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "never": 0, "zero": 0}
_WORD_NUMBER = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)

# The explicit phrase lists. One list per requirement class, matched against the bullet the quote comes from.
TOGGLE_WORDS = re.compile(
    r"\b(toggl\w*|chatter\w*|flicker\w*|flutter\w*|short-?cycl\w*|cycl(?:e|es|ing)|oscillat\w*|flip\w*|bounc\w*|frequen\w*|rate"
    r"|chang(?:e|es|ing)\s+(?:its\s+)?state|switch(?:es|ing)?)\b",
    re.IGNORECASE,
)
PRESS_TOGGLE_WORDS = re.compile(r"\b(toggl\w*|flip\w*|alternat\w*|each press|every press|per press|one press|once per)\b", re.IGNORECASE)
RELEASE_WORDS = re.compile(
    r"\b(releas\w*|unpress\w*|not\s+(?:pressed|held|active|asserted)|idle|rest(?:ing)?|open(?:ed)?|otherwise|else|elsewhere"
    r"|no longer|until|unless|when\s+not|stops?|ends?|deassert\w*|inactive|off|clears?|cleared|let go|lifted)\b",
    re.IGNORECASE,
)
OVERRIDE_WORDS = re.compile(r"\b(forc\w*|overrid\w*|regardless|irrespective|latch\w*|takes? priority|supersed\w*)\b", re.IGNORECASE)
_DEBOUNCE_WINDOW = [
    re.compile(rf"(?:debounce\w*|settl\w*|stab\w*)[^.;:\n]{{0,30}}?({_NUM})\s*({_UNIT})\b", re.IGNORECASE),
    re.compile(rf"({_NUM})\s*({_UNIT})\s+(?:debounce|settl\w*|stab\w*)", re.IGNORECASE),
]
_RANGE = re.compile(
    rf"\b(?:outside|inside|within|between|beyond|out of)\b[^0-9+\-]{{0,40}}?({_NUM})\s*(?:to|and|through|-|\.\.|\u2026)\s*({_NUM})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Ungrounded:
    rule: str
    reason: str


def _plain(text: str) -> str:
    return (text or "").translate(_SIMPLE)


def bullets(spec_text: str) -> list[str]:
    return [re.sub(r"^\s*[-*\u2022]\s*", "", ln).strip() for ln in _plain(spec_text).splitlines() if ln.strip()]


def bullet_of(quote: str, spec_text: str) -> str:
    """The spec bullet that holds the quote: the one sharing most of its words. The quote itself when none does."""
    q = set(words(quote))
    best, hits = "", 0
    for b in bullets(spec_text):
        n = len(q & set(words(b)))
        if n > hits:
            best, hits = b, n
    return best if hits else _plain(quote)


def durations_ms(text: str) -> list[float]:
    """Every duration in the text, in ms: '5000 ms', '5 s', '2 minutes', 'per second'."""
    scale = {"ms": 1, "msec": 1, "s": 1000, "sec": 1000, "secs": 1000, "min": 60000, "mins": 60000}
    out = []
    for value, unit in _DURATION.findall(_plain(text)):
        u = unit.lower()
        factor = scale.get(u) or (1 if u.startswith("milli") else 1000 if u.startswith("second") else 60000)
        out.append(float(value) * factor)
    out += [1000.0 if m.lower() == "second" else 60000.0 for m in _PER_UNIT.findall(_plain(text))]
    return out


def counts(text: str) -> list[float]:
    """Counts that are not durations: '2 times', 'twice', 'once'."""
    plain = _DURATION.sub(" ", _plain(text))
    nums = [float(n) for n in re.findall(rf"(?<![\w.]){_NUM}(?![\w.])", plain)]
    return nums + [float(_NUMBER_WORDS[w.lower()]) for w in _WORD_NUMBER.findall(plain)]


def numbers(text: str) -> list[float]:
    return [float(n) for n in re.findall(rf"(?<![\w.]){_NUM}", _plain(text))]


def _near(value: float, pool: list[float]) -> bool:
    return any(abs(value - x) <= max(1e-6, abs(x) * 1e-6) for x in pool)


def _in_spec(value: float, spec_text: str) -> bool:
    """A threshold is the spec's when it, its magnitude, or the same value in the other of mV and V is written there."""
    pool = numbers(spec_text)
    return any(_near(c, pool) for c in (value, abs(value), value * 1000, value / 1000))


def _fmt(x: float) -> str:
    return f"{x:g}"


def _rate_limit(a: MaxToggles, bullet: str, quote: str) -> Optional[Ungrounded]:
    if not TOGGLE_WORDS.search(bullet):
        return Ungrounded("rate_limit", f"it limits {a.pin} to {a.max_toggles} change(s) in {_fmt(a.window_ms)} ms, but its spec bullet says nothing about toggling, chatter or a rate")
    # Numbers come from the quoted clause only: a bullet can hold other clauses with durations of their own.
    windows, stated = durations_ms(quote), counts(quote)
    if windows and not _near(a.window_ms, windows):
        return Ungrounded("rate_limit", f"its window of {_fmt(a.window_ms)} ms is not in the quoted clause, which gives {', '.join(_fmt(w) + ' ms' for w in windows)}")
    if stated and not _near(float(a.max_toggles), stated):
        return Ungrounded("rate_limit", f"its limit of {a.max_toggles} is not in the quoted clause, which gives {', '.join(_fmt(c) for c in stated)}")
    return None


def _hysteresis_band(a: OutputFollows, spec: DeviceSpec) -> Optional[Ungrounded]:
    hi, lo = a.high_when, a.low_when
    if hi is None or lo is None or hi.pin != lo.pin or hi.value == lo.value or not hi.pin.startswith("A"):
        return None
    missing = [v for v in (hi.value, lo.value) if not _in_spec(v, spec.behaviour)]
    if missing:
        return Ungrounded("hysteresis_band", f"it needs a band of {_fmt(lo.value)} and {_fmt(hi.value)} on {hi.pin}, and {', '.join(_fmt(v) for v in missing)} is not a number in the spec")
    return None


def _debounce(a: TogglePerPress, spec: DeviceSpec, bullet: str) -> Optional[Ungrounded]:
    if not PRESS_TOGGLE_WORDS.search(bullet):
        return Ungrounded("debounce", f"it demands exactly one toggle per press of {a.input_pin}, but its spec bullet does not say the output toggles")
    if "settle_ms" in a.model_fields_set:
        stated = [d for rx in _DEBOUNCE_WINDOW for m in rx.findall(_plain(spec.behaviour)) for d in durations_ms(f"{m[0]} {m[1]}")]
        if stated and a.settle_ms < min(stated) - 1e-6:
            return Ungrounded("debounce", f"its settle time of {_fmt(a.settle_ms)} ms is shorter than the {_fmt(min(stated))} ms the spec states, so it demands a toggle for presses the spec lets the firmware ignore")
    return None


def _region_has(op: str, edge: float, point: float) -> bool:
    """Is `point` inside the half-line that starts at `edge` and runs the way `op` points?"""
    if op in (">", ">="):
        return point > edge
    if op in ("<", "<="):
        return point < edge
    return False


def _range_bound(a: OutputFollows, quote: str) -> Optional[Ungrounded]:
    found = _RANGE.search(_plain(quote))
    if not found:
        return None
    bounds = (float(found.group(1)), float(found.group(2)))
    for name, cond in (("high_when", a.high_when), ("low_when", a.low_when)):
        if cond is None or not cond.pin.startswith("A"):
            continue
        for edge, other in (bounds, bounds[::-1]):
            if _near(cond.value, [edge]) and _region_has(cond.op, edge, other):
                return Ungrounded("range_bound", f"its {name} `{cond.pin} {cond.op} {_fmt(cond.value)}` also covers {_fmt(other)}, the other bound of the quoted range {_fmt(bounds[0])} to {_fmt(bounds[1])}, where the bullet asks for the opposite")
    return None


def _invented_converse(a: OutputFollows, spec: DeviceSpec, bullet: str) -> Optional[Ungrounded]:
    if not OVERRIDE_WORDS.search(bullet):
        return None  # "lit while held" implies "dark when not held"; only a forcing bullet leaves the released state open
    for name, cond in (("high_when", a.high_when), ("low_when", a.low_when)):
        pin = spec.pin(cond.pin) if cond is not None else None
        if cond is None or pin is None or pin.type != "digital_input" or cond.op != "==":
            continue
        idle = 1 if pin.active_low else 0
        if int(cond.value) == idle and not RELEASE_WORDS.search(bullet):
            return Ungrounded("invented_converse", f"its {name} demands a state while {cond.pin} is released, and its spec bullet never mentions a release, an idle input or \"otherwise\"")
    return None


def check_requirement(a, spec: DeviceSpec) -> Optional[Ungrounded]:
    """Why this assertion asks for more than its bullet, or None. Types without a rule are never judged."""
    quote = getattr(a, "spec_quote", "") or ""
    if not quote.strip():
        return None
    bullet = bullet_of(quote, spec.behaviour)
    if isinstance(a, MaxToggles):
        return _rate_limit(a, bullet, quote)
    if isinstance(a, TogglePerPress):
        return _debounce(a, spec, bullet)
    if isinstance(a, OutputFollows):
        return _range_bound(a, quote) or _invented_converse(a, spec, bullet) or _hysteresis_band(a, spec)
    return None


def ungrounded_requirements(assertions: list, spec: DeviceSpec) -> dict[str, Ungrounded]:
    """assertion id -> the rule it broke. Only assertions that broke one are in the result."""
    out: dict[str, Ungrounded] = {}
    for a in assertions:
        found = check_requirement(a, spec)
        if found is not None:
            out[a.id] = found
    return out
