"""Build bench/adjudication.md and bench/results/summary.md for one benchmark run.

Reads only files in the repo: the two score files, the raw run files, bench/adjudication.json (manual
verdicts with run evidence) and <run>_replay.json (reference replay and partial-run snapshot).
Usage: backend/.venv/bin/python -m bench.summarize RUN_ID
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from bench.case_io import JUDGEMENTS_DIR, RESULTS_DIR, list_case_ids, load_case  # noqa: E402

SYSTEMS = ["baseline_deepseek", "baseline_openai", "hexorcist"]
LABEL = {"baseline_deepseek": "Baseline DeepSeek", "baseline_openai": "Baseline gpt-4o-mini", "hexorcist": "Hexorcist (DeepSeek)"}


def norm(code: str) -> str:
    return re.sub(r"\s+", "", code or "")


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def money(x: float) -> str:
    return f"${x:.3f}"


def load(run: str):
    score_ds = json.loads((RESULTS_DIR / f"{run}_score_deepseek.json").read_text())
    score_oai = json.loads((RESULTS_DIR / f"{run}_score_openai.json").read_text())
    pick = lambda d, name: next(s for s in d["systems"] if s["system"] == name)  # noqa: E731
    scored = {
        "baseline_deepseek": pick(score_ds, "baseline"),
        "baseline_openai": pick(score_oai, "baseline"),
        "hexorcist": pick(score_ds, "hexorcist"),
    }
    raw = {
        "baseline_deepseek": json.loads((RESULTS_DIR / f"{run}_baseline_deepseek.json").read_text()),
        "baseline_openai": json.loads((RESULTS_DIR / f"{run}_baseline_openai.json").read_text()),
        "hexorcist": json.loads((RESULTS_DIR / f"{run}_hexorcist.json").read_text()),
    }
    adj = json.loads((ROOT / "bench/adjudication.json").read_text())
    replay = json.loads((RESULTS_DIR / f"{run}_replay.json").read_text())
    return scored, raw, adj, replay


def removal_by_case(adj: dict) -> dict[str, Counter]:
    """False alarms that adjudication removes (valid findings and duplicates), per system and case."""
    rem: dict[str, Counter] = {s: Counter() for s in SYSTEMS}
    for e in adj["hexorcist"]:
        if e["class"] in ("A", "D"):
            rem["hexorcist"][e["case"]] += 1
    for e in adj["baseline_examined"]:
        if e["verdict"] in ("valid", "duplicate"):
            rem[e["system"]][e["case"]] += 1
    return rem


def metrics(run: str):
    scored, raw, adj, replay = load(run)
    cases = {cid: load_case(cid) for cid in list_case_ids()}
    rem = removal_by_case(adj)
    out: dict[str, dict] = {}
    for s in SYSTEMS:
        rows = scored[s]["rows"]
        rawrows = {r["case_id"]: r for r in raw[s]["cases"]}
        buggy = [r for r in rows if r["truth_bugs"]]
        corr = [r for r in rows if not r["truth_bugs"]]
        patched = {r["case_id"]: bool((rawrows[r["case_id"]].get("patched_sketch") or "").strip()) for r in rows}
        changed = {
            r["case_id"]: patched[r["case_id"]] and norm(rawrows[r["case_id"]]["patched_sketch"]) != norm(cases[r["case_id"]].sketch)
            for r in rows
        }
        fa = lambda rs: sum(r["false_alarms"] for r in rs)  # noqa: E731
        fa_adj = lambda rs: sum(r["false_alarms"] - rem[s][r["case_id"]] for r in rs)  # noqa: E731
        n_patched = sum(patched.values())
        broke = [r["case_id"] for r in corr if patched[r["case_id"]] and (not r["compiles"] or not r["fixed"])]
        m = {
            "cases": len(rows), "buggy": len(buggy), "correct": len(corr),
            "bugs": sum(r["truth_bugs"] for r in rows), "detected": sum(r["detected"] for r in rows),
            "fa_buggy": fa(buggy), "fa_correct": fa(corr), "fa_buggy_adj": fa_adj(buggy), "fa_correct_adj": fa_adj(corr),
            "patched": n_patched, "compiled": sum(1 for r in rows if patched[r["case_id"]] and r["compiles"]),
            "fixed_buggy": sum(1 for r in buggy if r["fixed"]), "broke": broke, "n_broke": len(broke),
            "patched_correct": sum(1 for r in corr if patched[r["case_id"]]),
            "changed_correct": sum(1 for r in corr if changed[r["case_id"]]),
            "median_s": statistics.median(r["wall_s"] for r in rows),
            "cost": sum(float(r.get("cost_usd") or 0) for r in rows),
            "rows": rows,
        }
        if s == "hexorcist":
            m["self_fixed_buggy"] = sum(1 for r in buggy if rawrows[r["case_id"]]["status"] == "fixed")
            m["statuses"] = Counter(r["status"] for r in raw[s]["cases"])
        out[s] = m
    return scored, raw, adj, replay, cases, rem, out


def category_table(scored, cases, rem):
    cats = sorted({b["category"] for c in cases.values() for b in c.truth})
    rows = []
    for cat in cats + ["correct"]:
        ids = [cid for cid, c in cases.items() if (cat in c.categories)]
        entry = {"cat": cat, "cases": len(ids), "bugs": sum(1 for cid in ids for b in cases[cid].truth if b["category"] == cat)}
        for s in SYSTEMS:
            byc = {r["case_id"]: r for r in scored[s]["rows"]}
            det = sum(1 for cid in ids for b in cases[cid].truth if b["category"] == cat and byc[cid]["detection"].get(b["id"]))
            entry[s] = {
                "det": det,
                "fixed": sum(1 for cid in ids if byc[cid]["fixed"]) if cat != "correct" else None,
                "fa": sum(byc[cid]["false_alarms"] for cid in ids),
                "fa_adj": sum(byc[cid]["false_alarms"] - rem[s][cid] for cid in ids),
            }
        rows.append(entry)
    return rows


def evidence_check(scored, replay):
    """For each detected truth bug, does any credited report fail on a scenario where the reference passes?"""
    rep = {(r["case"], r["index"]): r for r in replay["reports"]}
    run = replay["run_id"]
    weak = []
    detected_total = 0
    for row in scored["hexorcist"]["rows"]:
        if not row["detected"]:
            continue
        j = json.loads((JUDGEMENTS_DIR / f"{run}_score_deepseek_hexorcist_{row['case_id']}.json").read_text())["judgement"]
        by_truth: dict[str, set[int]] = defaultdict(set)
        for m in j.get("matches") or []:
            if m.get("matched"):
                by_truth[m["truth_id"]].add(m["reported_index"])
        for d in j.get("duplicate_of_truth") or []:
            by_truth[d["truth_id"]].add(d["reported_index"])
        for tid, idxs in by_truth.items():
            detected_total += 1
            ok = any(rep[(row["case_id"], i)]["failing_scenarios"] - rep[(row["case_id"], i)]["reference_also_fails"] > 0 for i in idxs if (row["case_id"], i) in rep)
            if not ok:
                weak.append((row["case_id"], tid))
    return detected_total, weak


# ---------------------------------------------------------------------------------------------------
def adjudication_md(run: str, adj: dict, replay: dict, out: dict) -> str:
    H = adj["hexorcist"]
    cnt = Counter((e["class"], e["case"].endswith("_ok")) for e in H)
    cls = lambda c, ok=None: sum(v for (k, o), v in cnt.items() if k == c and (ok is None or o == ok))  # noqa: E731
    L = [f"# Adjudication of false alarms, run {run}", ""]
    L += [
        "Strict scoring counts every report that the judge did not match to a frozen true bug as a false alarm. "
        "This document checks those reports against the specs. `bench/cases/` and the frozen ground truth are unchanged.",
        "",
        "## Method",
        "",
        "**Hexorcist.** All 27 strict false alarms were checked, plus every report on a correct case. "
        "Each report's own assertion and scenarios were replayed against the case's `reference.ino` (the known-good firmware; "
        "it is identical to `sketch.ino` on all 11 correct cases). If the known-good firmware fails the same check, "
        "the check or the evaluator is wrong, not the firmware. Each entry states how many "
        "of the report's failing scenarios also fail on the reference. Data: `bench/results/" + run + "_replay.json`.",
        "",
        "Every cause is exactly one of:",
        "",
        "- **A**: the sketch really violates a spec bullet that the frozen checks do not test. A valid finding.",
        "- **B**: Hexorcist wrote an assertion that misreads the spec.",
        "- **C**: Hexorcist's evaluator or harness judged wrongly.",
        "- **D**: not a false alarm. The scorer's judge failed to mark a duplicate of a true bug. Outside A/B/C, listed so the counts add up.",
        "",
        "**Baselines.** Baseline claims carry no measured evidence. Each of the 81 and 53 strict false alarms was read against the spec and the "
        "sketch. Only claims that were plausible violations or duplicates of a true bug are listed below, with a verdict. "
        "Every other claim contradicted the spec or the code, or named only a risk with no violated bullet. "
        "These verdicts come from reading and from measurements Hexorcist made on the same sketches, not from a run per claim, so the "
        "'valid' counts are a lower bound.",
        "",
        "**Scorer fix.** The judge sometimes returned a false-alarm index equal to the number of reports. `bench/score.py` now drops "
        "indices that name no report. Effect on strict counts: Hexorcist 31 to 27, DeepSeek baseline 83 to 81, gpt-4o-mini baseline unchanged (53). "
        "The as-scored files are in `bench/results/asscored/`.",
        "",
        "## Counts for Hexorcist",
        "",
        "| Cause | Reports on correct cases | False alarms on buggy cases | Total |",
        "| --- | ---: | ---: | ---: |",
    ]
    for c, name in (("A", "A sketch violates untested bullet"), ("B", "B assertion misreads spec"), ("C", "C evaluator or harness wrong"), ("D", "D duplicate of a true bug (not a false alarm)")):
        L.append(f"| {name} | {cls(c, True)} | {cls(c, False)} | {cls(c)} |")
    L.append(f"| **Total** | {len(H) and sum(1 for e in H if e['case'].endswith('_ok'))} | {sum(1 for e in H if not e['case'].endswith('_ok'))} | {len(H)} |")
    L += ["", "Three correct cases (greenhouse_ok, lobby_lamp_ok, studio_siren_ok) produced no reports and no patch.", ""]

    L += ["## Class C: bugs in Hexorcist's evaluator (most important)", ""]
    c_main = [e for e in H if e["class"] == "C"] + adj["hexorcist_extra_c"]
    L += [
        "**C1. An output pin used as a condition is read as constant 0.** `digital_input_levels()` in `backend/app/assertions.py` reads only pin "
        "events with `dir == 'in'`. When a model-written `output_follows` check uses an output pin as its condition (here LED D11 follows solenoid D8), "
        "the condition never changes, and the check demands the wrong level for the whole pulse. The firmware is correct in every case. "
        "It produced one false alarm and two reports that the scorer credited as duplicates of the true bug. All three kept their runs at `partial`.",
        "",
    ]
    for e in c_main:
        L.append(f"- `{e['case']}` {e['assertion_id']} ({'false alarm' if e['counted_as_false_alarm'] else 'credited as duplicate, not counted'}): "
                 f"{e['reasoning']} Run `{e['run_id']}`; evidence: \"{e['evidence']}\" Reference also fails {e['reference_also_fails']} of {e['failing_scenarios']}.")
    L += [
        "",
        "**C2. Input noise exceeds the ADC margin at threshold hovers (minor, cause inferred).** The evaluator takes the input once per 10 ms and allows a 10 mV "
        "ADC margin, but the built-in hover scenario adds 12 mV of noise. The likely cause is that a correct firmware reading a noisy sample inside the 10 ms window "
        "differs from the evaluator's view for 1 to 3 ms at the end of a required interval. Example: `lab_ph_ok` a4, builtin-hover-a1, "
        "'D10 was not HIGH for 1 ms' at 794 ms (input 3236 mV last sample, threshold 3250 mV, D10 flips at 791 to 797 ms). The same 1 to 3 ms spans appear in "
        "`weather_ok` a5 and `weather_line_prefix` a5. Each of those reports is class B overall, because its other scenarios fail for larger reasons, "
        "so C2 adds no report to the C count.",
        "",
        "## All Hexorcist false alarms and reports on correct cases",
        "",
    ]

    def block(title: str, entries: list[dict]) -> None:
        L.append(f"### {title}")
        L.append("")
        for e in entries:
            L.append(f"**{e['case']} {e['assertion_id']}, class {e['class']}.** Claim: \"{e['claim']}\" ({e['assertion_type']}, run `{e['run_id']}`)")
            L.append(f"- Spec bullet: {e['spec_bullet']}")
            L.append(f"- Evidence: scenario \"{e['scenario']}\": {e['evidence']} Reference also fails {e['reference_also_fails']} of {e['failing_scenarios']} failing scenarios.")
            L.append(f"- Why {e['class']}: {e['reasoning']}")
            L.append("")

    block("Reports on correct cases (13)", [e for e in H if e["case"].endswith("_ok")])
    block("False alarms on buggy cases (14)", [e for e in H if not e["case"].endswith("_ok")])

    L += ["## Baseline false alarms examined", "",
          "| System | Case | Claim | Spec bullet | Verdict | Reasoning |", "| --- | --- | --- | --- | --- | --- |"]
    for e in adj["baseline_examined"]:
        v = {"valid": "**valid finding**", "duplicate": "duplicate of true bug", "genuine": "genuine false alarm"}[e["verdict"]]
        L.append(f"| {LABEL[e['system']]} | {e['case']} | {e['claim']} | {e['spec_bullet']} | {v} | {e['reasoning']} |")
    L += ["", "| System | Strict false alarms | Valid findings | Duplicates of true bugs | Adjudicated false alarms |", "| --- | ---: | ---: | ---: | ---: |"]
    for s in SYSTEMS:
        ex = adj["baseline_examined"]
        valid = sum(1 for e in ex if e["system"] == s and e["verdict"] == "valid")
        dup = sum(1 for e in ex if e["system"] == s and e["verdict"] == "duplicate")
        if s == "hexorcist":
            valid, dup = cls("A"), cls("D")
        strict = out[s]["fa_buggy"] + out[s]["fa_correct"]
        L.append(f"| {LABEL[s]} | {strict} | {valid} | {dup} | {strict - valid - dup} |")
    L.append("")
    return "\n".join(L)


def summary_md(run: str, out: dict, adj: dict, replay: dict, scored, raw, cat_rows, weak, detected_total) -> str:
    H = adj["hexorcist"]
    hx, d4, o4 = out["hexorcist"], out["baseline_deepseek"], out["baseline_openai"]
    cnt = lambda c, ok=None: sum(1 for e in H if e["class"] == c and (ok is None or e["case"].endswith("_ok") == ok))  # noqa: E731
    parts = replay["partial_runs"]
    pb = [p for p in parts if p["buggy"]]
    pc = [p for p in parts if not p["buggy"]]
    all_on_ref = [p for p in parts if p["still_failing"] and p["still_failing"] == p["still_failing_also_on_reference"]]
    some_not_ref = [p for p in parts if p["still_failing"] != p["still_failing_also_on_reference"]]
    nocomp = [p for p in parts if p["non_compiling_attempts"]]
    hb = {p["case"]: p for p in parts}
    judge_cost = 0.0162 + 0.0070

    def row(label: str, f) -> str:
        return f"| {label} | " + " | ".join(f(out[s]) for s in SYSTEMS) + " |"

    L = [f"# Benchmark v2 results, run {run}", ""]
    L += [
        "40 frozen cases (29 with planted bugs holding 32 bugs, 11 correct), one run per case, serial. "
        "Baselines: one plain-LLM review per case (DeepSeek `deepseek-chat`, OpenAI `gpt-4o-mini`). Hexorcist: Find-bugs mode over the live API with `deepseek-chat`. "
        "Every patch is checked against the frozen checks. Match judge: `gpt-4o-mini`, current rubric (symptom match, duplicates merged). "
        "The case files were unchanged from freeze commit `6a92c57` (verified with `git diff` and `git status`). All runs finished with no errors and no budget stop.",
        "",
        "Strict scoring counts every unmatched report as a false alarm. Adjudicated scoring removes reports that adjudication showed to be valid findings or duplicates of a true bug "
        "(see `bench/adjudication.md`). Adjudicated recall equals strict recall.",
        "",
        "## Overall",
        "",
        "| Metric | " + " | ".join(LABEL[s] for s in SYSTEMS) + " |",
        "| --- | ---: | ---: | ---: |",
        row("Detection recall (32 bugs)", lambda m: pct(m["detected"], m["bugs"])),
        row("False alarms per buggy case, strict", lambda m: f"{m['fa_buggy'] / m['buggy']:.2f} ({m['fa_buggy']})"),
        row("False alarms per buggy case, adjudicated", lambda m: f"{m['fa_buggy_adj'] / m['buggy']:.2f} ({m['fa_buggy_adj']})"),
        row("False alarms per correct case, strict", lambda m: f"{m['fa_correct'] / m['correct']:.2f} ({m['fa_correct']})"),
        row("False alarms per correct case, adjudicated", lambda m: f"{m['fa_correct_adj'] / m['correct']:.2f} ({m['fa_correct_adj']})"),
        row("Patch compiles (cases with a patch)", lambda m: pct(m["compiled"], m["patched"])),
        row("Verified fix on buggy cases (frozen checks)", lambda m: pct(m["fixed_buggy"], m["buggy"])),
        row("Correct sketches given a patch", lambda m: f"{m['patched_correct']}/{m['correct']}"),
        row("Correct sketches whose patch differs from the original", lambda m: f"{m['changed_correct']}/{m['correct']}"),
        row("Broke a correct sketch (patch does not compile or fails frozen checks)", lambda m: f"{m['n_broke']}/{m['correct']}"),
        row("Median time per case", lambda m: f"{m['median_s']:.0f} s"),
        row("Cost of the run", lambda m: money(m["cost"])),
        "",
        f"Judge cost: about {money(judge_cost)} (gpt-4o-mini, first scoring; re-scores used the cache). Total spend for the run: {money(d4['cost'] + o4['cost'] + hx['cost'] + judge_cost)}. "
        "Baselines give no verified-fix claim of their own, so their 'verified fix' is the frozen-check result of the patch they wrote. "
        f"Hexorcist's own verdict was `fixed` on {hx['self_fixed_buggy']} of 29 buggy cases; the frozen checks passed on {hx['fixed_buggy']} of 29 (statuses: "
        + ", ".join(f"{k} {v}" for k, v in sorted(hx["statuses"].items())) + ").",
        "",
        "## Hexorcist false alarms by cause",
        "",
        "| Cause | Correct cases | Buggy cases | Total |",
        "| --- | ---: | ---: | ---: |",
        f"| A. Sketch violates a bullet the frozen checks do not test (valid finding) | {cnt('A', True)} | {cnt('A', False)} | {cnt('A')} |",
        f"| B. Hexorcist's assertion misreads the spec | {cnt('B', True)} | {cnt('B', False)} | {cnt('B')} |",
        f"| C. Hexorcist's evaluator or harness is wrong | {cnt('C', True)} | {cnt('C', False)} | {cnt('C')} |",
        f"| D. Not a false alarm (duplicate of a true bug the judge missed) | {cnt('D', True)} | {cnt('D', False)} | {cnt('D')} |",
        f"| **Strict false alarms** | **{hx['fa_correct']}** | **{hx['fa_buggy']}** | **{hx['fa_correct'] + hx['fa_buggy']}** |",
        "",
        "Class C is a bug in the judge: an output pin used as a condition is read as constant 0, so `output_follows` demands the wrong level "
        "(`solenoid_ok` a2). Two more reports with the same cause (`glue_solenoid_short` a2, `mist_injector_long` a2) were credited as duplicates of the "
        "true bug, so they are not false alarms, but they kept those runs from finishing as `fixed`. A smaller evaluator weakness gives 1 to 3 ms "
        "violations at noisy threshold hovers (see adjudication). Every report on the 8 correct cases that produced one fails the same way on the known-good reference.",
        "",
        "## Partial Hexorcist runs",
        "",
        f"{len(parts)} runs ended `partial`: {len(pb)} on buggy cases and {len(pc)} on correct cases.",
        "",
        f"- Buggy cases ({len(pb)}): all {sum(1 for p in pb if p['true_bug_found'])} found the true bug (matched by the judge), and none missed it. "
        f"{sum(1 for p in pb if p['true_bug_found'])} found it but did not verify a fix, with the caveat that the patch passed the frozen checks in {sum(1 for p in pb if p['frozen_patch_fixed'])} of {len(pb)}.",
        f"- Why verification failed: in {len(all_on_ref)} of {len(parts)} partial runs every check still failing at the best patch also fails on the known-good reference, "
        "so no correct firmware could pass them. The failing checks are model-written assertions that misread the spec (class B) or hit the evaluator bug (class C).",
        f"- The other {len(some_not_ref)}: " + "; ".join(
            f"`{p['case']}` ({p['still_failing'] - p['still_failing_also_on_reference']} of {p['still_failing']} failures not on the reference, frozen checks {'pass' if p['frozen_patch_fixed'] else 'FAIL ' + ', '.join(p['frozen_failing'])})" for p in some_not_ref) + ".",
        f"- {len(nocomp)} of {len(parts)} partial runs had at least one patch attempt that did not compile ({', '.join(p['case'] for p in nocomp)}).",
        f"- The one bug Hexorcist missed was the second bug of `panel_dual_debounce_edge` (inverted_pullup); that run finished `fixed`. It was not a partial run.",
        "",
        "## By bug category",
        "",
        "Dual-bug cases count in both of their categories. `FA` is strict false alarms per case with the adjudicated figure in brackets. "
        "Systems in order: Baseline DeepSeek / Baseline gpt-4o-mini / Hexorcist.",
        "",
        "| Category | Cases | Bugs | Recall | Verified fix (cases) | FA per case, strict (adjudicated) |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for r in cat_rows:
        rec = " / ".join(f"{r[s]['det']}/{r['bugs']}" for s in SYSTEMS) if r["cat"] != "correct" else "n/a"
        fix = " / ".join(f"{r[s]['fixed']}/{r['cases']}" for s in SYSTEMS) if r["cat"] != "correct" else "n/a"
        fa = " / ".join(f"{r[s]['fa'] / r['cases']:.1f} ({r[s]['fa_adj'] / r['cases']:.1f})" for s in SYSTEMS)
        L.append(f"| {r['cat'].replace('_', ' ')} | {r['cases']} | {r['bugs'] or '-'} | {rec} | {fix} | {fa} |")
    L += ["", "## Findings", ""]
    ev = f"{detected_total - len(weak)} of {detected_total}"
    cat = {r["cat"]: r for r in cat_rows}
    weak_txt = ", ".join(f"`{c}`" for c, _ in weak)
    L += [
        f"- **Recall.** DeepSeek baseline found {d4['detected']} of 32 bugs, Hexorcist {hx['detected']}, gpt-4o-mini {o4['detected']}. "
        "The planted bugs are mostly visible in the code, so a plain review does well here. Hexorcist's one miss was the second bug of a dual-bug case "
        "(`panel_dual_debounce_edge`, inverted pull-up). gpt-4o-mini missed 4, including the integer overflow in `blend_tank_sum_ovf`.",
        f"- **Reports per case.** Strict false alarms per correct case: {d4['fa_correct'] / 11:.1f} (DeepSeek), {o4['fa_correct'] / 11:.1f} (gpt-4o-mini), "
        f"{hx['fa_correct'] / 11:.1f} (Hexorcist); per buggy case {d4['fa_buggy'] / 29:.1f}, {o4['fa_buggy'] / 29:.1f}, {hx['fa_buggy'] / 29:.1f}. "
        "Baseline claims on correct sketches are mostly speculation (\"minor\", \"fragile\") or contradict the spec. "
        "Hexorcist's reports on correct sketches come with measured numbers, but each one fails the same way on the known-good firmware, so the numbers are accurate and the check is wrong.",
        f"- **Fixes.** Patches passed the frozen checks on {hx['fixed_buggy']} of 29 buggy cases for Hexorcist, {d4['fixed_buggy']} for the DeepSeek baseline and {o4['fixed_buggy']} for gpt-4o-mini. "
        f"Hexorcist did best on inverted pull-up ({cat['inverted_pullup']['hexorcist']['fixed']}/3, against {cat['inverted_pullup']['baseline_deepseek']['fixed']}/3 for DeepSeek) "
        f"and lost on integer overflow ({cat['integer_overflow']['hexorcist']['fixed']}/2; the `cabin_heater_mul_ovf` patch fails `a_follow`) and millis rollover "
        f"({cat['millis_rollover']['hexorcist']['fixed']}/2; the `nav_beacon_byte_timer` patch fails `a_max` and `a_period`).",
        f"- **Correct sketches.** Hexorcist left {11 - hx['patched_correct']} of 11 alone (no report, no patch) and rewrote {hx['changed_correct']}; none of its patches failed the frozen checks. "
        f"The baselines are asked for a patched sketch every time and rewrote {d4['changed_correct']}/11 (DeepSeek) and {o4['changed_correct']}/11 (gpt-4o-mini); one gpt-4o-mini rewrite (`loft_fan_ok`) failed the frozen checks.",
        f"- **Behaviours the frozen checks miss.** Four defects, confirmed by measurement (pct period, toggle limit, porch restart) or by reading the code in both sketch and reference (freeze): the pct stream stretching to 1246 ms while the force button is held "
        "(`blend_tank_sum_ovf`, found by Hexorcist and by gpt-4o-mini), and fan toggling past 2 per 5 s under boost presses (`loft_fan_ok`, found by Hexorcist and the DeepSeek baseline). "
        "The DeepSeek baseline also found that the freeze in `weather_ok` and `weather_line_prefix` never freezes (the sketch re-latches the value on every loop; Hexorcist wrote no freeze assertion in either run), "
        "and that `porch_gate_block` restarts the chime for a press that began while it was sounding (3600 ms pulse; the reference ignores the press).",
        f"- **Where Hexorcist loses.** After adjudication, {cnt('B')} of its {hx['fa_correct_adj'] + hx['fa_buggy_adj']} remaining false alarms are assertions that misread the spec and {cnt('C')} is an evaluator bug. "
        "A run ends `partial` when such a check cannot be satisfied, and the loop keeps patching to meet it: "
        f"{hx['self_fixed_buggy']} of 29 buggy cases reached Hexorcist's own `fixed` status while {hx['fixed_buggy']} passed the frozen checks. "
        f"It is slower (median {hx['median_s']:.0f} s against {d4['median_s']:.0f} s for the DeepSeek baseline) and costs {money(hx['cost'])} per 40 cases against {money(d4['cost'])}.",
        f"- **Evidence strength.** For {ev} detected bugs, at least one matched report failed on a scenario where the known-good firmware passes. "
        f"For {weak_txt} the judge matched a report to the true bug, but the check that report cites fails the same way on the reference, so its measured evidence does not separate the buggy sketch from the correct one (for `drip_scheduler_u8` the numbers differ in size but not in outcome).",
        "- **Gaps in the frozen set.** The reference firmware itself violates a spec bullet in 5 cases: the freeze (`weather_ok`, `weather_line_prefix`), the toggle limit under button presses "
        "(`loft_fan_ok`, `attic_vent_hyst`) and the pct period with the button held (`blend_tank_sum_ovf`). Of the 34 cases with a digital input, 17 have no frozen scenario that drives any digital input, "
        "and 4 more leave one input undriven. These are recorded here and the cases are unchanged.",
        "",
        "## Limitations",
        "",
        "- 40 cases and one Hexorcist run per case. The app is not deterministic, so differences of a few bugs or false alarms are within run-to-run noise.",
        "- The cases were written for this benchmark, by the project author, with planted bugs from a fixed list of 13 categories. Results may not transfer to real firmware.",
        "- Hexorcist's prompts were tuned on DeepSeek and on the four buggy preset firmwares, not on these cases. The baseline prompt was not tuned.",
        "- The baseline is one plain-LLM review per case. A stronger prompt, tool use or a larger model could do better.",
        "- Matching and false-alarm counting use an LLM judge (gpt-4o-mini). It returned 6 false-alarm indices that name no report (dropped in the scorer) and missed some duplicates. "
        "Baseline claims were adjudicated by reading, not by running each claim, so the baseline 'valid' counts are a lower bound.",
        "- Verified fix means passing the frozen checks. They are hand-written and have the gaps above, so a patch can pass and still break an untested bullet.",
        "- The frozen checks are scored with the same `evaluate_all` code that Hexorcist uses as its judge. An evaluator weakness can therefore hide in the ground truth too: the `porch_gate_block` restart above passes the frozen `a_pulse` check because the evaluator lets a held trigger fire again.",
        "- Adjudication was done once, by the agent that ran the benchmark, after seeing the results.",
        "",
        "Files: `bench/adjudication.md`, `bench/adjudication.json`, `bench/results/" + run + "_*.json`, `bench/results/" + run + "_replay.json`, `bench/results/asscored/`, `bench/results/run.log`.",
        "",
    ]
    return "\n".join(L)


def main() -> None:
    run = sys.argv[1]
    scored, raw, adj, replay, cases, rem, out = metrics(run)
    cat_rows = category_table(scored, cases, rem)
    detected_total, weak = evidence_check(scored, replay)
    (ROOT / "bench/adjudication.md").write_text(adjudication_md(run, adj, replay, out))
    (RESULTS_DIR / "summary.md").write_text(summary_md(run, out, adj, replay, scored, raw, cat_rows, weak, detected_total))
    print("wrote bench/adjudication.md and bench/results/summary.md")
    for s in SYSTEMS:
        m = out[s]
        print(s, {k: v for k, v in m.items() if k not in ("rows", "statuses")})
    print("weak evidence:", weak, "of", detected_total)


if __name__ == "__main__":
    main()
