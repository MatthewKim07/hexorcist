"""The orchestrator. Holds the API key, plans and judges, and never executes user code itself.

All compiling and running happens through SandboxRunner. All verdicts come from the
deterministic assertion engine. The LLM only proposes: assertions, attacks, explanations, patches.
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import re
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

from . import prompts
from .approach import Attempt, find_code_reversion, find_measured_reversion
from .assertions import evaluate_all
from .config import Settings
from .events import RunBus
from .guard import screen_request
from .llm import LLMClient, LLMError
from .models import (
    Assertion,
    AssertionResult,
    DeviceSpec,
    MaxToggles,
    NoCrash,
    OutputFollows,
    PinSpec,
    SafeStateOnFault,
    Scenario,
    SerialPeriod,
    SerialValueMatches,
    TimedPulse,
    TogglePerPress,
    normalize_pin,
)
from .sandbox import CompileResult, ContainmentRecord, SandboxError, SandboxRunner
from .scenario_lib import builtin_scenarios, fill_defaults, idle_level
from .store import Store

log = logging.getLogger("hexorcist.agent")

MAX_FIX_ITERATIONS = 3
MAX_BUILD_ATTEMPTS = 3
MAX_LLM_SCENARIOS = 10
MAX_LLM_SCENARIO_MS = 12000
MAX_STORED_PIN_EVENTS = 8000
MAX_STORED_SERIAL = 4000

_ASSERTION = TypeAdapter(Assertion)
_HOST_INCLUDE_RE = re.compile(r'^\s*#\s*(?:include|include_next|import)\s*"(?:/|~|\.\./)[^"]*"\s*$', re.MULTILINE)
_MISSING_FILE_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"~[^"]*"\s*$', re.MULTILINE)


@dataclass
class SuiteResult:
    iteration: int
    results: dict[str, list[AssertionResult]] = field(default_factory=dict)
    exit_reasons: dict[str, str] = field(default_factory=dict)

    def failures(self) -> set[tuple[str, str]]:
        return {(r.assertion_id, r.scenario_id) for rs in self.results.values() for r in rs if r.status == "fail"}

    def failing_assertions(self) -> set[str]:
        return {a for a, _ in self.failures()}


def _describe(a: Any) -> str:
    if a.description:
        return a.description
    if isinstance(a, NoCrash):
        return "Firmware runs for the whole scenario without crashing or deadlocking"
    return a.type.replace("_", " ")


def normalize_assertions(raw: list[dict], spec: DeviceSpec) -> tuple[list, list[str]]:
    """Keep only assertions that validate against the schema and this device."""
    warnings: list[str] = []
    kept: list = []
    seen: set[str] = set()
    known = {p.pin for p in spec.pins}

    def pins_ok(a: Any) -> Optional[str]:
        refs: list[str] = []
        if isinstance(a, OutputFollows):
            refs.append(a.pin)
            refs.extend(c.pin for c in (a.high_when, a.low_when) if c is not None)
            if a.high_when is None and a.low_when is None:
                return "output_follows needs a condition"
        elif isinstance(a, MaxToggles):
            refs.append(a.pin)
        elif isinstance(a, TogglePerPress):
            refs.extend([a.input_pin, a.output_pin])
        elif isinstance(a, TimedPulse):
            refs.extend([a.pin, a.trigger.pin])
        elif isinstance(a, SerialValueMatches):
            refs.append(a.input_pin)
        elif isinstance(a, SafeStateOnFault):
            refs.append(a.output_pin)
            if a.fault_when is None and not a.floating_pin:
                return "safe_state_on_fault needs a fault condition"
            if a.fault_when is not None:
                refs.append(a.fault_when.pin)
            if a.floating_pin:
                refs.append(a.floating_pin)
        for pin in refs:
            if pin not in known:
                return f"references {pin}, which is not in the pin map"
        return None

    for item in raw:
        try:
            parsed = _ASSERTION.validate_python(item)
        except ValidationError as exc:
            warnings.append(f"Dropped an invalid assertion: {str(exc).splitlines()[0][:160]}")
            continue
        problem = pins_ok(parsed)
        if problem:
            warnings.append(f"Dropped {parsed.type}: {problem}")
            continue
        if isinstance(parsed, (SerialPeriod, SerialValueMatches)):
            try:
                compiled = re.compile(parsed.pattern)
            except re.error as exc:
                warnings.append(f"Dropped {parsed.type}: bad regex ({exc})")
                continue
            if isinstance(parsed, SerialValueMatches) and compiled.groups < 1:
                warnings.append(f"Dropped {parsed.type}: the regex has no capture group")
                continue
        key = json.dumps(parsed.model_dump(exclude={"id", "description"}), sort_keys=True)
        if key in seen or isinstance(parsed, NoCrash):
            continue
        seen.add(key)
        kept.append(parsed)

    kept = _resolve_overlaps(kept, warnings)
    kept.append(NoCrash())
    for i, a in enumerate(kept):
        a.id = f"a{i + 1}"
        a.description = _describe(a)
    return kept, warnings


def _same_condition(a: Any, b: Any) -> bool:
    return a is not None and b is not None and a.pin == b.pin and a.op == b.op and a.value == b.value


def _resolve_overlaps(assertions: list, warnings: list[str]) -> list:
    """Remove checks that repeat a timed_pulse, and any that no correct firmware could pass with it."""
    pulses = [a for a in assertions if isinstance(a, TimedPulse)]
    kept: list = []
    for a in assertions:
        pulse = None
        if isinstance(a, OutputFollows) and a.mode == "edge":
            pulse = next((p for p in pulses if p.pin == a.pin and _same_condition(p.trigger, a.high_when)), None)
            if pulse is not None:
                # The start deadline is already part of the pulse check. Keep the shortest press the model read from the spec.
                pulse.min_trigger_ms = max(pulse.min_trigger_ms, a.min_trigger_ms)
                warnings.append(f"Dropped output_follows on {a.pin}: timed_pulse already checks that the trigger starts it.")
                continue
        if isinstance(a, SafeStateOnFault):
            pulse = next((p for p in pulses if p.pin == a.output_pin and _same_condition(p.trigger, a.fault_when) and a.safe_value != p.active_level), None)
            if pulse is not None:
                warnings.append(f"Dropped safe_state_on_fault on {a.output_pin}: its fault condition is the trigger that must turn the output on, so no firmware could pass both.")
                continue
        kept.append(a)
    return kept


def fallback_assertions(spec: DeviceSpec) -> list:
    """Used only if the LLM cannot produce assertions. Weak but honest: crash and chatter."""
    raw: list[dict] = [{"type": "max_toggles", "pin": p.pin, "max_toggles": 20, "window_ms": 1000, "description": f"{p.pin} must not chatter"} for p in spec.outputs()]
    kept, _ = normalize_assertions(raw, spec)
    return kept


def normalize_scenarios(raw: list[dict], spec: DeviceSpec, assertions: list) -> tuple[list[Scenario], list[str]]:
    warnings: list[str] = []
    kept: list[Scenario] = []
    inputs = {p.pin for p in spec.inputs()}
    for i, item in enumerate(raw[:MAX_LLM_SCENARIOS]):
        if not isinstance(item, dict):
            continue
        data = dict(item)
        data["id"] = f"llm-{i + 1}"
        data["source"] = "llm"
        data.setdefault("seed", 100 + i)
        # A button left unstated rests at idle. Pydantic's default of 0 would hold an active-LOW button down.
        pins = {p.pin: p for p in spec.inputs()}
        for d in data.get("digital") or []:
            if isinstance(d, dict) and "initial" not in d:
                try:
                    pin = pins.get(normalize_pin(d.get("pin", "")))
                except ValueError:
                    pin = None
                if pin is not None:
                    d["initial"] = idle_level(pin)
        try:
            data["duration_ms"] = min(float(data.get("duration_ms", 8000)), MAX_LLM_SCENARIO_MS)
            scenario = Scenario.model_validate(data)
        except (ValidationError, TypeError, ValueError) as exc:
            warnings.append(f"Dropped an invalid attack scenario: {str(exc).splitlines()[0][:160]}")
            continue
        scenario.analog = [a for a in scenario.analog if a.pin in inputs]
        scenario.digital = [d for d in scenario.digital if d.pin in inputs]
        scenario.floating = [f for f in scenario.floating if f.pin in inputs]
        if not (scenario.analog or scenario.digital or scenario.floating):
            warnings.append(f"Dropped attack scenario {scenario.name!r}: it drives no known input")
            continue
        kept.append(fill_defaults(scenario, spec, assertions))
    return kept, warnings


def strip_host_includes(firmware: str) -> str:
    return _HOST_INCLUDE_RE.sub("", firmware)


def make_diff(before: str, after: str) -> dict:
    lines = list(difflib.unified_diff(before.splitlines(), after.splitlines(), "original.ino", "patched.ino", lineterm="", n=3))
    added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
    return {"unified": "\n".join(lines), "added": added, "removed": removed}


def trim_trace(trace: dict) -> dict:
    """Assertions see the full trace. The copy kept for replay is capped so the UI stays quick."""
    out = dict(trace)
    pins = trace.get("pin_events", [])
    if len(pins) > MAX_STORED_PIN_EVENTS:
        out["pin_events"] = pins[:MAX_STORED_PIN_EVENTS]
        out["pin_events_trimmed_from"] = len(pins)
    serial = trace.get("serial_log", [])
    if len(serial) > MAX_STORED_SERIAL:
        out["serial_log"] = serial[:MAX_STORED_SERIAL]
        out["serial_trimmed_from"] = len(serial)
    return out


def text_before_fence(reply: str) -> str:
    head = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).split("```", 1)[0].strip()
    return head[:600]


class Pipeline:
    def __init__(self, run_id: str, settings: Settings, runner: SandboxRunner, store: Store, bus: RunBus) -> None:
        self.run_id = run_id
        self.settings = settings
        self.runner = runner
        self.store = store
        self.bus = bus
        self.llm = LLMClient(settings)
        self.records: list[dict] = []
        self.warnings: list[str] = []
        self._sem = asyncio.Semaphore(settings.max_parallel)

    # ------------------------------------------------------------- plumbing

    async def _warn(self, text: str) -> None:
        self.warnings.append(text)
        await self.bus.emit("warning", detail=text)

    async def _record(self, record: ContainmentRecord) -> None:
        data = record.to_dict()
        self.records.append(data)
        await self.bus.emit("containment", record=data)

    async def _compile(self, sketch: str, label: str) -> CompileResult:
        async with self._sem:
            built = await asyncio.to_thread(self.runner.compile, sketch, label)
        await self._record(built.record)
        return built

    async def _run_one(self, elf: bytes, scenario: Scenario, assertions: list, spec: DeviceSpec, suite: SuiteResult, label: str) -> None:
        async with self._sem:
            run = await asyncio.to_thread(self.runner.run, elf, scenario.harness_json(), f"{label}: {scenario.name}")
        await self._record(run.record)
        results = evaluate_all(assertions, run.trace, scenario, spec)
        suite.results[scenario.id] = results
        suite.exit_reasons[scenario.id] = run.trace.get("exit_reason", "unknown")
        await asyncio.to_thread(self.store.add_trace, self.run_id, suite.iteration, scenario.id, trim_trace(run.trace))
        failed = [r.assertion_id for r in results if r.status == "fail"]
        await self.bus.emit(
            "scenario_result",
            iteration=suite.iteration,
            scenario_id=scenario.id,
            name=scenario.name,
            passed=not failed,
            failed=failed,
            exit_reason=suite.exit_reasons[scenario.id],
            sim_ms=run.trace.get("sim_ms", 0),
            duration_ms=round(run.record.duration_ms, 1),
        )

    async def _run_suite(self, elf: bytes, scenarios: list[Scenario], assertions: list, spec: DeviceSpec, iteration: int, label: str) -> SuiteResult:
        suite = SuiteResult(iteration=iteration)
        await asyncio.gather(*(self._run_one(elf, s, assertions, spec, suite, label) for s in scenarios))
        return suite

    @staticmethod
    def _failure_payload(suite: SuiteResult, assertions: list, scenarios: list[Scenario]) -> list[dict]:
        by_id = {s.id: s for s in scenarios}
        out: list[dict] = []
        for a in assertions:
            failing = [r for rs in suite.results.values() for r in rs if r.assertion_id == a.id and r.status == "fail"]
            if not failing:
                continue
            failing.sort(key=lambda r: -len(r.violations))
            out.append(
                {
                    "assertion_id": a.id,
                    "requirement": a.description,
                    "assertion": a.model_dump(exclude={"id", "description"}, exclude_none=True),
                    "failing_in": [
                        {
                            "scenario": by_id[r.scenario_id].name,
                            "hypothesis": by_id[r.scenario_id].hypothesis,
                            "measured": r.evidence,
                            "first_violations": [v.model_dump() for v in r.violations[:3]],
                        }
                        for r in failing[:3]
                    ],
                    "failing_scenario_count": len(failing),
                }
            )
        return out

    # ---------------------------------------------------------- break mode

    async def run_break(self, firmware: str, spec: DeviceSpec, extra_report: Optional[dict] = None) -> tuple[str, dict]:
        bus = self.bus

        # 1. UNDERSTAND
        await bus.step("understand", "running", "Reading the firmware and specification")
        device_model = prompts.DeviceModel()
        spec_checked = True
        try:
            reply = await self.llm.json(prompts.UNDERSTAND_SYSTEM, prompts.understand_user(firmware, spec), prompts.UnderstandReply, "understand")
            device_model = reply.device_model
            assertions, warnings = normalize_assertions(reply.assertions, spec)
            for w in warnings:
                await self._warn(w)
            if len(assertions) <= 1:
                await self._warn("The LLM produced no usable assertions, so only baseline crash and chatter checks are running.")
                assertions = fallback_assertions(spec)
                spec_checked = False
        except LLMError as exc:
            if not self.settings.llm_configured:
                await bus.step("understand", "failed", str(exc))
                return "error", self._report("error", firmware, spec, error=str(exc), extra=extra_report)
            await self._warn(f"Could not derive assertions from the spec, so only baseline crash and chatter checks are running: {exc}")
            assertions = fallback_assertions(spec)
            spec_checked = False
        await bus.emit("device_model", device_model=device_model.model_dump())
        await bus.emit("assertions", assertions=[a.model_dump(exclude_none=True) for a in assertions])
        await bus.step("understand", "done", f"{len(assertions)} machine-checkable assertions")

        # 2. COMPILE
        await bus.step("compile", "running", "Compiling in a sandbox")
        built = await self._compile(firmware, "compile uploaded firmware")
        if not built.ok:
            await bus.emit("compile_log", iteration=0, ok=False, log=built.log)
            await bus.step("compile", "failed", "The firmware does not compile")
            return "compile_failed", self._report("compile_failed", firmware, spec, assertions=assertions, device_model=device_model, compile_log=built.log, extra=extra_report)
        await bus.emit("compile_log", iteration=0, ok=True, log=built.log)
        await bus.step("compile", "done", _sketch_size(built.log))

        # 3. ATTACK PLAN
        await bus.step("attack", "running", "Designing adversarial scenarios")
        library = builtin_scenarios(spec, assertions)
        llm_scenarios: list[Scenario] = []
        try:
            plan = await self.llm.json(
                prompts.ATTACK_SYSTEM,
                prompts.attack_user(firmware, spec, [a.model_dump(exclude_none=True) for a in assertions], [s.name for s in library]),
                prompts.AttackPlan,
                "attack",
            )
            llm_scenarios, warnings = normalize_scenarios(plan.scenarios, spec, assertions)
            for w in warnings:
                await self._warn(w)
        except LLMError as exc:
            await self._warn(f"The LLM attack plan failed, so only the built-in library is running: {exc}")
        scenarios = library + llm_scenarios
        await bus.emit("scenarios", scenarios=[s.model_dump() for s in scenarios])
        await bus.step("attack", "done", f"{len(llm_scenarios)} from the agent, {len(library)} built in")

        # 4. EXECUTE
        await bus.step("execute", "running", f"Running {len(scenarios)} scenarios in parallel sandboxes")
        baseline = await self._run_suite(built.elf, scenarios, assertions, spec, 0, "attack")
        baseline_failures = baseline.failures()
        failing_ids = baseline.failing_assertions()
        await bus.step("execute", "done", f"{len(baseline_failures)} failures across {len(failing_ids)} assertions")

        exercised = {r.assertion_id for rs in baseline.results.values() for r in rs if r.status != "not_exercised"}
        for a in assertions:
            if a.id not in exercised:
                await self._warn(f"No scenario exercised {a.id} ({a.description}), so it was not really tested.")
        extra_report = {**(extra_report or {}), "spec_checked": spec_checked, "unexercised": [a.id for a in assertions if a.id not in exercised]}

        iterations: list[dict] = [self._iteration_row(0, baseline, set(), set(), "Uploaded firmware", True, assertions)]
        if not baseline_failures:
            for step in ("diagnose", "fix", "verify"):
                await bus.step(step, "skipped", "No bugs to work on")
            # Never give an all-clear unless the spec was really turned into checks that really ran.
            spec_tested = spec_checked and any(a.type != "no_crash" and a.id in exercised for a in assertions)
            status = "clean" if spec_tested else "inconclusive"
            report = self._report(status, firmware, spec, assertions=assertions, device_model=device_model, scenarios=scenarios, suites={0: baseline}, iterations=iterations, extra=extra_report)
            return status, report

        # 5. DIAGNOSE
        await bus.step("diagnose", "running", f"Explaining {len(failing_ids)} failing assertions")
        payload = self._failure_payload(baseline, assertions, scenarios)
        diagnoses: dict[str, prompts.BugDiagnosis] = {}
        try:
            diag = await self.llm.json(prompts.DIAGNOSE_SYSTEM, prompts.diagnose_user(firmware, spec, payload), prompts.DiagnoseReply, "diagnose")
            diagnoses = {b.assertion_id: b for b in diag.bugs}
        except LLMError as exc:
            await self._warn(f"Diagnosis failed, so the bug cards carry measured evidence only: {exc}")
        line_count = len(firmware.splitlines())
        bugs = [self._build_bug(a, baseline, scenarios, diagnoses.get(a.id), line_count) for a in assertions if a.id in failing_ids]
        for bug in bugs:
            await bus.emit("bug", bug=bug)
        await bus.step("diagnose", "done", f"{len(bugs)} bugs found")

        # 6 and 7. FIX and VERIFY
        assertions_json = [a.model_dump(exclude_none=True) for a in assertions]
        current = firmware
        failures = payload
        previous: Optional[dict] = None
        best: Optional[dict] = None
        suites: dict[int, SuiteResult] = {0: baseline}
        tested: list[Attempt] = []

        def disproven() -> list[Attempt]:
            return [a for a in tested if best is None or a.n != best["n"]]

        def history() -> list[dict]:
            return [
                {
                    "attempt": a.n,
                    "approach": a.summary[:300],
                    "failing_checks": len(a.failing),
                    "failing_requirements": sorted({descriptions[aid] for aid, _ in a.failing}),
                    "status": "your best patch so far" if best is not None and a.n == best["n"] else "disproven",
                }
                for a in tested
            ]

        descriptions = {a.id: a.description for a in assertions}

        for n in range(1, MAX_FIX_ITERATIONS + 1):
            await bus.step("fix", "running", f"Writing patch, attempt {n} of {MAX_FIX_ITERATIONS}")
            try:
                code, raw_reply = await self.llm.code(prompts.FIX_SYSTEM, prompts.fix_user(current, spec, failures, assertions_json, previous, history()), "fix")
                reverted = find_code_reversion(code, disproven(), best["code"] if best else None, firmware)
                if code.strip() == current.strip():
                    # One free chance: a model can claim a fix and still repeat the code. Nothing was tested.
                    await self._warn(f"Patch {n} repeated the firmware unchanged, so it was sent back.")
                    await bus.step("fix", "running", f"Patch {n} changed nothing. Asking again")
                    redo = {**(previous or {}), "rejected_without_testing": "Your reply was byte-for-byte the firmware above, although your summary claimed a change. The failures above still happen. Change the code."}
                    code, raw_reply = await self.llm.code(prompts.FIX_SYSTEM, prompts.fix_user(current, spec, failures, assertions_json, redo, history()), "fix")
                    reverted = find_code_reversion(code, disproven(), best["code"] if best else None, firmware)
                elif reverted is not None:
                    # One free chance to change course: this patch was never tested, so it costs no attempt.
                    await self._warn(f"Patch {n} was sent back without testing. {reverted.reason}")
                    await bus.step("fix", "running", f"Patch {n} went back to attempt {reverted.attempt}, which was disproven. Asking for a different approach")
                    redo = {**(previous or {}), "rejected_without_testing": f"{reverted.reason} That approach was already measured and it failed. Use a different mechanism."}
                    code, raw_reply = await self.llm.code(prompts.FIX_SYSTEM, prompts.fix_user(current, spec, failures, assertions_json, redo, history()), "fix")
                    reverted = find_code_reversion(code, disproven(), best["code"] if best else None, firmware)
            except LLMError as exc:
                await self._warn(f"The fix attempt failed: {exc}")
                await bus.step("fix", "failed", str(exc)[:200])
                break
            summary = text_before_fence(raw_reply)
            await bus.step("fix", "done", summary[:200] or f"Patch {n} written")

            if reverted is not None:
                previous = {"rejected_without_testing": f"Patch {n} was rejected. {reverted.reason} That approach was already measured and it failed.", "firmware_above": "your best patch so far"}
                iterations.append({"n": n, "compile_ok": False, "rejected": True, "reverted_to": reverted.attempt, "summary": f"Rejected: {reverted.reason}", "patch": code, "failing": None, "still_failing": [], "regressions": []})
                await self._warn(f"Patch {n} was rejected without testing. {reverted.reason}")
                continue

            screened = screen_request(code, "")
            if not screened["allowed"]:
                previous = {"rejected_by_input_guard": screened["reasons"]}
                current = code
                iterations.append({"n": n, "compile_ok": False, "rejected": True, "summary": summary, "failing": None, "still_failing": [], "regressions": []})
                await self._warn(f"Patch {n} was rejected by the input guard: {screened['reasons']}")
                continue
            if code.strip() == current.strip():
                log.info("run %s patch %d was identical to its input. Reply was:\n%s", self.run_id, n, raw_reply[:6000])
                previous = {"problem": "Your patch was byte-for-byte identical to the firmware it was meant to change, so the failures above still happen. Change the code."}
                iterations.append({"n": n, "compile_ok": False, "rejected": True, "summary": "Patch made no changes.", "failing": None, "still_failing": [], "regressions": []})
                continue

            await bus.step("verify", "running", f"Recompiling patch {n} and re-running all {len(scenarios)} scenarios")
            patched = await self._compile(code, f"compile patch {n}")
            await bus.emit("compile_log", iteration=n, ok=patched.ok, log=patched.log)
            if not patched.ok:
                previous = {"compile_errors": patched.log[:3000], "firmware_above": "your last patch, which did not compile"}
                current = code
                iterations.append({"n": n, "compile_ok": False, "summary": summary, "patch": code, "failing": None, "still_failing": [], "regressions": []})
                await bus.step("verify", "running", f"Patch {n} did not compile, feeding the errors back")
                continue

            suite = await self._run_suite(patched.elf, scenarios, assertions, spec, n, f"verify patch {n}")
            suites[n] = suite
            now_failing = suite.failures()
            still = now_failing & baseline_failures
            regressions = now_failing - baseline_failures
            row = self._iteration_row(n, suite, still, regressions, summary, True, assertions)
            row["patch"] = code

            # A patch must beat the best so far to replace it, so a tie keeps the earlier, smaller change.
            improved = best is None or len(now_failing) < len(best["failing"])
            repeated = None if improved else find_measured_reversion(now_failing, disproven())
            if repeated is not None:
                row["rejected"] = True
                row["reverted_to"] = repeated.attempt
                await self._warn(f"Patch {n} was rejected after testing. {repeated.reason}")
            iterations.append(row)
            await bus.emit("iteration", iteration=row)

            tested.append(Attempt(n=n, code=code, summary=summary, failing=now_failing))
            if improved:
                best = {"n": n, "code": code, "summary": summary, "failing": now_failing, "still": still, "regressions": regressions}
                best_suite = suite
            if not now_failing:
                break

            # Always build on the best measured patch. A worse patch is a dead end, not a starting point.
            current = best["code"]
            failures = self._failure_payload(best_suite, assertions, scenarios)
            previous = {
                "latest_patch": f"attempt {n}: {len(now_failing)} failing checks, {len(still)} of them from the original firmware, {len(regressions)} new",
                "new_regressions": [{"assertion": a, "scenario": s} for a, s in sorted(regressions)][:10],
                "firmware_above": "your best patch so far" if improved else f"your best patch so far, attempt {best['n']}. Attempt {n} was no better, so it was discarded",
            }
            if repeated is not None:
                previous["rejected_after_testing"] = repeated.reason
            await bus.step("verify", "running", f"Patch {n}: {len(still)} still failing, {len(regressions)} new. Building on patch {best['n']}")

        # 8. REPORT
        if best is None:
            status = "unfixed"
            await bus.step("verify", "failed", "No patch compiled and ran")
        elif not best["failing"]:
            status = "fixed"
            await bus.step("verify", "done", f"Patch {best['n']} passes all {len(scenarios)} scenarios with no regressions")
        else:
            status = "partial"
            await bus.step("verify", "failed", f"Best patch still has {len(best['failing'])} failing checks")

        report = self._report(
            status,
            firmware,
            spec,
            assertions=assertions,
            device_model=device_model,
            scenarios=scenarios,
            suites=suites,
            iterations=iterations,
            bugs=bugs,
            best=best,
            extra=extra_report,
        )
        return status, report

    def _iteration_row(self, n: int, suite: SuiteResult, still: set, regressions: set, summary: str, compile_ok: bool, assertions: list) -> dict:
        return {
            "n": n,
            "compile_ok": compile_ok,
            "summary": summary,
            "failing": len(suite.failures()),
            "failing_assertions": sorted(suite.failing_assertions()),
            "still_failing": sorted(f"{a}:{s}" for a, s in still),
            "regressions": sorted(f"{a}:{s}" for a, s in regressions),
        }

    @staticmethod
    def _build_bug(a: Any, suite: SuiteResult, scenarios: list[Scenario], diagnosis: Optional[prompts.BugDiagnosis], line_count: int) -> dict:
        names = {s.id: s.name for s in scenarios}
        failing = [r for rs in suite.results.values() for r in rs if r.assertion_id == a.id and r.status == "fail"]
        # Lead with the most damaging measurement, breaking ties by scenario order for stable reports.
        order = {s.id: i for i, s in enumerate(scenarios)}
        failing.sort(key=lambda r: (-len(r.violations), order.get(r.scenario_id, 0)))
        primary = failing[0]
        severity = diagnosis.severity if diagnosis else ("critical" if isinstance(a, (NoCrash, SafeStateOnFault)) else "high")
        return {
            "id": f"bug-{a.id}",
            "assertion_id": a.id,
            "assertion_type": a.type,
            "requirement": a.description,
            "title": (diagnosis.title if diagnosis and diagnosis.title else a.description),
            "severity": severity,
            "root_cause": diagnosis.root_cause if diagnosis else "",
            "code_lines": [n for n in (diagnosis.code_lines if diagnosis else []) if isinstance(n, int) and 1 <= n <= line_count],
            "scenario_id": primary.scenario_id,
            "scenario_name": names.get(primary.scenario_id, primary.scenario_id),
            "evidence": primary.evidence,
            "metrics": primary.metrics,
            "failing_scenarios": [{"id": r.scenario_id, "name": names.get(r.scenario_id, r.scenario_id), "evidence": r.evidence} for r in failing],
        }

    def _report(
        self,
        status: str,
        firmware: str,
        spec: DeviceSpec,
        assertions: Optional[list] = None,
        device_model: Optional[prompts.DeviceModel] = None,
        scenarios: Optional[list[Scenario]] = None,
        suites: Optional[dict[int, SuiteResult]] = None,
        iterations: Optional[list[dict]] = None,
        bugs: Optional[list[dict]] = None,
        best: Optional[dict] = None,
        compile_log: str = "",
        error: str = "",
        extra: Optional[dict] = None,
    ) -> dict:
        suites = suites or {}
        bugs = bugs or []
        final_failing: set[str] = set()
        clean_final = False
        if best is not None:
            final_failing = {a for a, _ in best["failing"]}
            clean_final = not best["regressions"]

        for bug in bugs:
            baseline = suites[0].results.get(bug["scenario_id"], []) if 0 in suites else []
            bug["before"] = next((_result_brief(r) for r in baseline if r.assertion_id == bug["assertion_id"]), None)
            bug["after"] = None
            if best is not None and best["n"] in suites:
                after = suites[best["n"]].results.get(bug["scenario_id"], [])
                bug["after"] = next((_result_brief(r) for r in after if r.assertion_id == bug["assertion_id"]), None)
            # Verified means this check passes on every scenario AND the patch broke nothing else.
            bug["verified"] = best is not None and bug["assertion_id"] not in final_failing and clean_final

        report: dict = {
            "status": status,
            "firmware": firmware,
            "spec": spec.model_dump(),
            "device_model": device_model.model_dump() if device_model else None,
            "assertions": [a.model_dump(exclude_none=True) for a in (assertions or [])],
            "scenarios": [s.model_dump() for s in (scenarios or [])],
            "matrix": {str(n): {sid: [r.model_dump() for r in rs] for sid, rs in suite.results.items()} for n, suite in suites.items()},
            "exit_reasons": {str(n): suite.exit_reasons for n, suite in suites.items()},
            "iterations": iterations or [],
            "bugs": bugs,
            "compile_log": compile_log,
            "error": error,
            "warnings": self.warnings,
            "containment": self._containment_summary(),
            "llm": self._llm_summary(),
            "score": {
                "bugs_found": len(bugs),
                "bugs_verified": sum(1 for b in bugs if b["verified"]),
                "scenarios": len(scenarios or []),
                "assertions": len(assertions or []),
                "fix_attempts": max(0, len(iterations or []) - 1),
            },
        }
        if best is not None:
            report["fix"] = {
                "iteration": best["n"],
                "summary": best["summary"],
                "patched_firmware": best["code"],
                "diff": make_diff(firmware, best["code"]),
                "all_passing": not best["failing"],
                "regressions": sorted(f"{a}:{s}" for a, s in best["regressions"]),
            }
        if extra:
            report.update(extra)
        return report

    def _containment_summary(self) -> dict:
        records = self.records
        return {
            "records": records,
            "total": len(records),
            "removed": sum(1 for r in records if r["removed"]),
            "secrets_found": sum(r["secrets_found"] for r in records),
            "timeouts": sum(1 for r in records if r["timed_out"]),
            "oom_kills": sum(1 for r in records if r["oom_killed"]),
            "network_none": all(r["limits"].get("network") == "none" for r in records) if records else None,
            "violations": sum(len(r["violations"]) for r in records),
        }

    def _llm_summary(self) -> dict:
        calls = self.llm.calls
        return {
            "model": self.settings.llm_model,
            "calls": len(calls),
            "repairs": sum(1 for c in calls if c.repaired),
            "prompt_tokens": sum(c.prompt_tokens for c in calls),
            "completion_tokens": sum(c.completion_tokens for c in calls),
        }

    # ---------------------------------------------------- containment mode

    async def run_containment(self, firmware: str, spec: DeviceSpec, verdict: dict) -> tuple[str, dict]:
        """The guard blocked this upload, so it never reaches the LLM. Show the sandbox holding anyway."""
        bus = self.bus
        checks: list[dict] = []

        def check(label: str, ok: bool, detail: str) -> None:
            checks.append({"label": label, "ok": bool(ok), "detail": detail})

        await bus.step("understand", "done", f"Input guard blocked this upload (score {verdict['score']}). The LLM was not contacted.")
        check("Input guard flagged the upload", not verdict["allowed"], "; ".join(verdict["reasons"]))

        await bus.step("compile", "running", "Compiling the hostile sketch, inside a sandbox")
        hostile = await self._compile(firmware, "compile hostile upload as written")
        await bus.emit("compile_log", iteration=0, ok=hostile.ok, log=hostile.log)

        # The realistic attack: pull files in, and read them back through compiler errors.
        # Drop only the include of a file that does not exist, so the others get that far.
        exfil_source = _MISSING_FILE_INCLUDE_RE.sub("", firmware)
        exfil = await self._compile(exfil_source, "compile with readable includes, to leak them through errors")
        await bus.step("compile", "done", f"Compile attempts contained, {sum(len(r.violations) for r in (hostile.record, exfil.record))} events recorded")

        await bus.step("attack", "skipped", "No attack plan: this upload is the attack")

        await bus.step("execute", "running", "Inspecting the sandbox, then running firmware that never stops")
        await bus.emit("scenarios", scenarios=[{"id": "containment-probe", "name": "Sandbox self-inspection", "hypothesis": "What can a program inside the sandbox see or reach?", "source": "builtin"}, {"id": "containment-runaway", "name": "Runaway firmware (no time cap)", "hypothesis": "The simulated-time cap is removed on purpose, so only the wall-clock kill can stop this.", "source": "builtin"}])

        async with self._sem:
            facts, probe_record = await asyncio.to_thread(self.runner.probe)
        await self._record(probe_record)
        await bus.emit("scenario_result", iteration=0, scenario_id="containment-probe", name="Sandbox self-inspection", passed=True, failed=[], exit_reason="completed", sim_ms=0, duration_ms=round(probe_record.duration_ms, 1))

        runaway_info: dict = {"ran": False}
        stripped = strip_host_includes(firmware)
        runaway_build = await self._compile(stripped, "compile with host includes stripped")
        if runaway_build.ok:
            async with self._sem:
                run = await asyncio.to_thread(self.runner.run, runaway_build.elf, {"seed": 1, "duration_ms": 1000}, "runaway firmware, simulated-time cap removed", True)
            await self._record(run.record)
            runaway_info = {
                "ran": True,
                "killed": run.record.timed_out,
                "duration_s": round(run.record.duration_ms / 1000, 1),
                "timeout_s": run.record.timeout_s,
                "exit_code": run.record.exit_code,
                "removed": run.record.removed,
                "note": "The harness normally stops at the scenario's simulated duration. That cap was removed for this one run, so only the external wall-clock kill could end it.",
            }
            await bus.emit("scenario_result", iteration=0, scenario_id="containment-runaway", name="Runaway firmware (no time cap)", passed=run.record.timed_out, failed=[], exit_reason="killed" if run.record.timed_out else run.trace.get("exit_reason", "unknown"), sim_ms=0, duration_ms=round(run.record.duration_ms, 1))
        else:
            await self._warn("After stripping the host includes the sketch still did not compile, so the runaway probe was skipped.")
        await bus.step("execute", "done", "Sandbox inspected and runaway firmware handled")

        for step in ("diagnose", "fix", "verify"):
            await bus.step(step, "skipped", "Blocked upload: no LLM work is done")

        records = self.records
        check("LLM never contacted", len(self.llm.calls) == 0, f"{len(self.llm.calls)} LLM calls for this run, so the prompt injection reached no model")
        leaks = sum(r["secrets_found"] for r in records)
        check("No control-plane secrets in any output", leaks == 0, f"Searched all {len(records)} sandbox outputs for the API key and passcode: {leaks} found")
        env_names = sorted({name for r in records for name in r["env_names"]})
        check("No secrets in the sandbox environment", not any(n in env_names for n in ("LLM_API_KEY", "DEMO_PASSCODE")), f"Environment variables Docker set: {', '.join(env_names) or 'none'}")
        check("Network disabled", all(r["limits"].get("network") == "none" for r in records) and facts.get("network") == "blocked" and facts.get("dns") == "blocked", f"NetworkMode none on all {len(records)} containers. Outbound connect: {facts.get('network')}. DNS: {facts.get('dns')}")
        check("No host filesystem access", all(not r["limits"].get("binds") and not r["limits"].get("mounts") for r in records), "Zero bind mounts and zero volumes, so paths inside resolve only to the sandbox image")
        check("No Docker socket in the sandbox", facts.get("docker_sock") == "absent", f"/var/run/docker.sock: {facts.get('docker_sock')}")
        check("Stripped of privileges", facts.get("cap_eff") == "0000000000000000" and facts.get("no_new_privs") == "1" and facts.get("uid") != "0", f"uid {facts.get('uid')}, effective capabilities {facts.get('cap_eff')}, no_new_privs {facts.get('no_new_privs')}")
        check("Read-only root filesystem", facts.get("rootfs") == "read-only", f"Write to / was {facts.get('rootfs')}")
        if runaway_info.get("ran"):
            check("Runaway firmware killed by wall clock", bool(runaway_info.get("killed")), f"SIGKILL at {runaway_info.get('duration_s')} s against a {runaway_info.get('timeout_s')} s limit")
        check("Every container removed", all(r["removed"] for r in records), f"{sum(1 for r in records if r['removed'])} of {len(records)} removed")

        contained = all(c["ok"] for c in checks)
        status = "contained" if contained else "containment_failed"
        report = self._report(status, firmware, spec, compile_log=hostile.log)
        report["contained"] = {
            "contained": contained,
            "guard": verdict,
            "checks": checks,
            "probe": facts,
            "runaway": runaway_info,
            "file_reads": sorted({v["detail"] for r in records for v in r["violations"] if v["type"] == "file_read_attempt"}),
            "hostile_compile_log": hostile.log[:4000],
            "exfil_compile_log": exfil.log[:4000],
            "what_the_attacker_got": {
                "etc_passwd_users": facts.get("etc_passwd_users", []),
                "environ_names": facts.get("proc_environ_names", []),
                "ssh_key": facts.get("ssh_key"),
                "note": "The compiler did open /etc/passwd and /proc/self/environ. They are the sandbox's own files, which hold nothing but image defaults. No host file is reachable.",
            },
        }
        report["score"]["checks_passed"] = sum(1 for c in checks if c["ok"])
        report["score"]["checks_total"] = len(checks)
        return status, report

    # ---------------------------------------------------------- build mode

    async def run_build(self, description: str, pins: list[PinSpec]) -> tuple[str, dict]:
        bus = self.bus
        await bus.step("write", "running", "Turning the description into a specification")
        hint = ""
        if pins:
            hint = "\nThe user already chose this wiring, keep it:\n" + "\n".join(f"{p.pin} {p.type} {p.role} {p.scale}".strip() for p in pins)
        try:
            spec_reply = await self.llm.json(prompts.BUILD_SPEC_SYSTEM, f"<description>\n{description}\n</description>{hint}\n\nReturn the JSON object.", prompts.BuildSpecReply, "write")
        except LLMError as exc:
            await bus.step("write", "failed", str(exc)[:300])
            return "error", self._report("error", "", DeviceSpec(), error=str(exc))
        try:
            spec = DeviceSpec(pins=[PinSpec(**p.model_dump()) for p in spec_reply.pins], behaviour=spec_reply.behaviour)
        except ValidationError as exc:
            message = f"The generated pin map was invalid: {str(exc)[:300]}"
            await bus.step("write", "failed", message)
            return "error", self._report("error", "", DeviceSpec(), error=message)
        await bus.emit("spec", spec=spec.model_dump(), title=spec_reply.title)

        code = ""
        last_error: Optional[str] = None
        attempts: list[dict] = []
        built: Optional[CompileResult] = None
        for attempt in range(1, MAX_BUILD_ATTEMPTS + 1):
            await bus.step("write", "running", f"Writing firmware, attempt {attempt} of {MAX_BUILD_ATTEMPTS}")
            try:
                code, _ = await self.llm.code(prompts.BUILD_CODE_SYSTEM, prompts.build_code_user(spec, last_error, code or None), "write")
            except LLMError as exc:
                await bus.step("write", "failed", str(exc)[:300])
                return "error", self._report("error", code, spec, error=str(exc))
            screened = screen_request(code, "")
            if not screened["allowed"]:
                last_error = f"Rejected by the input guard: {screened['reasons']}. Use only the Arduino core and Servo."
                attempts.append({"attempt": attempt, "ok": False, "error": last_error})
                continue
            built = await self._compile(code, f"compile generated firmware, attempt {attempt}")
            attempts.append({"attempt": attempt, "ok": built.ok, "error": "" if built.ok else built.log[:1500]})
            await bus.emit("compile_log", iteration=-attempt, ok=built.ok, log=built.log)
            if built.ok:
                break
            last_error = built.log
        await bus.emit("firmware", firmware=code)
        extra = {"build": {"description": description, "title": spec_reply.title, "attempts": attempts}}
        if built is None or not built.ok:
            await bus.step("write", "failed", f"No compiling firmware after {MAX_BUILD_ATTEMPTS} attempts")
            return "compile_failed", self._report("compile_failed", code, spec, compile_log=last_error or "", extra=extra)
        await bus.step("write", "done", f"Compiled on attempt {len(attempts)}. Now attacking its own code")
        return await self.run_break(code, spec, extra_report=extra)


def _sketch_size(log_text: str) -> str:
    match = re.search(r"Sketch uses (\d+) bytes \((\d+)%\)", log_text)
    return f"Compiled: {match.group(1)} bytes of flash, {match.group(2)}%" if match else "Compiled"


def _result_brief(r: AssertionResult) -> dict:
    return {"status": r.status, "evidence": r.evidence, "metrics": r.metrics}


async def execute_run(pipeline: Pipeline, mode: str, firmware: str, spec: DeviceSpec, description: str, verdict: dict) -> None:
    """Run the pipeline to completion. Always leaves the run in a final state and closes the stream."""
    bus = pipeline.bus
    store = pipeline.store
    run_id = pipeline.run_id
    status = "error"
    report: Optional[dict] = None
    try:
        if not verdict["allowed"]:
            if mode == "build":
                await bus.step("write", "failed", "Input guard blocked this description. The LLM was not contacted.")
                status, report = "blocked", pipeline._report("blocked", "", spec, error="; ".join(verdict["reasons"]))
                report["guard"] = verdict
            else:
                status, report = await pipeline.run_containment(firmware, spec, verdict)
        elif mode == "build":
            status, report = await pipeline.run_build(description, spec.pins)
        else:
            status, report = await pipeline.run_break(firmware, spec)
        await bus.step("report", "done" if status != "error" else "failed", status)
    except SandboxError as exc:
        log.warning("sandbox failure in run %s: %s", run_id, exc)
        report = pipeline._report("error", firmware, spec, error=f"Sandbox failure: {exc}")
        await bus.step("report", "failed", str(exc)[:300])
    except Exception as exc:  # noqa: BLE001 - a failed run must still reach a final state
        log.error("run %s crashed\n%s", run_id, traceback.format_exc())
        report = pipeline._report("error", firmware, spec, error=f"Internal error: {type(exc).__name__}: {exc}")
        await bus.step("report", "failed", f"{type(exc).__name__}: {exc}"[:300])
    finally:
        await asyncio.to_thread(store.finish_run, run_id, status, report)
        await bus.emit("done", status=status)
        await bus.close()


__all__ = ["Pipeline", "execute_run"]
