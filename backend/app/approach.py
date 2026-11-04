"""Tell when a patch goes back to an approach the emulator already disproved.

A disproven attempt is one that was tested and is not the best patch so far. Machinery the best
patch still uses is not disproven, so refining the best patch is always allowed: only what the
best patch dropped counts, measured two ways.

Before running: the candidate reintroduces the named machinery or the code shape of that attempt.
After running: the emulator measures the same failures as that attempt, which also catches renames.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?[A-Za-z]*\b")

# Language and Arduino words, plus names every patch tends to use whatever its approach.
_COMMON = frozenset(
    """
    if else for while do switch case break continue return const static volatile void bool boolean
    int long unsigned short float double char byte true false sizeof uint8_t uint16_t uint32_t
    int8_t int16_t int32_t size_t HIGH LOW INPUT OUTPUT INPUT_PULLUP pinMode digitalRead digitalWrite
    analogRead analogWrite millis micros delay delayMicroseconds Serial begin print println available
    setup loop now i j k n
    """.split()
)

MIN_NAMES = 2
NAME_OVERLAP = 0.6
MIN_SHAPES = 5
SHAPE_OVERLAP = 0.8
SHORTEST_SHAPE = 12
FAILURE_OVERLAP = 0.8


@dataclass
class Attempt:
    """A patch the emulator has judged."""

    n: int
    code: str
    summary: str = ""
    failing: set[tuple[str, str]] = field(default_factory=set)


@dataclass
class Reversion:
    attempt: int
    reason: str


def _clean(code: str) -> str:
    return _STRING_RE.sub('""', _COMMENT_RE.sub("", code))


def _canonical(code: str) -> str:
    return re.sub(r"\s+", "", _clean(code))


def identifiers(code: str) -> set[str]:
    """Names the code uses, leaving out the language, the Arduino core and generic names."""
    return {name for name in _IDENT_RE.findall(_clean(code)) if name not in _COMMON}


def shapes(code: str) -> set[str]:
    """Lines with names and numbers blanked out, so renaming does not hide a repeated structure."""
    out: set[str] = set()
    for line in _clean(code).splitlines():
        compact = re.sub(r"\s+", "", _NUMBER_RE.sub("N", line))
        blanked = _IDENT_RE.sub(lambda m: m.group(0) if m.group(0) in _COMMON else "X", compact)
        if len(blanked) >= SHORTEST_SHAPE:
            out.add(blanked)
    return out


def find_code_reversion(candidate: str, disproven: list[Attempt], best_code: Optional[str], original: str) -> Optional[Reversion]:
    """Return the disproven attempt this code goes back to, judged from the code alone."""
    base_names = identifiers(original) | identifiers(best_code or "")
    base_shapes = shapes(original) | shapes(best_code or "")
    names = identifiers(candidate) - base_names
    candidate_shapes = shapes(candidate) - base_shapes
    canonical = _canonical(candidate)

    for attempt in disproven:
        if canonical == _canonical(attempt.code):
            return Reversion(attempt.n, f"It is the same code as attempt {attempt.n}.")
        old_names = identifiers(attempt.code) - base_names
        if len(old_names) >= MIN_NAMES:
            shared = old_names & names
            if len(shared) / len(old_names) >= NAME_OVERLAP:
                return Reversion(attempt.n, f"It brings back the machinery of attempt {attempt.n}: {', '.join(sorted(shared))}.")
        old_shapes = shapes(attempt.code) - base_shapes
        if len(old_shapes) >= MIN_SHAPES and len(old_shapes & candidate_shapes) / len(old_shapes) >= SHAPE_OVERLAP:
            return Reversion(attempt.n, f"It has the same code structure as attempt {attempt.n}.")
    return None


def find_measured_reversion(failing: set[tuple[str, str]], disproven: list[Attempt]) -> Optional[Reversion]:
    """Return the disproven attempt whose measured failures this patch repeats."""
    for attempt in disproven:
        if not failing or not attempt.failing:
            continue
        overlap = len(failing & attempt.failing) / len(failing | attempt.failing)
        if overlap >= FAILURE_OVERLAP:
            return Reversion(attempt.n, f"The emulator measured the same failures as attempt {attempt.n} ({len(failing & attempt.failing)} shared of {len(failing | attempt.failing)}).")
    return None
