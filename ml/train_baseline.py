"""Train TF-IDF plus logistic regression and export it as plain JSON for the backend.

C is chosen by leave-one-family-out on the training split, which rewards generalising to attack styles
the model has not seen. The threshold comes from the validation split. Test is only scored at the end.

Run from ml/: .venv/bin/python train_baseline.py
Add --latency-only to re-time the exported model. Do that on an otherwise idle machine.
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from common import ARTIFACTS, TARGET_FPR, load, labelled_chunks, save_scores, score_documents, threshold_for_fpr
from app.guard_model import MODEL_PATH, GuardModel, chunks, features

GRID_C = [1.0, 3.0, 10.0, 30.0, 100.0]
VOCABULARY_SIZE = 15000


def vectorizer(vocabulary=None) -> TfidfVectorizer:
    return TfidfVectorizer(analyzer=features, sublinear_tf=True, min_df=1 if vocabulary else 2, vocabulary=vocabulary)


def classifier(c: float) -> LogisticRegression:
    return LogisticRegression(C=c, class_weight="balanced", max_iter=2000, solver="liblinear")


def leave_one_family_out(texts: list[str], labels: np.ndarray, groups: np.ndarray) -> float:
    """Pick C by recall on each attack family left out of training, at about 1% chunk false positives."""
    families = sorted(set(groups) - {"benign"})
    rng = np.random.default_rng(1)
    benign = np.flatnonzero(groups == "benign")
    held_benign = rng.choice(benign, size=len(benign) // 5, replace=False)
    results: dict[float, float] = {}
    for c in GRID_C:
        recalls = []
        for family in families:
            hold = groups == family
            train_mask = ~hold
            train_mask[held_benign] = False
            vec = vectorizer()
            x = vec.fit_transform([t for t, m in zip(texts, train_mask) if m])
            model = classifier(c).fit(x, labels[train_mask])
            eval_x = vec.transform([texts[i] for i in np.flatnonzero(hold)])
            neg_x = vec.transform([texts[i] for i in held_benign])
            cut = threshold_for_fpr(list(model.predict_proba(neg_x)[:, 1]))
            recalls.append(float((model.predict_proba(eval_x)[:, 1] >= cut).mean()))
        results[c] = float(np.mean(recalls))
        print(f"  C={c}: mean recall on a left-out family {results[c]:.3f}", flush=True)
    return max(results, key=lambda c: results[c])


def measure_latency(guard: GuardModel, test: list[dict]) -> dict:
    """One document at a time on one core, as the backend runs it."""
    timings = []
    for d in test:
        begin = time.perf_counter()
        guard.score(d["firmware"], d["spec"])
        timings.append((time.perf_counter() - begin) * 1000)
    firmware = "\n".join(d["firmware"] for d in test if d["firmware"])[: 64 * 1024]
    spec = "x " * 2000
    begin = time.perf_counter()
    guard.score(firmware, spec)
    worst_ms = (time.perf_counter() - begin) * 1000
    return {"p50": float(np.percentile(timings, 50)), "p95": float(np.percentile(timings, 95)), "largest_upload": worst_ms, "chunks_in_largest": len(chunks(firmware, spec))}


def latency_only() -> None:
    path = ARTIFACTS / "baseline.json"
    data = json.loads(path.read_text())
    data["latency_ms"] = measure_latency(GuardModel(json.loads(MODEL_PATH.read_text())), load("test"))
    path.write_text(json.dumps(data))
    print(data["latency_ms"])


def main() -> None:
    train, val, test = load("train"), load("val"), load("test")
    texts, labels_list, groups_list = labelled_chunks(train)
    labels = np.array(labels_list)
    groups = np.array(groups_list)
    print(f"train chunks: {len(texts)}, {int(labels.sum())} positive")

    start = time.monotonic()
    best_c = leave_one_family_out(texts, labels, groups)
    print(f"chose C={best_c}")

    # Keep the most useful features, then refit on only those, so that exported inference is exact.
    vec = vectorizer()
    x = vec.fit_transform(texts)
    model = classifier(best_c).fit(x, labels)
    order = np.argsort(-np.abs(model.coef_[0]))[:VOCABULARY_SIZE]
    names = vec.get_feature_names_out()
    vec = vectorizer(vocabulary=sorted(names[i] for i in order))
    x = vec.fit_transform(texts)
    model = classifier(best_c).fit(x, labels)
    train_seconds = time.monotonic() - start

    exported = {
        "version": "tfidf-logreg-1",
        "intercept": round(float(model.intercept_[0]), 5),
        "threshold": 0.5,
        "vocab": {name: [round(float(idf), 4), round(float(coef), 5)] for name, idf, coef in zip(vec.get_feature_names_out(), vec.idf_, model.coef_[0]) if abs(coef) > 1e-6},
    }
    guard = GuardModel(exported)

    # Exported pure-Python inference must agree with scikit-learn.
    sample = texts[:: max(1, len(texts) // 500)]
    sklearn_scores = model.predict_proba(vec.transform(sample))[:, 1]
    python_scores = np.array([guard.score_chunk(t) for t in sample])
    disagreement = float(np.abs(sklearn_scores - python_scores).max())
    print(f"worst disagreement between scikit-learn and exported inference: {disagreement:.6f}")
    if disagreement > 1e-2:
        raise SystemExit("exported inference does not match scikit-learn")

    def score_many(pieces: list[str]) -> list[float]:
        return [guard.score_chunk(p) for p in pieces]

    val_scores = score_documents(val, score_many)
    threshold = threshold_for_fpr([s for s, d in zip(val_scores, val) if d["label"] == 0])
    exported["threshold"] = round(threshold, 5)
    guard.threshold = exported["threshold"]
    val_recall = float(np.mean([s >= threshold for s, d in zip(val_scores, val) if d["label"] == 1]))
    print(f"threshold {threshold:.4f} for {TARGET_FPR:.0%} FPR on validation, validation recall {val_recall:.3f}")

    MODEL_PATH.write_text(json.dumps(exported, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {MODEL_PATH} with {len(exported['vocab'])} features, {MODEL_PATH.stat().st_size / 1024:.0f} KiB")

    latency = measure_latency(guard, test)

    save_scores(
        "baseline",
        {
            "name": "TF-IDF + logistic regression",
            "threshold": threshold,
            "best_c": best_c,
            "train_seconds": round(train_seconds, 1),
            "val_recall": val_recall,
            "test_scores": score_documents(test, score_many),
            "val_scores": val_scores,
            "latency_ms": latency,
            "size_mb": MODEL_PATH.stat().st_size / 1024 / 1024,
            "extra_runtime_mb": 0,
        },
    )
    print(f"saved scores to {ARTIFACTS}")


if __name__ == "__main__":
    if "--latency-only" in sys.argv:
        latency_only()
    else:
        main()
