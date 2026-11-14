"""Submit each case through the live Hexorcist Find-bugs API (system B)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT)]
load_dotenv(_ROOT / ".env", override=False)

from bench.case_io import RESULTS_DIR, list_case_ids, load_case, write_json


def wait_done(client: httpx.Client, run_id: str, timeout_s: float = 900) -> dict:
    after = 0
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = client.get(f"/api/runs/{run_id}/events.json", params={"after": after}, timeout=60)
        r.raise_for_status()
        body = r.json()
        events = body.get("events") or []
        if events:
            after = events[-1].get("seq", after)
        if body.get("done"):
            break
        time.sleep(1.5)
    run = client.get(f"/api/runs/{run_id}", timeout=60)
    run.raise_for_status()
    return run.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--api", default=os.environ.get("HEXORCIST_API", "http://127.0.0.1:8080"))
    ap.add_argument("--passcode", default=os.environ.get("DEMO_PASSCODE", ""))
    ap.add_argument("--run-id", default="")
    ap.add_argument("--max-cases", type=int, default=0, help="Optional early stop for dry runs")
    args = ap.parse_args()

    run_id = args.run_id or f"hexorcist_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    ids = args.cases or list_case_ids()
    if args.max_cases:
        ids = ids[: args.max_cases]

    headers = {"X-Demo-Passcode": args.passcode} if args.passcode else {}
    rows = []
    with httpx.Client(base_url=args.api, headers=headers, timeout=60) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        print("health", {k: health.json().get(k) for k in ("ok", "llm_configured", "llm_model", "passcode_required")})

        for cid in ids:
            case = load_case(cid)
            payload = {
                "mode": "break",
                "title": f"bench:{cid}",
                "firmware": case.sketch,
                "pins": case.pins,
                "behaviour": case.spec.strip(),
                "compare": False,
            }
            # Never send truth.json or checks.json.
            t0 = time.monotonic()
            try:
                resp = client.post("/api/runs", json=payload, timeout=60)
                if resp.status_code >= 400:
                    rows.append(
                        {
                            "case_id": cid,
                            "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                            "bugs": [],
                            "patched_sketch": "",
                            "wall_s": round(time.monotonic() - t0, 2),
                        }
                    )
                    print(cid, "POST failed", resp.status_code)
                    continue
                rid = resp.json()["run_id"]
                run = wait_done(client, rid)
            except Exception as exc:
                rows.append({"case_id": cid, "error": str(exc)[:300], "bugs": [], "patched_sketch": "", "wall_s": round(time.monotonic() - t0, 2)})
                print(cid, "error", exc)
                continue

            report = run.get("report") or {}
            bugs = []
            for b in report.get("bugs") or []:
                bugs.append(
                    {
                        "id": b.get("id"),
                        "title": b.get("title") or b.get("requirement"),
                        "description": " ".join(
                            x for x in [b.get("root_cause") or "", b.get("evidence") or ""] if x
                        ).strip(),
                        "assertion_type": b.get("assertion_type"),
                        "verified": b.get("verified"),
                        "evidence": b.get("evidence"),
                        "root_cause": b.get("root_cause"),
                    }
                )
            fix = report.get("fix") or {}
            llm = report.get("llm") or {}
            rows.append(
                {
                    "case_id": cid,
                    "run_id": run.get("id") or rid,
                    "status": run.get("status"),
                    "bugs": bugs,
                    "patched_sketch": fix.get("patched_firmware") or "",
                    "wall_s": round(time.monotonic() - t0, 2),
                    "llm_calls": llm.get("calls"),
                    "prompt_tokens": llm.get("prompt_tokens"),
                    "completion_tokens": llm.get("completion_tokens"),
                    "cost_usd": None,  # filled by scorer projection / llm report elsewhere
                    "model": llm.get("model"),
                }
            )
            print(f"{cid}: status={run.get('status')} bugs={len(bugs)} time={rows[-1]['wall_s']}s")

    out = {
        "run_id": run_id,
        "system": "hexorcist",
        "api": args.api,
        "cases": rows,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{run_id}.json"
    write_json(path, out)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
