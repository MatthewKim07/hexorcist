"""Run the real engine with no LLM: planted bugs must fail, correct firmware must pass.

Run from backend/: python -m scripts.check_presets [preset ...]
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

from pydantic import TypeAdapter

from app.assertions import evaluate_all
from app.config import load_settings
from app.models import Assertion, DeviceSpec, NoCrash, PinSpec
from app.presets import PRESETS
from app.sandbox import SandboxRunner
from app.scenario_lib import builtin_scenarios
from tests.fixtures import ASSERTIONS, CORRECT_FIRMWARE

ADAPTER = TypeAdapter(Assertion)


def load(preset: dict) -> tuple[DeviceSpec, list]:
    spec = DeviceSpec(pins=[PinSpec(**p) for p in preset["pins"]], behaviour=preset["behaviour"])
    assertions = [ADAPTER.validate_python(a) for a in ASSERTIONS[preset["id"]]]
    assertions.append(NoCrash())
    for i, a in enumerate(assertions):
        a.id = f"a{i + 1}"
    return spec, assertions


def suite(runner: SandboxRunner, firmware: str, spec: DeviceSpec, assertions: list, label: str) -> dict:
    built = runner.compile(firmware, label)
    if not built.ok:
        print(built.log)
        raise SystemExit(f"{label}: failed to compile")
    scenarios = builtin_scenarios(spec, assertions)

    def run_one(scenario):
        result = runner.run(built.elf, scenario.harness_json(), scenario.name)
        return scenario, result.trace, evaluate_all(assertions, result.trace, scenario, spec)

    with ThreadPoolExecutor(max_workers=4) as pool:
        return {"built": built, "runs": list(pool.map(run_one, scenarios))}


def main() -> None:
    wanted = sys.argv[1:] or list(ASSERTIONS)
    runner = SandboxRunner(load_settings())
    problems = 0
    for preset in PRESETS:
        if preset["id"] not in wanted:
            continue
        spec, assertions = load(preset)
        print(f"\n===== {preset['id']} =====")

        buggy = suite(runner, preset["firmware"], spec, assertions, f"{preset['id']} buggy")
        failed: dict[str, list] = {}
        for scenario, _trace, results in buggy["runs"]:
            for r in results:
                if r.status == "fail":
                    failed.setdefault(r.assertion_id, []).append((scenario.name, r.evidence))
        print(f"BUGGY: {len(buggy['runs'])} scenarios, {len(failed)} of {len(assertions)} assertions failing")
        for a in assertions:
            if a.id in failed:
                name, evidence = failed[a.id][0]
                print(f"  FAIL {a.id} {a.type} in {len(failed[a.id])} scenario(s). e.g. [{name}] {evidence}")
            else:
                print(f"  pass {a.id} {a.type}")
        non_crash = [a.id for a in assertions if a.type != "no_crash" and a.id in failed]
        if not non_crash:
            print("  PROBLEM: the planted bug was not detected")
            problems += 1

        fixed = suite(runner, CORRECT_FIRMWARE[preset["id"]], spec, assertions, f"{preset['id']} fixed")
        bad = 0
        exercised: dict[str, int] = {}
        for scenario, _trace, results in fixed["runs"]:
            for r in results:
                if r.status != "not_exercised":
                    exercised[r.assertion_id] = exercised.get(r.assertion_id, 0) + 1
                if r.status == "fail":
                    bad += 1
                    print(f"  UNFAIR? [{scenario.name}] {r.assertion_id} {r.type}: {r.evidence}")
        print(f"CORRECT: {len(fixed['runs'])} scenarios, {bad} failures, exercised per assertion {exercised}")
        problems += bad
        for a in assertions:
            if exercised.get(a.id, 0) == 0:
                print(f"  PROBLEM: {a.id} {a.type} is never exercised")
                problems += 1

    print(f"\n{'ALL GOOD' if problems == 0 else f'{problems} PROBLEM(S)'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
