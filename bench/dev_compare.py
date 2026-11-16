"""Compare a DEV-set Hexorcist run with an earlier one on the same frozen v2 cases and write the numbers.

Reads the score file (<run>_score.json or <run>_score_deepseek.json), the raw Hexorcist file, the judgements and,
for the new run, <run>_replay.json from bench.replay_run. Remaining false alarms are classified without manual
adjudication: a reported check that also fails on the case's known-good reference is class B (no correct firmware
can pass it). Everything else is "not explained by the reference" and needs a human reading.

"Honest recall" counts a planted bug as found only if a report the judge matched to it comes with evidence that
separates the buggy sketch from the correct one: some scenario where the check fails on the uploaded sketch and passes
on the known-good reference. A matched report whose check fails identically on the reference is a coincidence of
wording, not a detection.

Usage: backend/.venv/bin/python -m bench.dev_compare RUN [RUN ...]   (writes JSON to stdout; the first run is the oldest)
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from bench.case_io import JUDGEMENTS_DIR, RESULTS_DIR  # noqa: E402


def load_score(run: str) -> dict[str, dict]:
    for name in (f"{run}_score.json", f"{run}_score_deepseek.json"):
        p = RESULTS_DIR / name
        if p.is_file():
            data = json.loads(p.read_text())
            return {r["case_id"]: r for s in data["systems"] if s["system"] == "hexorcist" for r in s["rows"]}
    raise SystemExit(f"no score file for {run}")


def load_raw(run: str) -> dict[str, dict]:
    return {r["case_id"]: r for r in json.loads((RESULTS_DIR / f"{run}_hexorcist.json").read_text())["cases"]}


def fa_indices(run: str, case_id: str) -> tuple[list[int], list[dict]]:
    """Reported bugs the judge counted as false alarms, by the scorer's own rule."""
    for name in (f"{run}_score_hexorcist_{case_id}.json", f"{run}_hexorcist_{case_id}.json"):
        p = JUDGEMENTS_DIR / name
        if p.is_file():
            j = json.loads(p.read_text())
            reported, jd = j.get("reported") or [], j.get("judgement") or {}
            credited = {m["reported_index"] for m in jd.get("matches") or [] if m.get("matched") and isinstance(m.get("reported_index"), int)}
            credited |= {d["reported_index"] for d in jd.get("duplicate_of_truth") or [] if isinstance(d.get("reported_index"), int)}
            uniq = jd.get("unique_false_alarm_indices")
            if isinstance(uniq, list) and all(isinstance(i, int) for i in uniq):
                idx = sorted({i for i in uniq if 0 <= i < len(reported)})
            else:
                idx = sorted(i for i in range(len(reported)) if i not in credited)
            if not jd and reported:
                idx = list(range(len(reported)))
            return idx, reported
    return [], []


def user_failures(api: str, run_id: str) -> dict[str, set[str]]:
    """Scenarios where each check failed on the uploaded firmware (iteration 0 of the stored report)."""
    import httpx

    report = httpx.get(f"{api}/api/runs/{run_id}", timeout=60).json().get("report") or {}
    out: dict[str, set[str]] = {}
    for sid, results in (report.get("matrix") or {}).get("0", {}).items():
        for r in results:
            if r["status"] == "fail":
                out.setdefault(r["assertion_id"], set()).add(sid)
    return out


def judgement_path(run: str, case_id: str) -> Path | None:
    for name in (f"{run}_score_hexorcist_{case_id}.json", f"{run}_score_deepseek_hexorcist_{case_id}.json", f"{run}_hexorcist_{case_id}.json"):
        if (JUDGEMENTS_DIR / name).is_file():
            return JUDGEMENTS_DIR / name
    return None


def matched_reports(run: str, case_id: str) -> dict[str, list[int]]:
    """truth id -> reported indices the judge matched to it."""
    p = judgement_path(run, case_id)
    out: dict[str, list[int]] = {}
    if p is None:
        return out
    for m in (json.loads(p.read_text()).get("judgement") or {}).get("matches") or []:
        if m.get("matched") and m.get("truth_id") and isinstance(m.get("reported_index"), int):
            out.setdefault(str(m["truth_id"]), []).append(m["reported_index"])
    return out


def honest_recall(run: str, raw: dict, score: dict, replay: dict | None, old_replay: list | None) -> dict:
    """Detections whose matched report separates the buggy sketch from the reference."""
    honest, hollow = 0, []
    for c, row in score.items():
        if not row["truth_bugs"]:
            continue
        bugs = raw[c].get("bugs") or []
        user = None
        for truth_id, ok in (row.get("detection") or {}).items():
            if not ok:
                continue
            real = False
            for i in matched_reports(run, c).get(truth_id, []):
                if replay is not None:
                    a = bugs[i].get("assertion_id") if i < len(bugs) else None
                    ref = set((replay.get(c, {}).get("assertions", {}).get(a) or {}).get("ref_fail") or [])
                    if user is None:
                        user = user_failures(API, raw[c]["run_id"])
                    real = real or bool(user.get(a, set()) - ref)
                elif old_replay is not None:
                    r = next((x for x in old_replay if x["case"] == c and x["index"] == i), None)
                    real = real or bool(r and r["failing_scenarios"] > r["reference_also_fails"])
            if real:
                honest += 1
            else:
                hollow.append((c, truth_id))
    return {"honest_detected": honest, "hollow": hollow}


def med(xs):
    return statistics.median(xs) if xs else 0.0


def summarize(run: str, replay: dict | None, old_replay: list | None = None) -> dict:
    score, raw = load_score(run), load_raw(run)
    ids = sorted(score)
    buggy = [c for c in ids if score[c]["truth_bugs"]]
    corr = [c for c in ids if not score[c]["truth_bugs"]]
    out: dict = {"cases": len(ids), "buggy": len(buggy), "correct": len(corr)}
    out["truth"] = sum(score[c]["truth_bugs"] for c in buggy)
    out["detected"] = sum(score[c]["detected"] for c in buggy)
    out["fa_buggy"] = sum(score[c]["false_alarms"] for c in buggy)
    out["fa_correct"] = sum(score[c]["false_alarms"] for c in corr)
    out["frozen_pass_buggy"] = sum(1 for c in buggy if score[c]["fixed"])
    out["broke_correct"] = sum(1 for c in corr if score[c]["compiles"] and not score[c]["fixed"])
    out["status"] = {s: sum(1 for c in ids if raw[c]["status"] == s) for s in sorted({raw[c]["status"] for c in ids})}
    claimed = [c for c in ids if raw[c]["status"] == "fixed"]
    out["claimed_fixed"] = len(claimed)
    out["claimed_fixed_frozen_pass"] = sum(1 for c in claimed if score[c]["fixed"])
    out["claimed_fixed_buggy"] = sum(1 for c in claimed if c in buggy)
    out["patch_on_correct"] = sum(1 for c in corr if (raw[c].get("patched_sketch") or "").strip())
    out["cost"] = sum(float(raw[c].get("cost_usd") or 0) for c in ids)
    out["median_s"] = med([float(raw[c]["wall_s"]) for c in ids])
    out["total_s"] = sum(float(raw[c]["wall_s"]) for c in ids)
    out["errors"] = [c for c in ids if raw[c].get("error")]
    out["recall_missed"] = [c for c in buggy if score[c]["detected"] < score[c]["truth_bugs"]]
    # New-agent fields (absent in the first run).
    if any("unconfirmed" in raw[c] for c in ids):
        out["unconfirmed_total"] = sum(len(raw[c].get("unconfirmed") or []) for c in ids)
        out["unconfirmed_cases"] = sum(1 for c in ids if raw[c].get("unconfirmed"))
        out["xcheck_status"] = {s: sum(1 for c in ids if (raw[c].get("cross_check") or {}).get("status") == s) for s in sorted({(raw[c].get("cross_check") or {}).get("status", "?") for c in ids})}
        out["found_by_search_bugs"] = sum(len(raw[c].get("found_by_search") or []) for c in ids)
        out["found_by_search_cases"] = [c for c in ids if raw[c].get("found_by_search")]
        out["search_variants"] = sum((raw[c].get("search") or {}).get("variants_run", 0) or 0 for c in ids)
        out["search_failing_variants"] = sum((raw[c].get("search") or {}).get("failing_variants", 0) or 0 for c in ids)
        out["search_kept"] = sum(len((raw[c].get("search") or {}).get("kept") or []) for c in ids)
        out["search_discarded"] = sum(len((raw[c].get("search") or {}).get("discarded_by_clean_room") or []) for c in ids)
        out["search_wall_median"] = med([(raw[c].get("search") or {}).get("wall_s", 0) or 0 for c in ids])
        out["search_sandbox_s"] = sum((raw[c].get("search") or {}).get("sandbox_s", 0) or 0 for c in ids)
        out["cross_sandbox_s"] = sum(((raw[c].get("cross_check") or {}).get("usage") or {}).get("sandbox_s", 0) or 0 for c in ids)
        out["cross_tokens"] = sum(v.get("prompt_tokens", 0) + v.get("completion_tokens", 0) for c in ids for k, v in (raw[c].get("llm_by_step") or {}).items() if k.startswith("cleanroom"))
        out["grounding_checked"] = sum((raw[c].get("grounding") or {}).get("checked") or 0 for c in ids)
        out["grounding_dropped"] = sum(len((raw[c].get("grounding") or {}).get("dropped") or []) for c in ids)
    out.update(honest_recall(run, raw, score, replay, old_replay))
    if replay is not None:
        ref = lambda c, a: (replay.get(c, {}).get("assertions", {}).get(a) or {}).get("ref_fail")  # noqa: E731
        right, wrong, unknown = [], [], []
        for c in ids:
            sketch_pass_ref = []
            for u in raw[c].get("unconfirmed") or []:
                f = ref(c, u["assertion_id"])
                (unknown if f is None else right if f else wrong).append((c, u["assertion_id"], u["type"], bool(score[c]["truth_bugs"])))
        out["unconfirmed_reference"] = {"fails_on_reference": len(right), "passes_on_reference": len(wrong), "not_replayed": len(unknown)}
        out["unconfirmed_passes_reference"] = wrong
        fa_rows = []
        for c in ids:
            idx, reported = fa_indices(run, c)
            bugs = raw[c].get("bugs") or []
            for i in idx:
                # The judge saw the run's bugs in order, so index i is bugs[i].
                reported = bugs
                a = bugs[i].get("assertion_id") if i < len(bugs) else None
                f = ref(c, a) if a else None
                share = None
                if f is not None:
                    mine = user_failures(API, raw[c]["run_id"]).get(a, set())
                    share = len(mine & set(f)) / len(mine) if mine else None
                # B: the check fails on the known-good reference in at least half of the scenarios where it fails on the
                # uploaded firmware, so no correct firmware passes it. Less than that, the reference passes where the
                # uploaded firmware fails, so the check says something real (a valid finding or a duplicate of a true bug).
                kind = "unknown" if share is None else ("B" if share >= 0.5 else "not B")
                fa_rows.append({"case": c, "correct": not score[c]["truth_bugs"], "assertion": a, "class": kind, "ref_share": share, "ref_fail_scenarios": len(f or []), "title": (reported[i].get("title") or "")[:90], "found_by_search": bool(reported[i].get("found_by_search")), "evidence": (reported[i].get("evidence") or "")[:160]})
        out["fa_rows"] = fa_rows
    return out


API = "http://127.0.0.1:8080"


def main() -> None:
    runs = sys.argv[1:]
    result = {}
    for run in runs:
        rp = RESULTS_DIR / f"{run}_replay.json"
        data = json.loads(rp.read_text()) if rp.is_file() else None
        old = data["reports"] if isinstance(data, dict) and "reports" in data else None
        new = data if isinstance(data, dict) and "reports" not in data else None
        result[run] = summarize(run, new, old)
    print(json.dumps(result, indent=1, default=str))


if __name__ == "__main__":
    main()
