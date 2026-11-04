"""Drive every preset through the running HTTP API, following its SSE stream, and summarize.

Run from backend/: python -m scripts.run_presets [--api URL] [preset ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import httpx


def follow(client: httpx.Client, run_id: str, verbose: bool) -> None:
    with client.stream("GET", f"/api/runs/{run_id}/events", timeout=None) as stream:
        for line in stream.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if not verbose:
                continue
            if event.get("type") == "step":
                print(f"    [{event['step']:<10}] {event['status']:<8} {event.get('detail', '')[:110]}")
            elif event.get("type") == "warning":
                print(f"    WARNING {event['detail'][:140]}")


def summarize(run: dict) -> None:
    report = run.get("report") or {}
    score = report.get("score", {})
    print(f"  STATUS {run['status']}  score={score}")
    if report.get("error"):
        print(f"  ERROR {report['error'][:300]}")
    for bug in report.get("bugs", []):
        mark = "VERIFIED" if bug["verified"] else "not verified"
        print(f"  - [{bug['severity']}] {bug['title'][:70]} ({mark})")
        print(f"      evidence: {bug['evidence'][:170]}")
        if bug.get("root_cause"):
            print(f"      cause: {bug['root_cause'][:220]}")
        if bug.get("after"):
            print(f"      after: {bug['after']['status']}: {bug['after']['evidence'][:130]}")
    fix = report.get("fix")
    if fix:
        print(f"  FIX iteration {fix['iteration']}, +{fix['diff']['added']} -{fix['diff']['removed']} lines, all_passing={fix['all_passing']}, regressions={len(fix['regressions'])}")
    contained = report.get("contained")
    if contained:
        print(f"  CONTAINED {contained['contained']}")
        for check in contained["checks"]:
            print(f"    {'ok ' if check['ok'] else 'NO '} {check['label']}: {check['detail'][:130]}")
        print(f"    attacker got: {json.dumps(contained['what_the_attacker_got'])[:260]}")
    box = report.get("containment", {})
    print(f"  SANDBOX {box.get('total')} containers, {box.get('removed')} removed, network_none={box.get('network_none')}, secrets={box.get('secrets_found')}, timeouts={box.get('timeouts')}, oom={box.get('oom_kills')}")
    llm = report.get("llm", {})
    print(f"  LLM model={llm.get('model')} calls={llm.get('calls')} repairs={llm.get('repairs')} tokens={llm.get('prompt_tokens')}+{llm.get('completion_tokens')}")
    for w in report.get("warnings", []):
        print(f"  warning: {w[:170]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--passcode", default="")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("presets", nargs="*")
    args = parser.parse_args()

    headers = {"X-Demo-Passcode": args.passcode} if args.passcode else {}
    bad = 0
    with httpx.Client(base_url=args.api, headers=headers, timeout=60) as client:
        health = client.get("/api/health").json()
        print(f"health ok={health['ok']} llm={health['llm_model']} at {health['llm_base_url']}")
        for preset in client.get("/api/presets").json():
            if args.presets and preset["id"] not in args.presets:
                continue
            print(f"\n===== {preset['id']}: {preset['title']} =====")
            start = time.monotonic()
            created = client.post("/api/runs", json={"mode": "break", "title": preset["title"], "firmware": preset["firmware"], "pins": preset["pins"], "behaviour": preset["behaviour"]})
            if created.status_code != 201:
                print(f"  REJECTED {created.status_code}: {created.text[:300]}")
                bad += 1
                continue
            run_id = created.json()["run_id"]
            print(f"  run {run_id} guard={created.json()['guard']['allowed']} score={created.json()['guard']['score']}")
            follow(client, run_id, not args.quiet)
            run = client.get(f"/api/runs/{run_id}").json()
            print(f"  took {time.monotonic() - start:.0f} s")
            summarize(run)
            expected = "contained" if preset["id"] == "containment" else "fixed"
            if run["status"] != expected:
                bad += 1
    print(f"\n{'ALL PRESETS REACHED THEIR EXPECTED STATE' if bad == 0 else f'{bad} PRESET(S) DID NOT'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
