"""Measure compile time and emulation speed on this machine, alone and at full parallelism.

Run from backend/: python -m scripts.measure_speed
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor

from app.config import load_settings
from app.models import MAX_SCENARIO_MS, DeviceSpec, PinSpec
from app.presets import PRESETS
from app.sandbox import SandboxRunner
from app.scenario_lib import builtin_scenarios
from tests.fixtures import CORRECT_FIRMWARE

# The harness returns a partial trace at this wall-clock time, before the 30 s hard kill.
SOFT_LIMIT_S = 27.0


def speed(trace: dict) -> float:
    return trace["sim_ms"] / trace["wall_ms"] if trace.get("wall_ms") else 0.0


def main() -> None:
    settings = load_settings()
    runner = SandboxRunner(settings)
    preset = next(p for p in PRESETS if p["id"] == "thermostat")
    spec = DeviceSpec(pins=[PinSpec(**p) for p in preset["pins"]], behaviour=preset["behaviour"])
    # Noisy input and a tight loop are what the suite spends most of its time on.
    scenario = next(s for s in builtin_scenarios(spec, []) if "hover" in s.id)

    start = time.monotonic()
    built = runner.compile(CORRECT_FIRMWARE["thermostat"], "speed test")
    if not built.ok:
        sys.exit(f"compile failed:\n{built.log}")
    print(f"compile: {time.monotonic() - start:.1f} s")

    alone = runner.run(built.elf, scenario.harness_json(), "speed alone")
    alone_speed = speed(alone.trace)
    print(f"alone: {alone_speed:.2f}x realtime ({alone.trace['sim_ms']:.0f} ms simulated in {alone.trace['wall_ms']:.0f} ms)")

    workers = settings.max_parallel
    with ThreadPoolExecutor(max_workers=workers) as pool:
        started = time.monotonic()
        runs = list(pool.map(lambda i: runner.run(built.elf, scenario.harness_json(), f"speed parallel {i}"), range(workers)))
        elapsed = time.monotonic() - started
    speeds = [speed(r.trace) for r in runs]
    print(f"{workers} in parallel: {min(speeds):.2f}x to {max(speeds):.2f}x realtime each, {elapsed:.1f} s wall including container start")

    # The slowest case that has to fit: the longest scenario allowed, with all sandboxes busy.
    longest_s = MAX_SCENARIO_MS / 1000
    worst = min(speeds)
    needed = longest_s / SOFT_LIMIT_S
    print(f"longest allowed scenario: {longest_s:.0f} s, needs {needed:.2f}x to finish inside the {SOFT_LIMIT_S:.0f} s limit")
    if worst < needed:
        sys.exit(f"TOO SLOW: {worst:.2f}x would cut long scenarios short. Lower SANDBOX_MAX_PARALLEL or use a faster VM.")
    print(f"OK: {worst / needed:.1f} times the speed needed")


if __name__ == "__main__":
    main()
