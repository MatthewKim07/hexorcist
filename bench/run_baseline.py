"""Plain LLM review baseline (system A). One call per case + at most one parse retry."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT), str(_ROOT / "backend")]

from bench.case_io import PROMPTS_DIR, RESULTS_DIR, list_case_ids, load_case, write_json
from bench.llm_budget import Budget, BudgetExceeded, BudgetLLM, endpoint_from_env

# Reuse extract helpers without importing async client side effects beyond config dotenv.
from app.llm import extract_code, extract_json_text


def parse_review(text: str) -> dict:
    raw = extract_json_text(text)
    obj = json.loads(raw)
    bugs = obj.get("bugs") or []
    sketch = obj.get("patched_sketch") or obj.get("patched_firmware") or ""
    if not sketch:
        code = extract_code(text)
        sketch = code or ""
    return {"bugs": bugs, "patched_sketch": sketch}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--model", default="", help="Override LLM_MODEL / endpoint model")
    ap.add_argument("--endpoint", choices=["llm", "openai"], default="llm", help="llm=LLM_* env; openai=OPENAI_* env")
    ap.add_argument("--max-cost-deepseek", type=float, default=0.80)
    ap.add_argument("--max-cost-openai", type=float, default=3.00)
    ap.add_argument("--run-id", default="")
    args = ap.parse_args()

    run_id = args.run_id or f"baseline_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    ep = endpoint_from_env("OPENAI" if args.endpoint == "openai" else "LLM")
    if args.model:
        ep.model = args.model
    if not ep.configured:
        raise SystemExit(f"endpoint {args.endpoint} is not configured (need base URL, key, model)")

    budget = Budget(max_cost_deepseek=args.max_cost_deepseek, max_cost_openai=args.max_cost_openai)
    llm = BudgetLLM(ep, budget)
    system = (PROMPTS_DIR / "baseline_review.txt").read_text()
    ids = args.cases or list_case_ids()
    rows = []
    stopped = None

    for cid in ids:
        case = load_case(cid)
        user = (
            f"## Pin map\n```json\n{json.dumps(case.pins, indent=2)}\n```\n\n"
            f"## Behaviour\n{case.spec.strip()}\n\n"
            f"## Sketch\n```cpp\n{case.sketch.rstrip()}\n```\n"
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        t0 = time.monotonic()
        try:
            raw = llm.chat(messages, step=f"baseline:{cid}", max_tokens=4000, temperature=0.0, json_mode=True)
            try:
                parsed = parse_review(raw["text"])
            except Exception:
                # One repair retry only.
                repair = messages + [
                    {"role": "assistant", "content": raw["text"][:2000]},
                    {"role": "user", "content": "Your previous reply was not valid JSON of the required shape. Reply again with only the JSON object."},
                ]
                raw = llm.chat(repair, step=f"baseline_retry:{cid}", max_tokens=4000, temperature=0.0, json_mode=True, allow_retry=False)
                parsed = parse_review(raw["text"])
        except BudgetExceeded as exc:
            stopped = str(exc)
            print(f"BUDGET STOP on {cid}: {exc}")
            break
        except Exception as exc:
            rows.append(
                {
                    "case_id": cid,
                    "error": str(exc)[:300],
                    "bugs": [],
                    "patched_sketch": "",
                    "wall_s": round(time.monotonic() - t0, 2),
                    "llm_calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost_usd": 0,
                }
            )
            continue

        rows.append(
            {
                "case_id": cid,
                "bugs": parsed["bugs"],
                "patched_sketch": parsed["patched_sketch"],
                "wall_s": round(time.monotonic() - t0, 2),
                "llm_calls": 1 if not raw.get("cached") else 0,
                "prompt_tokens": raw.get("prompt_tokens", 0),
                "completion_tokens": raw.get("completion_tokens", 0),
                "cost_usd": raw.get("cost_usd", 0),
                "cached": raw.get("cached", False),
                "model": ep.model,
            }
        )
        print(f"{cid}: bugs={len(parsed['bugs'])} cost={raw.get('cost_usd')} cached={raw.get('cached')}")

    out = {
        "run_id": run_id,
        "system": "baseline",
        "model": ep.model,
        "endpoint": args.endpoint,
        "stopped": stopped,
        "budget": budget.summary(),
        "cases": rows,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{run_id}.json"
    write_json(path, out)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
