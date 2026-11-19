"""How a Hexorcist run is summarised in a bench row when the spec-coverage step was on."""
from __future__ import annotations


def coverage_row(cov: dict | None) -> dict | None:
    """What the spec-coverage step did on one run, without the per-bullet detail. None when the step was off."""
    if not cov:
        return None
    return {
        "uncovered": cov.get("uncovered") or [],
        "bullets": len(cov.get("bullets") or []),
        "called": bool(cov.get("called")),
        "proposed": cov.get("proposed") or 0,
        "added": cov.get("added") or [],
        "rejected": cov.get("rejected") or [],
        "dropped": cov.get("dropped") or [],
        "displaced": cov.get("displaced") or [],
        "error": cov.get("error") or "",
    }
