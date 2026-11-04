"""Step 0 proof: compile real sketches and emulate them through the locked-down runner.

Run from backend/: python -m scripts.verify_sandbox
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from app.config import load_settings
from app.sandbox import SandboxRunner

EXAMPLES = Path(__file__).resolve().parents[2] / "sandbox" / "examples"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def check(ok: bool, message: str) -> None:
    if not ok:
        fail(message)
    print(f"  PASS {message}")


def show_record(record) -> None:
    d = record.to_dict()
    print(f"  container {d['container_id']} exit={d['exit_code']} {d['duration_ms']:.0f} ms removed={d['removed']} timed_out={d['timed_out']} oom={d['oom_killed']}")
    print(f"  env_names {d['env_names']} secrets_found={d['secrets_found']} violations={d['violations']}")


def main() -> None:
    runner = SandboxRunner(load_settings())
    print("health:", runner.health())

    print("\n== Blink: compile")
    start = time.monotonic()
    blink = runner.compile((EXAMPLES / "blink.ino").read_text(), "blink")
    print(f"  ok={blink.ok} in {time.monotonic() - start:.1f} s")
    print("  " + blink.log.strip().replace("\n", "\n  ")[:600])
    show_record(blink.record)
    if not blink.ok:
        fail("blink did not compile")

    print("\n== Blink: emulate 2 s")
    scenario = json.loads((EXAMPLES / "empty_scenario.json").read_text())
    result = runner.run(blink.elf, scenario, "blink")
    trace = result.trace
    show_record(result.record)
    print(f"  exit_reason={trace.get('exit_reason')} cycles={trace.get('cycles')} sim_ms={trace.get('sim_ms')} wall_ms={trace.get('wall_ms')}")
    d13 = [e for e in trace.get("pin_events", []) if e["pin"] == "D13"]
    print(f"  D13 events ({len(d13)}):")
    for e in d13:
        print(f"    t={e['t_ms']:9.3f} ms  value={e['value']}  dir={e['dir']}")
    if len(d13) < 6:
        fail("D13 did not toggle as expected")

    print("\n== analogRead + serial: compile")
    analog = runner.compile((EXAMPLES / "analog_serial.ino").read_text(), "analog")
    print(f"  ok={analog.ok}")
    show_record(analog.record)
    if not analog.ok:
        print(analog.log)
        fail("analog sketch did not compile")

    print("\n== analogRead + serial: emulate 5 s, A0 ramps 1000 to 4000 mV, D2 bounces low at 3 s")
    scenario = json.loads((EXAMPLES / "analog_scenario.json").read_text())
    result = runner.run(analog.elf, scenario, "analog")
    trace = result.trace
    show_record(result.record)
    print(f"  exit_reason={trace.get('exit_reason')} sim_ms={trace.get('sim_ms')} wall_ms={trace.get('wall_ms')}")
    errors = []
    for line in trace.get("serial_log", []):
        # A line is timestamped when its last byte leaves, about 1 ms per char at 9600 baud,
        # and analogRead ran before the first byte was queued.
        sampled = line["t_ms"] - len(line["text"]) * 1.04 - 2.0
        expected = 4000.0 if sampled >= 4000 else 1000.0 + 3000.0 * sampled / 4000.0
        if 2000 <= sampled < 2100:
            expected = 4900.0  # the injected spike
        mv = int(line["text"].split("mv=")[1].split()[0])
        errors.append(abs(mv - expected))
        print(f"    t={line['t_ms']:9.3f} ms  {line['text']!r}  (injected about {expected:.0f} mV at sample time)")
    d2 = [e for e in trace.get("pin_events", []) if e["pin"] == "D2"]
    print(f"  D2 input events: {[(round(e['t_ms'], 2), e['value']) for e in d2]}")
    spike = [p for p in trace.get("input_trace", []) if p["max_mv"] >= 4800]
    print(f"  input_trace points: {len(trace.get('input_trace', []))}, buckets showing the spike: {len(spike)}")
    print(f"  ADC error vs injected: max {max(errors):.0f} mV over {len(errors)} samples")
    check(len(errors) == 10, "ten serial lines")
    check(max(errors) < 25, "ADC reads within 25 mV of injected voltage")
    check(len(d2) >= 6, "D2 bounce reached the pin")
    check(len(spike) > 0, "spike visible in downsampled trace")
    btn = [line["text"].split("btn=")[1] for line in trace["serial_log"]]
    check(btn[0] == "1" and btn[-1] == "0", "digitalRead sees idle HIGH then pressed LOW")

    print("\n== PWM and pull-up")
    built = runner.compile((EXAMPLES / "pwm.ino").read_text(), "pwm")
    check(built.ok, "pwm compiles")
    trace = runner.run(built.elf, {"seed": 1, "duration_ms": 1000}, "pwm").trace
    print(f"  pwm_events: {[(round(e['t_ms']), e['pin'], e['duty']) for e in trace['pwm_events']]}")
    d9 = [(round(e["t_ms"]), e["value"]) for e in trace["pin_events"] if e["pin"] == "D9"]
    print(f"  D9 gpio: {d9}")
    check(any(e["pin"] == "D9" and e["duty"] == 128 for e in trace["pwm_events"]), "analogWrite(9,128) seen as duty 128")
    check(any(e["pin"] == "D9" and e["duty"] == -1 for e in trace["pwm_events"]), "analogWrite(9,0) hands D9 back to GPIO")
    check(any(v == 1 for _, v in d9), "digitalRead(3) with INPUT_PULLUP idles HIGH")

    print("\n== Determinism: same seed gives an identical trace, new seed does not")
    built = runner.compile((EXAMPLES / "analog_serial.ino").read_text(), "noise")
    noise = json.loads((EXAMPLES / "noise_scenario.json").read_text())
    one = runner.run(built.elf, noise, "noise a").trace
    two = runner.run(built.elf, noise, "noise b").trace
    other = runner.run(built.elf, {**noise, "seed": 43}, "noise c").trace
    keys = ("serial_log", "pin_events", "input_trace")
    check(all(one[k] == two[k] for k in keys), "seed 42 twice is identical")
    check(one["input_trace"] != other["input_trace"], "seed 43 differs")
    a1 = [p["mv"] for p in one["input_trace"] if p["pin"] == "A1"]
    print(f"  floating A1 range {min(a1):.0f} to {max(a1):.0f} mV over {len(a1)} points")
    check(max(a1) - min(a1) > 200, "floating pin wanders")

    print("\n== exit_reason: sleep_deadlock")
    built = runner.compile((EXAMPLES / "sleep_deadlock.ino").read_text(), "sleep")
    check(built.ok, "sleep sketch compiles")
    trace = runner.run(built.elf, {"seed": 1, "duration_ms": 3000}, "sleep").trace
    print(f"  exit_reason={trace.get('exit_reason')} sim_ms={trace.get('sim_ms')} serial={[l['text'] for l in trace['serial_log']]}")
    check(trace.get("exit_reason") == "sleep_deadlock", "reports sleep_deadlock")

    print("\n== exit_reason: crash")
    built = runner.compile((EXAMPLES / "wild_jump.ino").read_text(), "wild jump")
    check(built.ok, "wild jump sketch compiles")
    result = runner.run(built.elf, {"seed": 1, "duration_ms": 2000}, "wild jump")
    trace = result.trace
    print(f"  exit_reason={trace.get('exit_reason')} sim_ms={trace.get('sim_ms')} wall_ms={trace.get('wall_ms')} serial={[l['text'] for l in trace.get('serial_log', [])]}")
    check(trace.get("exit_reason") == "crash", "reports crash")

    print("\n== Hostile includes at compile time")
    built = runner.compile((EXAMPLES / "hostile_includes.ino").read_text(), "hostile")
    print(f"  ok={built.ok} violations={built.record.violations}")
    print("  " + built.log.strip().replace("\n", "\n  ")[:900])
    check(not built.ok, "hostile sketch does not compile")
    check(any(v["type"] == "file_read_attempt" for v in built.record.violations), "file read attempts recorded")
    check(built.record.removed, "container removed")

    print("\n== Runaway firmware with no simulated-time cap: only the wall clock can stop it")
    built = runner.compile((EXAMPLES / "runaway.ino").read_text(), "runaway")
    check(built.ok, "runaway compiles")
    start = time.monotonic()
    result = runner.run(built.elf, {"seed": 1, "duration_ms": 1000}, "runaway", no_sim_cap=True)
    print(f"  wall {time.monotonic() - start:.1f} s, timed_out={result.record.timed_out} exit={result.record.exit_code} removed={result.record.removed} violations={result.record.violations}")
    check(result.record.timed_out, "killed by wall-clock limit")
    check(result.record.removed, "container removed after kill")

    print("\n== Probe: what a program inside the sandbox sees")
    facts, record = runner.probe()
    print("  " + json.dumps(facts))
    show_record(record)
    print(f"  limits per docker inspect: {json.dumps(record.limits)}")

    check(facts.get("network") == "blocked" and facts.get("dns") == "blocked", "no network or DNS")
    check(facts.get("rootfs") == "read-only", "rootfs is read-only")
    check(facts.get("docker_sock") == "absent", "no Docker socket")
    check(facts.get("cap_eff") == "0000000000000000", "zero effective capabilities")
    check(facts.get("uid") == "1000", "non-root")
    check(facts.get("ssh_key") == "absent", "no SSH key to steal")
    check("PATH" in facts.get("proc_environ_names", []), "environ probe really read the environment")
    check(not any(k in facts.get("proc_environ_names", []) for k in ("LLM_API_KEY", "DEMO_PASSCODE")), "no control-plane secrets in environ")

    print("\nALL STEP 0 CHECKS PASSED")


if __name__ == "__main__":
    main()
