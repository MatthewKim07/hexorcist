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
from bench.llm_budget import cost_by_bucket, estimate_cost


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
                        "assertion_id": b.get("assertion_id"),
                        "found_by_search": bool(b.get("found_by_search")),
                        "verified": b.get("verified"),
                        "evidence": b.get("evidence"),
                        "root_cause": b.get("root_cause"),
                    }
                )
            fix = report.get("fix") or {}
            llm = report.get("llm") or {}
            # Prefer report.llm; fall back to top-level run fields if the API shape differs.
            model = llm.get("model") or run.get("model") or ""
            prompt_tokens = int(llm.get("prompt_tokens") or run.get("prompt_tokens") or 0)
            completion_tokens = int(llm.get("completion_tokens") or run.get("completion_tokens") or 0)
            cost = llm.get("cost_usd")
            # Each endpoint is priced on its own tokens: the agent's model (DeepSeek) and clean room 2's (OpenAI).
            providers = llm.get("providers") or []
            by_bucket = cost_by_bucket(providers, model, prompt_tokens, completion_tokens)
            if cost is None and by_bucket:
                cost = round(sum(by_bucket.values()), 8)
            rows.append(
                {
                    "case_id": cid,
                    "run_id": run.get("id") or rid,
                    "status": run.get("status"),
                    "bugs": bugs,
                    "patched_sketch": fix.get("patched_firmware") or "",
                    "wall_s": round(time.monotonic() - t0, 2),
                    "llm_calls": llm.get("calls") or run.get("llm_calls"),
                    "prompt_tokens": prompt_tokens or None,
                    "completion_tokens": completion_tokens or None,
                    "cost_usd": cost,
                    "cost_deepseek_usd": round(by_bucket.get("deepseek", 0.0), 8),
                    "cost_openai_usd": round(by_bucket.get("openai", 0.0), 8),
                    "cost_other_usd": round(by_bucket.get("other", 0.0), 8),
                    "providers": providers,
                    "model": model or None,
                    # What the cross-check, the spec grounding and the stimulus search did on this case.
                    "claimed_fixed": run.get("status") == "fixed",
                    "unconfirmed": [
                        {"assertion_id": u.get("assertion_id"), "type": u.get("assertion_type"), "requirement": u.get("requirement"), "your_firmware": u.get("your_firmware"), "clean_room": u.get("clean_room"), "failing_scenarios": u.get("failing_scenarios"), "shared_scenarios": u.get("shared_scenarios")}
                        for u in (report.get("cross_check") or {}).get("unconfirmed", [])
                    ],
                    # Checks left out because they ask for more than the spec bullet they quote (backend/app/requirements.py).
                    "ungrounded": [
                        {k: u.get(k) for k in ("assertion_id", "assertion_type", "rule", "reason", "spec_quote", "failing_scenarios")}
                        for u in report.get("ungrounded") or []
                    ],
                    "cross_check": {
                        **{k: v for k, v in (report.get("cross_check") or {}).items() if k in ("status", "reason", "rule", "usage", "model_diversity")},
                        # Per room, without the sketch itself: which model wrote it, whether it built, what it cost.
                        "rooms": [{k: r.get(k) for k in ("index", "model", "host", "status", "reason", "repaired", "llm_calls", "prompt_tokens", "completion_tokens")} for r in (report.get("cross_check") or {}).get("rooms", [])],
                    },
                    "search": {k: v for k, v in (report.get("search") or {}).items() if k != "mutations"},
                    "found_by_search": [b.get("assertion_id") for b in report.get("bugs") or [] if b.get("found_by_search")],
                    "grounding": {"checked": (report.get("grounding") or {}).get("checked"), "dropped": (report.get("grounding") or {}).get("dropped", [])},
                    "llm_by_step": llm.get("by_step"),
                    "assertion_ids": {b.get("id"): b.get("assertion_id") for b in report.get("bugs") or []},
                }
            )
            print(
                f"{cid}: status={run.get('status')} bugs={len(bugs)} "
                f"time={rows[-1]['wall_s']}s cost={cost}"
            )

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
