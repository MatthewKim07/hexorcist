"""Replay a stored run's assertions and scenarios against known-good reference firmware.

Decides who is wrong when a run fails. The firmware here is hand-written and correct, so a
failure means the scenario, the assertion or the evaluator is unfair, not the firmware.
With --attempt, replays one of the run's own stored patches instead, to re-judge it with the
current engine.

Run from backend/: python -m scripts.replay_reference [--api URL] [--show-scenario] run_id ...
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import httpx
from pydantic import TypeAdapter

from app.assertions import evaluate_all
from app.config import load_settings
from app.models import Assertion, DeviceSpec, Scenario
from app.presets import PRESETS
from app.sandbox import SandboxRunner
from tests.fixtures import CORRECT_FIRMWARE

ADAPTER = TypeAdapter(Assertion)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8080")
    parser.add_argument("--show-scenario", action="store_true", help="Print the definition of each failing scenario")
    parser.add_argument("--attempt", type=int, default=0, help="Replay this stored patch from the run, instead of the reference firmware")
    parser.add_argument("run_ids", nargs="+")
    args = parser.parse_args()

    runner = SandboxRunner(load_settings())
    problems = 0
    with httpx.Client(base_url=args.api, timeout=60) as client:
        for run_id in args.run_ids:
            report = client.get(f"/api/runs/{run_id}").json()["report"]
            preset = next((p for p in PRESETS if p["firmware"] == report["firmware"]), None)
            if preset is None or preset["id"] not in CORRECT_FIRMWARE:
                print(f"{run_id}: no reference firmware for this upload, skipped")
                continue
            spec = DeviceSpec.model_validate(report["spec"])
            assertions = [ADAPTER.validate_python(a) for a in report["assertions"]]
            scenarios = [Scenario.model_validate(s) for s in report["scenarios"]]
            firmware = next(i["patch"] for i in report["iterations"] if i["n"] == args.attempt) if args.attempt else CORRECT_FIRMWARE[preset["id"]]
            built = runner.compile(firmware, f"replay {preset['id']}")
            if not built.ok:
                raise SystemExit(built.log)

            def run_one(scenario: Scenario):
                result = runner.run(built.elf, scenario.harness_json(), scenario.name)
                return scenario, evaluate_all(assertions, result.trace, scenario, spec)

            with ThreadPoolExecutor(max_workers=4) as pool:
                outcomes = list(pool.map(run_one, scenarios))

            failures = [(s, r) for s, results in outcomes for r in results if r.status == "fail"]
            problems += len(failures)
            print(f"\n{run_id} {preset['id']}: {f'attempt {args.attempt}' if args.attempt else 'reference firmware'}, {len(scenarios)} scenarios, {len(assertions)} assertions, {len(failures)} failures")
            for scenario, r in failures:
                by_id = next(a for a in report["assertions"] if a["id"] == r.assertion_id)
                print(f"  {r.assertion_id} {scenario.id} [{scenario.name}]: {r.evidence}")
                print(f"     assertion: {json.dumps(by_id, ensure_ascii=False)[:220]}")
                if args.show_scenario:
                    print(f"     scenario: {scenario.model_dump_json(exclude={'hypothesis'})[:900]}")
    print(f"\n{'NO FAILURES' if problems == 0 else f'{problems} FAILURE(S)'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
