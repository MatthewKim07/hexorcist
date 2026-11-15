"""Clean-room cross-check: tell a firmware bug from a check that no correct firmware could pass.

A model writes the assertions from the spec. When one of them is wrong (it misreads the spec), a correct
sketch fails it too. So a second implementation, written from the spec and pin map alone and never shown
the uploaded sketch, is run through the same scenarios and assertions. An assertion that fails on the
uploaded firmware and fails the same way on the clean-room one is "unconfirmed": most likely the check or
the spec is ambiguous, not the firmware. Everything here is deterministic. The model only writes the sketch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from .models import AssertionResult, Violation

# An assertion is unconfirmed only if EVERY clean-room sketch fails it the same way in at least this share of the
# scenarios where it fails on the uploaded firmware. One clean room can be wrong itself (it misreads the spec, or
# implements the bug), and that must not hide a real bug, so two independent sketches have to agree.
MIN_SHARED_SHARE = 0.8
# Violation windows that start this close still count as the same stretch of time.
SLACK_MS = 150.0
# A violation window must be covered at least this much by the other firmware's windows to count as the same way.
MIN_OVERLAP_SHARE = 0.5

# These types report violations as stretches of time, so "the same way" means the same stretches.
# The others (serial text, crashes, silence) have no timing that two correct implementations would share, so they must
# fail the same kind of way: nothing seen at all, or something seen and wrong.
TIMED_TYPES = frozenset({"output_follows", "safe_state_on_fault", "max_toggles", "timed_pulse", "toggle_per_press"})


@dataclass
class Verdict:
    """What the clean-room runs say about one assertion that fails on the uploaded firmware."""

    assertion_id: str
    unconfirmed: bool
    failing: list[str] = field(default_factory=list)  # scenarios where the uploaded firmware fails it
    shared: list[str] = field(default_factory=list)  # of those, where the first clean room also fails it the same way
    user_evidence: str = ""
    cleanroom_evidence: str = ""  # from the first clean room, for the report
    scenario_id: str = ""  # the scenario the measurements come from
    # One entry per clean room that ran: how many of the failing scenarios it shares, and its measurement.
    rooms: list[dict] = field(default_factory=list)


def _covered_share(user: list[Violation], other: list[Violation]) -> float:
    """Share of the uploaded firmware's violation time that the other firmware's violations also cover."""
    if not user:
        return 1.0 if other else 0.0
    spans = sorted((v.t_start - SLACK_MS, v.t_end + SLACK_MS) for v in other)
    total = 0.0
    covered = 0.0
    for v in user:
        start, end = v.t_start, max(v.t_end, v.t_start + 1.0)
        total += end - start
        for s, e in spans:
            overlap = min(end, e) - max(start, s)
            if overlap > 0:
                covered += overlap
    return min(1.0, covered / total) if total else 0.0


def _silent(r: AssertionResult) -> bool:
    """The failure is that nothing matching was seen at all (no serial line to measure), not that what was seen was off."""
    return r.metrics.get("matches") == 0 or r.metrics.get("checked") == 0


def same_way(user: AssertionResult, clean: Optional[AssertionResult]) -> bool:
    """True when the clean-room firmware fails this assertion in this scenario as the uploaded firmware does."""
    if clean is None or user.status != "fail" or clean.status != "fail":
        return False
    if user.type not in TIMED_TYPES:
        # Text and crash checks have no timing to compare, but "printed nothing" and "printed it wrongly" are different
        # failures: a firmware that never prints the line is not failing the way one that prints it too slowly is.
        return _silent(user) == _silent(clean) and user.metrics.get("exit_reason") == clean.metrics.get("exit_reason")
    if not user.violations or not clean.violations:
        return True
    return _covered_share(user.violations, clean.violations) >= MIN_OVERLAP_SHARE


def classify(
    user_results: dict[str, list[AssertionResult]],
    clean_results: Union[dict[str, list[AssertionResult]], list[dict[str, list[AssertionResult]]]],
    scenario_order: Optional[list[str]] = None,
    assertion_ids: Optional[set[str]] = None,
) -> dict[str, Verdict]:
    """Verdict for every assertion that fails somewhere on the uploaded firmware.

    user_results maps scenario id to that scenario's results. clean_results is one such mapping per clean-room
    sketch (a single mapping is one room). With no room at all, nothing can be unconfirmed.
    An assertion is unconfirmed when every room fails it the same way in at least MIN_SHARED_SHARE of the scenarios
    where the uploaded firmware fails it. With one room (the other did not compile) the same share applies to it alone.
    """
    rooms = [clean_results] if isinstance(clean_results, dict) else list(clean_results)
    order = {sid: i for i, sid in enumerate(scenario_order or [])}
    by_room = [{(r.assertion_id, sid): r for sid, rs in room.items() for r in rs} for room in rooms]
    failing: dict[str, list[tuple[str, AssertionResult]]] = {}
    for sid, rs in user_results.items():
        for r in rs:
            if r.status == "fail" and (assertion_ids is None or r.assertion_id in assertion_ids):
                failing.setdefault(r.assertion_id, []).append((sid, r))

    verdicts: dict[str, Verdict] = {}
    for aid, rows in failing.items():
        rows.sort(key=lambda row: (-len(row[1].violations), order.get(row[0], 0)))
        shared_by_room = [[(sid, r) for sid, r in rows if same_way(r, room.get((aid, sid)))] for room in by_room]
        unconfirmed = bool(by_room) and all(len(s) * 100 >= round(MIN_SHARED_SHARE * 100) * len(rows) and len(s) > 0 for s in shared_by_room)
        # Quote one scenario for every measurement, so a reader can compare like with like: one all rooms share if any.
        common = [sid for sid, _ in rows if all(sid in {x for x, _ in s} for s in shared_by_room)] if by_room else []
        sid = common[0] if common else (shared_by_room[0][0][0] if by_room and shared_by_room[0] else rows[0][0])
        user_row = next(r for s, r in rows if s == sid)
        evidence = [room[(aid, sid)].evidence if (aid, sid) in room else "" for room in by_room]
        verdicts[aid] = Verdict(
            assertion_id=aid,
            unconfirmed=unconfirmed,
            failing=[s for s, _ in rows],
            shared=[s for s, _ in shared_by_room[0]] if shared_by_room else [],
            user_evidence=user_row.evidence,
            cleanroom_evidence=evidence[0] if evidence else "",
            scenario_id=sid,
            rooms=[{"shared": len(s), "share": round(len(s) / len(rows), 2), "evidence": e} for s, e in zip(shared_by_room, evidence)],
        )
    return verdicts


def unconfirmed_ids(verdicts: dict[str, Verdict]) -> set[str]:
    return {aid for aid, v in verdicts.items() if v.unconfirmed}
