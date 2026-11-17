"""Clock fast-forward helpers: when a run is worth starting late, and where to start it.

The harness can start a scenario with millis() already at any value (Scenario.start_millis). That reaches behaviour a
15 s run from power-on never sees: the 32-bit rollover after 49.7 days, a 16-bit timestamp wrapping every 65.5 s, a
signed 16-bit seconds counter at 9.1 hours, an 8-bit seconds counter at 256 s. It only matters when something depends
on elapsed time, so the attack prompt offers it, and the stimulus search varies it, only then.
"""
from __future__ import annotations

import re

MAX_START_MS = 2**32 - 1

# Code that reads the clock. delay() alone does not depend on the uptime, so it does not count.
_CODE = re.compile(r"\b(?:millis|micros)\s*\(")
# A spec that talks about time passing: "every 5 s", "after 30 minutes", "uptime", "for 400 ms".
_SPEC = re.compile(
    r"\b(?:uptime|up-time|power-up|power up|since boot|timer|timeout|schedule[ds]?|elapsed)\b"
    r"|\b(?:every|each|after|for|within|per)\s+\d+(?:\.\d+)?\s*(?:ms|milliseconds?|s|sec|secs|seconds?|min|mins|minutes?|h|hours?)\b",
    re.IGNORECASE,
)

# Where the interesting wraps are, as (label, the uptime in ms at which the counter wraps).
WRAPS: tuple[tuple[str, int], ...] = (
    ("32-bit millis() rollover", 2**32),
    ("16-bit millisecond timestamp wrap", 65536 * 3),
    ("signed 16-bit seconds counter wrap", 32768 * 1000),
    ("8-bit seconds counter wrap", 256 * 1000),
)
HOURS_IN_MS = 3 * 3600 * 1000


def uses_elapsed_time(firmware: str, spec_text: str = "") -> bool:
    """True when the firmware reads millis() or micros(), or the spec describes something that happens after a time."""
    return bool(_CODE.search(firmware or "") or _SPEC.search(spec_text or ""))


def start_before_wrap(wrap_ms: int, duration_ms: float, fraction: float) -> int:
    """A start_millis that puts the wrap `fraction` of the way through a run of `duration_ms`, to the nearest 10 ms."""
    start = wrap_ms - int(round(duration_ms * fraction / 10.0)) * 10
    return max(0, min(start, MAX_START_MS))


def clamp_start(value) -> int:
    """A start_millis from model output, forced into the counter's range. Anything unreadable is a normal power-on."""
    try:
        return max(0, min(int(float(value)), MAX_START_MS))
    except (TypeError, ValueError, OverflowError):
        return 0
