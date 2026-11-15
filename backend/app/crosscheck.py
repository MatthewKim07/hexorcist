"""Clean-room cross-check: tell a firmware bug from a check that no correct firmware could pass.

A model writes the assertions from the spec. When one of them is wrong (it misreads the spec), a correct
sketch fails it too. So a second implementation, written from the spec and pin map alone and never shown
the uploaded sketch, is run through the same scenarios and assertions. An assertion that fails on the
uploaded firmware and fails the same way on the clean-room one is "unconfirmed": most likely the check or
the spec is ambiguous, not the firmware. Everything here is deterministic. The model only writes the sketch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models import AssertionResult, Violation

# An unconfirmed assertion fails the same way on the clean-room firmware in at least this share of the
# scenarios where it fails on the uploaded one. A majority, not all: a second implementation differs in detail.
MIN_SHARED_SHARE = 0.5
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
    """What the clean-room run says about one assertion that fails on the uploaded firmware."""

    assertion_id: str
    unconfirmed: bool
    failing: list[str] = field(default_factory=list)  # scenarios where the uploaded firmware fails it
    shared: list[str] = field(default_factory=list)  # of those, where the clean-room firmware fails it the same way
    user_evidence: str = ""
    cleanroom_evidence: str = ""
    scenario_id: str = ""  # the scenario the two measurements come from


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
    clean_results: dict[str, list[AssertionResult]],
    scenario_order: Optional[list[str]] = None,
    assertion_ids: Optional[set[str]] = None,
) -> dict[str, Verdict]:
    """Verdict for every assertion that fails somewhere on the uploaded firmware.

    user_results and clean_results map scenario id to that scenario's assertion results.
    """
    order = {sid: i for i, sid in enumerate(scenario_order or [])}
    clean_by = {(r.assertion_id, sid): r for sid, rs in clean_results.items() for r in rs}
    failing: dict[str, list[tuple[str, AssertionResult]]] = {}
    for sid, rs in user_results.items():
        for r in rs:
            if r.status == "fail" and (assertion_ids is None or r.assertion_id in assertion_ids):
                failing.setdefault(r.assertion_id, []).append((sid, r))

    verdicts: dict[str, Verdict] = {}
    for aid, rows in failing.items():
        rows.sort(key=lambda row: (-len(row[1].violations), order.get(row[0], 0)))
        shared = [(sid, r) for sid, r in rows if same_way(r, clean_by.get((aid, sid)))]
        unconfirmed = len(shared) >= max(1.0, MIN_SHARED_SHARE * len(rows))
        # Quote the same scenario for both measurements, so a reader can compare like with like.
        sid, user_row = shared[0] if shared else rows[0]
        clean_row = clean_by.get((aid, sid))
        verdicts[aid] = Verdict(
            assertion_id=aid,
            unconfirmed=unconfirmed,
            failing=[s for s, _ in rows],
            shared=[s for s, _ in shared],
            user_evidence=user_row.evidence,
            cleanroom_evidence=clean_row.evidence if clean_row is not None else "",
            scenario_id=sid,
        )
    return verdicts


def unconfirmed_ids(verdicts: dict[str, Verdict]) -> set[str]:
    return {aid for aid, v in verdicts.items() if v.unconfirmed}
