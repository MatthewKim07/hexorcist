"""Drive Build mode through the running HTTP API: describe a device, then attack what the model wrote.

Run from backend/: python -m scripts.run_build [--api URL] [--repeat N] [task ...]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import httpx

from scripts.run_presets import follow, print_table, result_row, summarize

TASKS = {
    "stairlight": (
        "Stairwell light. A push button on D2 wired to ground, using the internal pull-up, bounces for up to 20 ms. "
        "A press turns on the light on D7 within 100 ms, and the light stays on for 4 seconds, then turns off by itself. "
        "A press while the light is on restarts the 4 seconds."
    ),
    "pump": (
        "Water tank pump controller. A level sensor on A0 outputs 10 mV per percent of tank level. The pump on D6 turns ON when the level "
        "falls to 20 percent or below and turns OFF when it rises to 80 percent or above, within 500 ms. If the sensor reads below 2 percent or above 98 percent "
        "it is faulty, and the pump must go OFF within 1000 ms. Print one line every 1000 ms in the form 'Level: <value> %', accurate to within 2 percent."
    ),
    "doorbell": (
        "Doorbell with a heartbeat. A push button on D3 wired to ground with the internal pull-up, bouncing for up to 10 ms. A press as short as 50 ms rings the chime on D5 "
        "within 100 ms, for exactly 2 seconds, and a press during a ring is ignored. Print 'alive' over serial every 1000 ms at all times, including during a ring."
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    # From the environment, so a passcode never sits on a command line.
    parser.add_argument("--passcode", default=os.environ.get("DEMO_PASSCODE", ""))
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("tasks", nargs="*")
    args = parser.parse_args()

    headers = {"X-Demo-Passcode": args.passcode} if args.passcode else {}
    bad = 0
    rows: list[dict] = []
    with httpx.Client(base_url=args.api, headers=headers, timeout=60) as client:
        health = client.get("/api/health").json()
        print(f"health ok={health['ok']} llm={health['llm_model']} at {health['llm_base_url']}")
        for round_number in range(args.repeat):
            for name, description in TASKS.items():
                if args.tasks and name not in args.tasks:
                    continue
                print(f"\n===== build {name} (round {round_number + 1} of {args.repeat}) =====")
                start = time.monotonic()
                created = client.post("/api/runs", json={"mode": "build", "title": name, "description": description})
                if created.status_code != 201:
                    print(f"  REJECTED {created.status_code}: {created.text[:300]}")
                    bad += 1
                    continue
                run_id = created.json()["run_id"]
                print(f"  run {run_id} guard={created.json()['guard']['allowed']}")
                follow(client, run_id, not args.quiet)
                run = client.get(f"/api/runs/{run_id}").json()
                seconds = time.monotonic() - start
                print(f"  took {seconds:.0f} s")
                summarize(run)
                report = run.get("report") or {}
                build = report.get("build") or {}
                print(f"  BUILD title={build.get('title')!r} compile attempts={len(build.get('attempts', []))}")
                print(f"  SPEC {report.get('spec', {}).get('behaviour', '')[:500]}")
                print(f"  ASSERTIONS {[a.get('type') for a in report.get('assertions', [])]}")
                rows.append(result_row(name, {**run, "id": run_id}, seconds))
                # A clean first draft and a verified repair are both a pass for Build mode.
                if run["status"] not in ("clean", "fixed"):
                    bad += 1
    print_table(rows)
    print(f"\n{'ALL TASKS SURVIVED THE ATTACK' if bad == 0 else f'{bad} RUN(S) DID NOT'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
