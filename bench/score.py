"""Score baseline (A) or Hexorcist (B) outputs against frozen ground truth."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT), str(_ROOT / "backend")]

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env", override=False)

from bench.case_io import JUDGEMENTS_DIR, RESULTS_DIR, Case, load_case, load_cases, write_json
from bench.evaluate_gt import build_spec, default_runner, load_assertions, load_scenarios, run_firmware
from bench.llm_budget import (
    DEFAULT_JUDGE_MODEL,
    Budget,
    BudgetExceeded,
    BudgetLLM,
    endpoint_from_env,
    estimate_cost,
)

PROMPTS = Path(__file__).resolve().parent / "prompts"


def _judge_endpoint():
    ep = endpoint_from_env("OPENAI")
    if not ep.configured:
        # Fall back to the app LLM for local dry runs when OPENAI_* is unset.
        ep = endpoint_from_env("LLM")
        ep.name = "judge-fallback"
    if not ep.model:
        ep.model = DEFAULT_JUDGE_MODEL
    return ep


def _plain_check_behaviour(assertion: dict[str, Any]) -> str:
    """One plain-English line for what an exposing check observes."""
    t = assertion.get("type") or ""
    pin = assertion.get("pin") or assertion.get("output_pin") or ""
    desc = (assertion.get("description") or "").strip()
    if t == "output_follows":
        hw = assertion.get("high_when") or {}
        lw = assertion.get("low_when") or {}
        within = assertion.get("within_ms")
        parts = [f"{pin} must follow its stimulus"]
        if hw:
            parts.append(f"HIGH when {hw.get('pin')} {hw.get('op')} {hw.get('value')}")
        if lw:
            parts.append(f"LOW when {lw.get('pin')} {lw.get('op')} {lw.get('value')}")
        if within is not None:
            parts.append(f"within {within} ms")
        return "; ".join(parts) + (f" ({desc})" if desc else "")
    if t == "max_toggles":
        return (
            f"{pin} must not toggle more than {assertion.get('max_toggles')} times "
            f"in any {assertion.get('window_ms')} ms window"
            + (f" ({desc})" if desc else "")
        )
    if t == "safe_state_on_fault":
        safe = assertion.get("safe_value", assertion.get("expected"))
        fault = assertion.get("fault_when") or "fault condition"
        return (
            f"{pin or 'output'} must stay {safe} during sensor fault ({fault})"
            + (f" ({desc})" if desc else "")
        )
    if t == "serial_period":
        return (
            f"serial lines matching {assertion.get('pattern')!r} every "
            f"{assertion.get('period_ms')} ms"
            + (f" ({desc})" if desc else "")
        )
    if t == "serial_value_matches":
        return (
            f"serial values for {assertion.get('pattern')!r} match the stimulus "
            f"(tolerance {assertion.get('tolerance')})"
            + (f" ({desc})" if desc else "")
        )
    if t == "timed_pulse":
        return (
            f"{pin} pulse length around {assertion.get('pulse_ms')} ms "
            f"(tolerance {assertion.get('tolerance_ms')} ms)"
            + (f" ({desc})" if desc else "")
        )
    if t == "toggle_per_press":
        return f"{pin} toggles exactly once per settled press on {assertion.get('button_pin')}" + (
            f" ({desc})" if desc else ""
        )
    if t == "responsive":
        return f"{pin} responds to stimulus within {assertion.get('within_ms')} ms" + (
            f" ({desc})" if desc else ""
        )
    if t == "no_crash":
        return "firmware must not crash"
    return desc or f"{t} on {pin}".strip()


def truth_bugs_for_judge(case: Case) -> list[dict[str, Any]]:
    """Truth bugs plus plain-language exposing-check behaviour for the judge."""
    by_id = {a.get("id"): a for a in (case.checks.get("assertions") or []) if isinstance(a, dict)}
    out = []
    for bug in case.truth:
        exposing = []
        for cid in bug.get("check_ids") or []:
            a = by_id.get(cid)
            if a:
                exposing.append(
                    {
                        "check_id": cid,
                        "type": a.get("type"),
                        "behaviour": _plain_check_behaviour(a),
                    }
                )
            else:
                exposing.append({"check_id": cid, "behaviour": f"unknown check {cid}"})
        out.append(
            {
                "id": bug.get("id"),
                "category": bug.get("category"),
                "description": bug.get("description"),
                "check_ids": bug.get("check_ids") or [],
                "exposing_checks": exposing,
            }
        )
    return out


def match_bugs_with_judge(
    case: Case,
    reported: list[dict[str, Any]],
    judge: BudgetLLM,
    run_id: str,
    system_name: str,
) -> dict[str, Any]:
    truth = case.truth
    if not truth and not reported:
        return {"matched_truth_ids": [], "false_alarms": [], "false_alarm_count": 0, "judgement": None}

    system = (PROMPTS / "judge_match.txt").read_text()
    user_payload = {
        "case_id": case.id,
        "spec": case.spec.strip(),
        "truth_bugs": truth_bugs_for_judge(case),
        "reported_bugs": reported,
    }
    user = json.dumps(user_payload, indent=2)
    raw = judge.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        step=f"judge:{system_name}:{case.id}",
        max_tokens=500,
        temperature=0.0,
        json_mode=True,
    )
    text = raw["text"]
    try:
        start, end = text.find("{"), text.rfind("}")
        judgement = json.loads(text[start : end + 1])
    except Exception:
        judgement = {"matches": [], "parse_error": text[:500]}

    JUDGEMENTS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(
        JUDGEMENTS_DIR / f"{run_id}_{system_name}_{case.id}.json",
        {
            "case_id": case.id,
            "system": system_name,
            "reported": reported,
            "truth": truth,
            "truth_for_judge": user_payload["truth_bugs"],
            "judge_input": user_payload,
            "raw": text,
            "judgement": judgement,
            "usage": {k: raw[k] for k in ("model", "prompt_tokens", "completion_tokens", "cost_usd", "cached")},
        },
    )

    matched: list[str] = []
    credited: set[int] = set()  # reports that detect a truth bug (primary or duplicate)
    for m in judgement.get("matches") or []:
        if m.get("matched") and m.get("truth_id"):
            matched.append(str(m["truth_id"]))
            idx = m.get("reported_index", -1)
            if isinstance(idx, int) and idx >= 0:
                credited.add(idx)
    for d in judgement.get("duplicate_of_truth") or []:
        idx = d.get("reported_index", -1)
        if isinstance(idx, int) and idx >= 0:
            credited.add(idx)

    # Prefer judge's unique_false_alarm_indices (deduped); else unmatched after removing credited.
    # The judge sometimes returns an index equal to len(reported); drop indices that name no report.
    uniq = judgement.get("unique_false_alarm_indices")
    if isinstance(uniq, list) and all(isinstance(i, int) for i in uniq):
        uniq = [i for i in uniq if 0 <= i < len(reported)]
        false_alarms = sorted(set(uniq))
    else:
        unmatched = judgement.get("unmatched_reported")
        if isinstance(unmatched, list) and unmatched and all(isinstance(i, int) for i in unmatched):
            false_alarms = sorted({i for i in unmatched if i not in credited})
        else:
            false_alarms = sorted(i for i in range(len(reported)) if i not in credited)

    if case.is_correct:
        # All reports are FAs; count unique root-cause clusters only.
        if isinstance(uniq, list) and uniq:
            fa_count = len(set(uniq))
        else:
            fa_count = len(false_alarms) if false_alarms else len(reported)
        false_alarms = list(range(len(reported))) if not false_alarms and reported else false_alarms
    else:
        fa_count = len(false_alarms)

    return {
        "matched_truth_ids": matched,
        "false_alarms": false_alarms,
        "false_alarm_count": fa_count,
        "judgement": judgement,
    }


def verify_patch(case: Case, patched: str | None, runner) -> dict[str, Any]:
    if not patched or not patched.strip():
        return {"compiles": False, "fixed": False, "failing_ids": [], "compile_log": "no patch"}
    spec = build_spec(case)
    assertions = load_assertions(case)
    scenarios = load_scenarios(case)
    result = run_firmware(runner, patched, spec, assertions, scenarios, f"score:{case.id}:patch")
    if not result["compile_ok"]:
        return {"compiles": False, "fixed": False, "failing_ids": [], "compile_log": result["compile_log"][:800]}
    failing = sorted(result["failing_ids"])
    return {"compiles": True, "fixed": len(failing) == 0, "failing_ids": failing, "compile_log": ""}


def score_system(
    system_name: str,
    case_results: list[dict[str, Any]],
    judge: BudgetLLM | None,
    run_id: str,
    runner,
) -> dict[str, Any]:
    rows = []
    cat_stats: dict[str, Counter] = defaultdict(Counter)
    for cr in case_results:
        case = load_case(cr["case_id"])
        reported = cr.get("bugs") or []
        # Normalize reported shape
        norm = []
        for i, b in enumerate(reported):
            if isinstance(b, str):
                norm.append({"id": f"r{i}", "title": b, "description": b})
            else:
                norm.append(
                    {
                        "id": b.get("id") or f"r{i}",
                        "title": b.get("title") or b.get("requirement") or "",
                        "description": b.get("description") or b.get("root_cause") or b.get("evidence") or "",
                        "category": b.get("category") or b.get("assertion_type") or "",
                    }
                )

        if judge is None:
            match = {
                "matched_truth_ids": [],
                "false_alarms": list(range(len(norm))),
                "false_alarm_count": len(norm),
                "judgement": None,
            }
        else:
            match = match_bugs_with_judge(case, norm, judge, run_id, system_name)

        truth_ids = [b["id"] for b in case.truth]
        detected = set(match["matched_truth_ids"])
        detection = {tid: tid in detected for tid in truth_ids}
        false_alarm_count = int(match.get("false_alarm_count", len(match.get("false_alarms") or [])))

        patch = cr.get("patched_sketch") or cr.get("patched_firmware")
        verify = verify_patch(case, patch, runner)

        cost = cr.get("cost_usd")
        if cost is None:
            pt = cr.get("prompt_tokens") or 0
            ct = cr.get("completion_tokens") or 0
            model = cr.get("model") or ""
            if pt or ct:
                cost = round(estimate_cost(model, int(pt), int(ct)), 8)

        row = {
            "case_id": case.id,
            "categories": case.categories,
            "truth_bugs": len(truth_ids),
            "detected": sum(1 for v in detection.values() if v),
            "detection": detection,
            "reported": len(norm),
            "false_alarms": false_alarm_count,
            "compiles": verify["compiles"],
            "fixed": verify["fixed"],
            "verify_failing": verify["failing_ids"],
            "wall_s": cr.get("wall_s"),
            "llm_calls": cr.get("llm_calls"),
            "prompt_tokens": cr.get("prompt_tokens"),
            "completion_tokens": cr.get("completion_tokens"),
            "cost_usd": cost,
            "model": cr.get("model"),
        }
        rows.append(row)
        for cat in case.categories:
            cat_stats[cat]["cases"] += 1
            cat_stats[cat]["truth_bugs"] += len(truth_ids) if cat != "correct" else 0
            if cat == "correct":
                cat_stats[cat]["false_alarms"] += false_alarm_count
            else:
                # attribute detection to each category bug
                for bug in case.truth:
                    if bug.get("category") == cat:
                        cat_stats[cat]["truth_bugs_cat"] += 1
                        if bug["id"] in detected:
                            cat_stats[cat]["detected"] += 1
            cat_stats[cat]["fixed"] += 1 if verify["fixed"] else 0
            cat_stats[cat]["compiles"] += 1 if verify["compiles"] else 0

    total_truth = sum(r["truth_bugs"] for r in rows)
    total_detected = sum(r["detected"] for r in rows)
    total_fa = sum(r["false_alarms"] for r in rows)
    return {
        "system": system_name,
        "cases": len(rows),
        "detection_recall": (total_detected / total_truth) if total_truth else None,
        "bugs_detected": total_detected,
        "bugs_truth": total_truth,
        "false_alarms": total_fa,
        "compile_rate": sum(1 for r in rows if r["compiles"]) / len(rows) if rows else 0,
        "fix_rate": sum(1 for r in rows if r["fixed"]) / len(rows) if rows else 0,
        "per_category": {k: dict(v) for k, v in sorted(cat_stats.items())},
        "rows": rows,
    }


def markdown_summary(payload: dict[str, Any]) -> str:
    lines = [f"# Benchmark {payload['run_id']}", "", f"Generated {payload['created_at']}", ""]
    for block in payload.get("systems") or []:
        lines.append(f"## {block['system']}")
        lines.append("")
        lines.append(
            f"- Detection recall: {block['detection_recall'] if block['detection_recall'] is not None else 'n/a'} "
            f"({block['bugs_detected']}/{block['bugs_truth']})"
        )
        lines.append(f"- False alarms: {block['false_alarms']}")
        lines.append(f"- Compile rate: {block['compile_rate']:.2%}")
        lines.append(f"- Verified-fix rate: {block['fix_rate']:.2%}")
        lines.append("")
        lines.append("| Case | Cats | Det | FA | Compile | Fixed | Time s | Cost |")
        lines.append("| --- | --- | ---: | ---: | --- | --- | ---: | ---: |")
        for r in block["rows"]:
            cost = r.get("cost_usd")
            cost_s = "-" if cost is None else cost
            wall = r.get("wall_s")
            wall_s = "-" if wall is None else wall
            lines.append(
                f"| {r['case_id']} | {','.join(r['categories'])} | {r['detected']}/{r['truth_bugs']} | "
                f"{r['false_alarms']} | {r['compiles']} | {r['fixed']} | {wall_s} | {cost_s} |"
            )
        lines.append("")
    if payload.get("budget"):
        lines.append("## Budget")
        lines.append("```")
        lines.append(json.dumps(payload["budget"], indent=2))
        lines.append("```")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    ap.add_argument("--baseline", type=Path, help="JSONL or JSON from run_baseline")
    ap.add_argument("--hexorcist", type=Path, help="JSONL or JSON from run_hexorcist")
    ap.add_argument("--max-cost-deepseek", type=float, default=0.80)
    ap.add_argument("--max-cost-openai", type=float, default=3.00)
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args()

    budget = Budget(max_cost_deepseek=args.max_cost_deepseek, max_cost_openai=args.max_cost_openai)
    judge = None
    if not args.no_judge:
        judge = BudgetLLM(_judge_endpoint(), budget)

    def load_results(path: Path) -> list[dict]:
        text = path.read_text()
        if path.suffix == ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        data = json.loads(text)
        return data if isinstance(data, list) else data.get("cases", [])

    runner = default_runner()
    systems = []
    try:
        if args.baseline:
            systems.append(score_system("baseline", load_results(args.baseline), judge, args.run_id, runner))
        if args.hexorcist:
            systems.append(score_system("hexorcist", load_results(args.hexorcist), judge, args.run_id, runner))
    except BudgetExceeded as exc:
        print(f"BUDGET STOP: {exc}", file=sys.stderr)

    payload = {
        "run_id": args.run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "systems": systems,
        "budget": budget.summary(),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_json = RESULTS_DIR / f"{args.run_id}.json"
    out_md = RESULTS_DIR / f"{args.run_id}.md"
    write_json(out_json, payload)
    out_md.write_text(markdown_summary(payload))
    print(out_md.read_text())
    print(f"wrote {out_json} and {out_md}")


if __name__ == "__main__":
    main()
