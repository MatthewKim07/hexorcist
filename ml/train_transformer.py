"""Fine-tune MiniLM on CPU on the same chunks, for comparison with the baseline.

The weights stay in ml/artifacts and are never committed.

Run from ml/, after installing requirements-transformer.txt: .venv/bin/python train_transformer.py
Add --latency-only to re-time the saved model. Do that on an otherwise idle machine.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HOME", str(Path(__file__).parent / ".cache" / "huggingface"))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np  # noqa: E402
import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

from common import ARTIFACTS, labelled_chunks, load, save_scores, score_documents, threshold_for_fpr  # noqa: E402
from app.guard_model import chunks  # noqa: E402

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MAX_LENGTH = 128
EPOCHS = 3
BATCH = 16
LEARNING_RATE = 3e-5
MAX_NEGATIVES_PER_POSITIVE = 2


def directory_mb(path: Path) -> float:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / 1024 / 1024


def scorer(model, tokenizer):
    @torch.inference_mode()
    def score_many(pieces: list[str]) -> list[float]:
        order = sorted(range(len(pieces)), key=lambda i: len(pieces[i]))
        scores = [0.0] * len(pieces)
        for i in range(0, len(order), 64):
            index = order[i : i + 64]
            encoded = tokenizer([pieces[j] for j in index], truncation=True, max_length=MAX_LENGTH, padding=True, return_tensors="pt")
            probs = torch.softmax(model(**encoded).logits, dim=1)[:, 1].tolist()
            for j, p in zip(index, probs):
                scores[j] = p
        return scores

    return score_many


def measure_latency(score_many, test: list[dict]) -> dict:
    """One core, one document at a time, batching only that document's chunks."""
    torch.set_num_threads(1)
    timings = []
    rng = random.Random(3)
    for d in rng.sample(test, 60):
        begin = time.perf_counter()
        score_many(chunks(d["firmware"], d["spec"]))
        timings.append((time.perf_counter() - begin) * 1000)
    firmware = "\n".join(d["firmware"] for d in test if d["firmware"])[: 64 * 1024]
    big_chunks = chunks(firmware, "x " * 2000)
    begin = time.perf_counter()
    score_many(big_chunks)
    worst_ms = (time.perf_counter() - begin) * 1000
    return {"p50": float(np.percentile(timings, 50)), "p95": float(np.percentile(timings, 95)), "largest_upload": worst_ms, "chunks_in_largest": len(big_chunks)}


def latency_only() -> None:
    directory = ARTIFACTS / "minilm"
    tokenizer = AutoTokenizer.from_pretrained(directory)
    model = AutoModelForSequenceClassification.from_pretrained(directory).eval()
    latency = measure_latency(scorer(model, tokenizer), load("test"))
    path = ARTIFACTS / "transformer.json"
    data = json.loads(path.read_text())
    data["latency_ms"] = latency
    path.write_text(json.dumps(data))
    print(latency)


def main() -> None:
    torch.manual_seed(7)
    random.seed(7)
    train, val, test = load("train"), load("val"), load("test")
    texts, labels, _ = labelled_chunks(train)
    positives = [t for t, y in zip(texts, labels) if y == 1]
    negatives = [t for t, y in zip(texts, labels) if y == 0]
    random.shuffle(negatives)
    negatives = negatives[: len(positives) * MAX_NEGATIVES_PER_POSITIVE]
    rows = [(t, 1) for t in positives] + [(t, 0) for t in negatives]
    print(f"training on {len(positives)} positive and {len(negatives)} negative chunks", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
    weights = torch.tensor([1.0, len(negatives) / max(len(positives), 1)])
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)

    start = time.monotonic()
    model.train()
    for epoch in range(EPOCHS):
        random.shuffle(rows)
        total = 0.0
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            encoded = tokenizer([t for t, _ in batch], truncation=True, max_length=MAX_LENGTH, padding=True, return_tensors="pt")
            logits = model(**encoded).logits
            loss = loss_fn(logits, torch.tensor([y for _, y in batch]))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += float(loss)
        print(f"epoch {epoch + 1}: mean loss {total / (len(rows) / BATCH):.4f}, {time.monotonic() - start:.0f} s", flush=True)
    train_seconds = time.monotonic() - start

    model.eval()
    directory = ARTIFACTS / "minilm"
    model.save_pretrained(directory)
    tokenizer.save_pretrained(directory)

    score_many = scorer(model, tokenizer)

    val_scores = score_documents(val, score_many)
    threshold = threshold_for_fpr([s for s, d in zip(val_scores, val) if d["label"] == 0])
    val_recall = float(np.mean([s >= threshold for s, d in zip(val_scores, val) if d["label"] == 1]))
    print(f"threshold {threshold:.4f}, validation recall {val_recall:.3f}", flush=True)
    test_scores = score_documents(test, score_many)

    latency = measure_latency(score_many, test)

    save_scores(
        "transformer",
        {
            "name": "MiniLM-L6 fine-tuned",
            "threshold": threshold,
            "train_seconds": round(train_seconds, 1),
            "val_recall": val_recall,
            "test_scores": test_scores,
            "val_scores": val_scores,
            "latency_ms": latency,
            "size_mb": directory_mb(directory),
        },
    )
    print("saved scores", flush=True)


if __name__ == "__main__":
    if "--latency-only" in sys.argv:
        latency_only()
    else:
        main()
