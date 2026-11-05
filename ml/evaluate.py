"""Compare the regex rules, each model, and regex plus model on the held-out test split.

Run from the repo root: ml/.venv/bin/python ml/evaluate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common import ARTIFACTS, HERE, TARGET_FPR, load
from app.guard import rule_verdict

RESULTS = HERE / "results.json"
NEW_STYLES = {"obfuscated", "disguised", "foreign", "indirect_include", "fake_markup", "patch_exfil", "llm_verdict", "llm_exfiltrate", "llm_takeover", "llm_poison"}


def confusion(preds: list[bool], labels: list[int]) -> dict:
    tp = sum(p and y == 1 for p, y in zip(preds, labels))
    fp = sum(p and y == 0 for p, y in zip(preds, labels))
    fn = sum((not p) and y == 1 for p, y in zip(preds, labels))
    tn = sum((not p) and y == 0 for p, y in zip(preds, labels))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1, "fpr": fp / (fp + tn) if fp + tn else 0.0}


def recall_at_fpr(scores: list[float], labels: list[int], target: float) -> float:
    """Reads the test set's own ROC curve. Descriptive only: no threshold is chosen from this."""
    negatives = sorted((s for s, y in zip(scores, labels) if y == 0), reverse=True)
    cut = negatives[int(len(negatives) * target)] if negatives else 1.0
    positives = [s for s, y in zip(scores, labels) if y == 1]
    return sum(s > cut for s in positives) / len(positives)


def report(name: str, preds: list[bool], test: list[dict], rows: dict) -> None:
    labels = [d["label"] for d in test]
    c = confusion(preds, labels)
    new = [i for i, d in enumerate(test) if d["label"] == 0 or d["family"] in NEW_STYLES]
    held = confusion([preds[i] for i in new], [labels[i] for i in new])
    families: dict[str, list[bool]] = {}
    for p, d in zip(preds, test):
        families.setdefault(d["family"], []).append(p)
    rows[name] = {
        **c,
        "held_out_recall": held["recall"],
        "per_family": {f: sum(v) / len(v) for f, v in sorted(families.items())},
        "family_sizes": {f: len(v) for f, v in sorted(families.items())},
    }
    print(f"{name:<32} P {c['precision']:.3f}  R {c['recall']:.3f}  F1 {c['f1']:.3f}  FPR {c['fpr']:.3f}  new-style recall {held['recall']:.3f}  TP {c['tp']} FP {c['fp']} FN {c['fn']} TN {c['tn']}")


def main() -> None:
    test = load("test")
    labels = [d["label"] for d in test]
    print(f"test: {len(test)} documents, {sum(labels)} attacks, {len(labels) - sum(labels)} benign\n")
    rows: dict = {}
    rules = [not rule_verdict(d["firmware"], d["spec"])["allowed"] for d in test]
    report("Regex rules only", rules, test, rows)
    extra: dict = {}
    for name in ("baseline", "transformer"):
        path = ARTIFACTS / f"{name}.json"
        if not path.exists():
            print(f"{name}: no scores yet")
            continue
        data = json.loads(path.read_text())
        preds = [s >= data["threshold"] for s in data["test_scores"]]
        report(data["name"], preds, test, rows)
        report(f"Regex + {data['name']}", [a or b for a, b in zip(rules, preds)], test, rows)
        for key in (data["name"],):
            extra[key] = {k: data.get(k) for k in ("threshold", "latency_ms", "size_mb", "train_seconds", "val_recall", "best_c")}
            extra[key]["recall_at_1pct_fpr"] = recall_at_fpr(data["test_scores"], labels, TARGET_FPR)
            extra[key]["recall_at_0_1pct_fpr"] = recall_at_fpr(data["test_scores"], labels, 0.001)
        print(f"  {data['name']}: threshold {data['threshold']:.4f}, recall at 1% test FPR {extra[data['name']]['recall_at_1pct_fpr']:.3f}, latency {data['latency_ms']}, size {data['size_mb']:.1f} MB")
    print("\nrecall per family (benign families show the share wrongly flagged)")
    names = list(rows)
    print(f"{'family':<20} {'n':>4} " + " ".join(f"{n[:22]:>22}" for n in names))
    for family, n in rows[names[0]]["family_sizes"].items():
        print(f"{family:<20} {n:>4} " + " ".join(f"{rows[x]['per_family'][family]:>22.2f}" for x in names))
    RESULTS.write_text(json.dumps({"models": rows, "details": extra, "documents": len(test), "attacks": sum(labels)}, indent=1))
    print(f"\nwrote {Path(RESULTS).name}")


if __name__ == "__main__":
    sys.exit(main())
