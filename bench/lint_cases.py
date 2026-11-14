"""Lint frozen benchmark cases: no bug-hinting words; every check covers a spec bullet.

Run from repo root:
  backend/.venv/bin/python -m bench.lint_cases
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bench.case_io import CASES_DIR, list_case_ids, load_case

FORBIDDEN = re.compile(
    r"\b(bug|wrong|oops|fixme|todo|should|incorrect|broken|hack)\b",
    re.IGNORECASE,
)

BULLET_RE = re.compile(r"^\s*[-*•]\s+(.*\S)\s*$", re.MULTILINE)


def spec_bullets(spec: str) -> list[str]:
    return [m.group(1).strip() for m in BULLET_RE.finditer(spec)]


def lint_case(case_id: str) -> list[str]:
    case = load_case(case_id)
    problems: list[str] = []

    for label, text in (("sketch", case.sketch), ("reference", case.reference)):
        for i, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                problems.append(f"{case_id}/{label}.ino:{i}: forbidden word in {line.strip()!r}")

    bullets = spec_bullets(case.spec)
    if len(bullets) < 4:
        problems.append(f"{case_id}/spec.md: need at least 4 bullets, found {len(bullets)}")
    if len(bullets) > 12:
        problems.append(f"{case_id}/spec.md: too many bullets ({len(bullets)}); keep 4–10")

    nonblank = [ln for ln in case.sketch.splitlines() if ln.strip()]
    if len(nonblank) < 35:
        problems.append(f"{case_id}/sketch.ino: {len(nonblank)} non-blank lines (min 35)")

    for a in case.checks.get("assertions") or []:
        if a.get("type") == "no_crash":
            continue
        covers = a.get("covers")
        if not covers or not str(covers).strip():
            problems.append(f"{case_id}/checks.json: assertion {a.get('id')} missing covers")
            continue
        cover = str(covers).strip()
        if not any(cover in b or b in cover for b in bullets):
            # Also allow covers to be an exact bullet substring match after normalizing spaces
            norm = {re.sub(r"\s+", " ", b).lower(): b for b in bullets}
            key = re.sub(r"\s+", " ", cover).lower()
            if key not in norm and not any(key in k or k in key for k in norm):
                problems.append(
                    f"{case_id}/checks.json: assertion {a.get('id')} covers={cover!r} "
                    f"matches no spec bullet"
                )

    return problems


def main() -> None:
    ids = sys.argv[1:] or list_case_ids()
    if not ids:
        print("no cases under bench/cases/")
        sys.exit(1)
    all_problems: list[str] = []
    for cid in ids:
        probs = lint_case(cid)
        if probs:
            all_problems.extend(probs)
            print(f"FAIL {cid}: {len(probs)} issue(s)")
            for p in probs:
                print(f"  {p}")
        else:
            print(f"OK   {cid}")
    print(f"\n{len(ids) - len({p.split('/')[0] for p in all_problems})} ok, "
          f"{len({p.split('/')[0] for p in all_problems})} failed")
    sys.exit(1 if all_problems else 0)


if __name__ == "__main__":
    main()
