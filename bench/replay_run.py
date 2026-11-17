"""Reference replay for a Hexorcist benchmark run: who is wrong when a check fails?

For every case in <run>_hexorcist.json this takes the run's own assertions and scenarios (from the live API) and runs
the case's known-good reference.ino through them with the current assertion engine. A check that fails on the
reference is a check no correct firmware can pass (class B: the model misread the spec, or the evaluator is wrong).
Writes bench/results/<run>_replay.json.

Usage: backend/.venv/bin/python -m bench.replay_run RUN_ID [--api URL] [case_id ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.assertions import evaluate_all  # noqa: E402
from app.models import Assertion, DeviceSpec, Scenario  # noqa: E402
from bench.case_io import RESULTS_DIR, add_dir_option, apply_dir_option, load_case, write_json  # noqa: E402
from bench.evaluate_gt import default_runner  # noqa: E402

ADAPTER = TypeAdapter(Assertion)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--api", default="http://127.0.0.1:8080")
    add_dir_option(ap)
    args = ap.parse_args()
    apply_dir_option(args)

    rows = {r["case_id"]: r for r in json.loads((RESULTS_DIR / f"{args.run_id}_hexorcist.json").read_text())["cases"]}
    out_path = RESULTS_DIR / f"{args.run_id}_replay.json"
    out = json.loads(out_path.read_text()) if out_path.is_file() else {}
    runner = default_runner()
    with httpx.Client(base_url=args.api, timeout=60) as client:
        for cid in args.cases or list(rows):
            if cid in out:
                continue
            report = client.get(f"/api/runs/{rows[cid]['run_id']}").json().get("report") or {}
            if not report.get("assertions"):
                out[cid] = {"skipped": "no assertions in the report", "assertions": {}}
                continue
            case = load_case(cid)
            spec = DeviceSpec.model_validate(report["spec"])
            assertions = [ADAPTER.validate_python({k: v for k, v in a.items() if k != "unconfirmed"}) for a in report["assertions"]]
            scenarios = [Scenario.model_validate(s) for s in report["scenarios"]]
            built = runner.compile(case.reference, f"replay {cid}")
            if not built.ok:
                out[cid] = {"skipped": "reference did not compile", "assertions": {}}
                continue

            def one(s: Scenario):
                return s, evaluate_all(assertions, runner.run(built.elf, s.harness_json(), s.id).trace, s, spec)

            with ThreadPoolExecutor(max_workers=4) as pool:
                runs = list(pool.map(one, scenarios))
            per: dict[str, dict] = {a.id: {"ref_fail": [], "ref_exercised": 0} for a in assertions}
            for s, results in runs:
                for r in results:
                    if r.status != "not_exercised":
                        per[r.assertion_id]["ref_exercised"] += 1
                    if r.status == "fail":
                        per[r.assertion_id]["ref_fail"].append(s.id)
            out[cid] = {"scenarios": len(scenarios), "assertions": per}
            write_json(out_path, out)
            print(cid, {a: len(v["ref_fail"]) for a, v in per.items() if v["ref_fail"]}, flush=True)
    write_json(out_path, out)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
