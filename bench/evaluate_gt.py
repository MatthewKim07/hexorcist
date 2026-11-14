"""Run a case's ground-truth checks.json against a sketch in the sandbox (no LLM)."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

# Allow `python -m bench.validate` from repo root.
_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from pydantic import TypeAdapter

from app.assertions import evaluate_all
from app.config import load_settings
from app.models import Assertion, DeviceSpec, NoCrash, PinSpec, Scenario
from app.sandbox import SandboxRunner

from bench.case_io import Case

ADAPTER = TypeAdapter(Assertion)


def build_spec(case: Case) -> DeviceSpec:
    return DeviceSpec(pins=[PinSpec(**p) for p in case.pins], behaviour=case.spec.strip())


def load_assertions(case: Case) -> list[Assertion]:
    raw = list(case.checks.get("assertions") or [])
    assertions: list[Assertion] = [ADAPTER.validate_python(a) for a in raw]
    if not any(a.type == "no_crash" for a in assertions):
        assertions.append(NoCrash(id="a_no_crash", description="Firmware must not crash"))
    for i, a in enumerate(assertions):
        if not a.id:
            a.id = f"a{i + 1}"
    return assertions


def load_scenarios(case: Case) -> list[Scenario]:
    out: list[Scenario] = []
    for raw in case.checks.get("scenarios") or []:
        data = dict(raw)
        data.setdefault("source", "builtin")
        out.append(Scenario.model_validate(data))
    return out


def run_firmware(
    runner: SandboxRunner,
    firmware: str,
    spec: DeviceSpec,
    assertions: list[Assertion],
    scenarios: list[Scenario],
    label: str,
    max_workers: int = 4,
) -> dict[str, Any]:
    built = runner.compile(firmware, label)
    if not built.ok:
        return {
            "ok": False,
            "compile_ok": False,
            "compile_log": built.log,
            "failing_ids": set(),
            "results": [],
            "by_assertion": {},
        }

    def one(scenario: Scenario):
        result = runner.run(built.elf, scenario.harness_json(), f"{label}:{scenario.id or scenario.name}")
        judged = evaluate_all(assertions, result.trace, scenario, spec)
        return scenario, judged

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        runs = list(pool.map(one, scenarios))

    failing: set[str] = set()
    by_assertion: dict[str, list[dict[str, Any]]] = {}
    flat: list[dict[str, Any]] = []
    for scenario, judged in runs:
        for r in judged:
            row = {
                "assertion_id": r.assertion_id,
                "scenario_id": scenario.id or scenario.name,
                "type": r.type,
                "status": r.status,
                "evidence": r.evidence,
            }
            flat.append(row)
            by_assertion.setdefault(r.assertion_id, []).append(row)
            if r.status == "fail" and r.type != "no_crash":
                failing.add(r.assertion_id)
            elif r.status == "fail" and r.type == "no_crash":
                failing.add(r.assertion_id)
    return {
        "ok": True,
        "compile_ok": True,
        "compile_log": built.log,
        "failing_ids": failing,
        "results": flat,
        "by_assertion": by_assertion,
    }


def default_runner() -> SandboxRunner:
    return SandboxRunner(load_settings())
