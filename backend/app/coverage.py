"""Spec coverage: find the spec bullets no assertion quotes, and vet the checks proposed for them.

The model writes each assertion with the spec sentence it enforces ("spec_quote"). A bullet that no quote falls inside
may simply be a wiring or scale note, or it may state a behaviour the model never wrote a check for. This module does
the plain part of that, with string matching and no model: split the spec into bullets, mark each one covered or not,
and keep only proposed checks whose quote lies inside an uncovered bullet. The extra model call itself is made by the
pipeline (agent.py); what comes back goes through the same normalization, requirement gate, scenarios, cross-check and
fix loop as every other check.
"""
from __future__ import annotations

from typing import Any

from .grounding import MIN_QUOTE_WORDS, find_quote, words
from .requirements import bullets

# At most this many new checks per uncovered bullet.
MAX_CHECKS_PER_BULLET = 2


def quote_inside(quote: str, bullet: str) -> bool:
    """True when the quoted clause occurs in the bullet (same tolerance as the spec citation check)."""
    q = words(quote or "")
    if not q:
        return False
    if len(q) < MIN_QUOTE_WORDS:
        return " " + " ".join(q) + " " in " " + " ".join(words(bullet)) + " "
    return find_quote(quote, bullet)[0]


def split_bullets(spec_text: str, assertions: list) -> list[dict]:
    """Every spec bullet with whether some assertion's spec_quote falls inside it. Bullets too short to quote are left out."""
    quotes = [(a.id, a.spec_quote) for a in assertions if getattr(a, "spec_quote", "")]
    out: list[dict] = []
    for b in bullets(spec_text):
        if len(words(b)) < MIN_QUOTE_WORDS:
            continue
        by = [aid for aid, q in quotes if quote_inside(q, b)]
        out.append({"bullet": b, "covered": bool(by), "covered_by": by})
    return out


def uncovered(split: list[dict]) -> list[str]:
    return [s["bullet"] for s in split if not s["covered"]]


def _clip(value: Any, n: int = 80) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= n else text[: n - 1] + "\u2026"


def _rejected(item: Any, reason: str) -> dict:
    """What a rejected proposal looked like when vetting saw it, so a later reader can tell why it failed."""
    if not isinstance(item, dict):
        return {"reason": reason, "quote": "", "type": "", "title": _clip(item, 40), "keys": []}
    title = item.get("id") or item.get("description") or item.get("title") or item.get("name") or ""
    return {"reason": reason, "quote": _clip(item.get("spec_quote"), 160), "type": _clip(item.get("type"), 30), "title": _clip(title), "keys": sorted(str(k) for k in item)[:20]}


def vet(raw: list[Any], uncovered_bullets: list[str]) -> tuple[list[dict], list[dict]]:
    """Keep proposed checks whose quote lies inside an uncovered bullet, at most MAX_CHECKS_PER_BULLET per bullet.

    Returns (kept, rejected). A crash check, a check with no usable quote, one quoting a covered bullet or one over the
    per-bullet limit is rejected with a reason. Anything the model put in "origin" is discarded: only this step sets it.
    """
    kept: list[dict] = []
    rejected: list[dict] = []
    per_bullet: dict[int, int] = {}
    for item in raw or []:
        if not isinstance(item, dict):
            rejected.append(_rejected(item, "not an object"))
            continue
        item = {k: v for k, v in item.items() if k != "origin"}
        quote = str(item.get("spec_quote") or "")
        if item.get("type") == "no_crash":
            rejected.append(_rejected(item, "a crash check is always present"))
            continue
        home = next((i for i, b in enumerate(uncovered_bullets) if quote_inside(quote, b)), None)
        if home is None:
            rejected.append(_rejected(item, "it has no spec_quote" if not quote.strip() else "its spec_quote is not inside an uncovered bullet"))
            continue
        if per_bullet.get(home, 0) >= MAX_CHECKS_PER_BULLET:
            rejected.append(_rejected(item, f"more than {MAX_CHECKS_PER_BULLET} checks for one bullet"))
            continue
        per_bullet[home] = per_bullet.get(home, 0) + 1
        kept.append(item)
    return kept, rejected
