"""Validate every case's ground truth in the sandbox (no LLM).

Run from repo root:
  backend/.venv/bin/python -m bench.validate [--fix-drop] [case_id ...]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

from bench import case_io
from bench.case_io import add_dir_option, apply_dir_option, load_case, list_case_ids, write_json
from bench.evaluate_gt import build_spec, default_runner, load_assertions, load_scenarios, run_firmware


def validate_one(runner, case_id: str) -> dict:
    case = load_case(case_id)
    spec = build_spec(case)
    assertions = load_assertions(case)
    scenarios = load_scenarios(case)
    if not scenarios:
        return {"id": case_id, "ok": False, "error": "no scenarios"}

    truth_ids = case.truth_check_ids
    # Assertions that participate in truth matching (exclude no_crash unless listed)
    tracked = {a.id for a in assertions if a.type != "no_crash" or a.id in truth_ids}

    buggy = run_firmware(runner, case.sketch, spec, assertions, scenarios, f"{case_id}:sketch")
    if not buggy["compile_ok"]:
        return {"id": case_id, "ok": False, "error": "sketch compile failed", "log": buggy["compile_log"][:500]}

    ref = run_firmware(runner, case.reference, spec, assertions, scenarios, f"{case_id}:ref")
    if not ref["compile_ok"]:
        return {"id": case_id, "ok": False, "error": "reference compile failed", "log": ref["compile_log"][:500]}

    sketch_fail = set(buggy["failing_ids"]) & tracked
    ref_fail = set(ref["failing_ids"]) & tracked

    problems: list[str] = []
    if case.is_correct:
        if sketch_fail:
            problems.append(f"correct case sketch failed {sorted(sketch_fail)}")
        if case.sketch.strip() != case.reference.strip():
            problems.append("correct case sketch != reference")
    else:
        if sketch_fail != truth_ids:
            problems.append(f"sketch failing {sorted(sketch_fail)} != truth {sorted(truth_ids)}")
        if ref_fail:
            problems.append(f"reference failed {sorted(ref_fail)}")

    # Every truth check id must exist
    known = {a.id for a in assertions}
    missing = truth_ids - known
    if missing:
        problems.append(f"truth check_ids missing from checks.json: {sorted(missing)}")

    cats = [b.get("category", "?") for b in case.truth] or ["correct"]
    return {
        "id": case_id,
        "ok": not problems,
        "categories": cats,
        "sketch_fail": sorted(sketch_fail),
        "ref_fail": sorted(ref_fail),
        "truth": sorted(truth_ids),
        "problems": problems,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--fix-drop", action="store_true", help="Move failing cases to bench/cases/_dropped/")
    add_dir_option(ap)
    args = ap.parse_args()
    apply_dir_option(args)

    ids = args.cases or list_case_ids()
    runner = default_runner()
    rows = []
    for cid in ids:
        print(f"== {cid} ==")
        row = validate_one(runner, cid)
        rows.append(row)
        if row["ok"]:
            print(f"  OK  cats={row['categories']}")
        else:
            print(f"  FAIL {row.get('problems') or row.get('error')}")

    ok = [r for r in rows if r["ok"]]
    bad = [r for r in rows if not r["ok"]]
    cat_counts: Counter[str] = Counter()
    for r in ok:
        for c in r["categories"]:
            cat_counts[c] += 1

    if args.fix_drop and bad:
        drop = case_io.CASES_DIR / "_dropped"
        drop.mkdir(exist_ok=True)
        for r in bad:
            src = case_io.CASES_DIR / r["id"]
            dst = drop / r["id"]
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(src), str(dst))
                print(f"dropped {r['id']} -> {dst}")

    summary = {
        "ok": len(ok),
        "failed": len(bad),
        "failed_ids": [r["id"] for r in bad],
        "per_category": dict(sorted(cat_counts.items())),
        "rows": rows,
    }
    out = _ROOT / "bench" / "results" / ("validate_latest.json" if case_io.CASES_DIR == case_io.FROZEN_DIR else f"validate_{case_io.CASES_DIR.name}_latest.json")
    write_json(out, summary)
    print(f"\n{len(ok)} ok, {len(bad)} failed")
    print("per category:", json.dumps(summary["per_category"], indent=2))
    print(f"wrote {out}")
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
