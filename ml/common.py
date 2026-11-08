"""Shared by both trainers: load documents, label chunks, pick a threshold, and save scores."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Callable

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.guard_model import chunks, normalize  # noqa: E402

DATASET = HERE / "dataset"
ARTIFACTS = HERE / "artifacts"
# The target false positive rate. Flagging a real upload sends it to the containment demo, so it is costly.
TARGET_FPR = 0.01
_PIECES = re.compile(r"(?<=[.!?:;])\s+|\n+")


def load(split: str) -> list[dict]:
    return [json.loads(line) for line in (DATASET / f"{split}.jsonl").read_text().splitlines() if line.strip()]


def _squash(text: str) -> str:
    return text.replace("\\", "").replace('"', "")


def labelled_chunks(docs: list[dict]) -> tuple[list[str], list[int], list[str]]:
    """Chunks from benign documents are negatives, chunks holding a payload are positives.

    The rest of an attack document is benign carrier text, already seen as a negative, so it is dropped.
    """
    texts: list[str] = []
    labels: list[int] = []
    groups: list[str] = []
    missed = 0
    for d in docs:
        pieces = chunks(d["firmware"], d["spec"])
        if d["label"] == 0:
            texts.extend(pieces)
            labels.extend([0] * len(pieces))
            groups.extend(["benign"] * len(pieces))
            continue
        # A payload injected into the spec loses its final full stop, so match without it.
        marks = [_squash(p.strip().rstrip(".!?:;")) for p in _PIECES.split(normalize(d["payload"])) if len(p.strip()) >= 4]
        hits = [c for c in pieces if any(m[:120] in _squash(c) for m in marks)]
        if not hits:
            missed += 1
            continue
        texts.extend(hits)
        labels.extend([1] * len(hits))
        groups.extend([d["family"]] * len(hits))
    if missed:
        print(f"  {missed} attack documents had no chunk holding their payload")
    return texts, labels, groups


def threshold_for_fpr(benign_scores: list[float], target: float = TARGET_FPR) -> float:
    """The lowest threshold whose false positive rate on these scores is at most the target."""
    ordered = sorted(benign_scores, reverse=True)
    allowed = int(len(ordered) * target)
    if allowed >= len(ordered):
        return 0.0
    return min(1.0, ordered[allowed] + 1e-9)


def score_documents(docs: list[dict], score_many: Callable[[list[str]], list[float]]) -> list[float]:
    """The score of a document is its worst chunk. Chunks repeat across documents, so score each once."""
    per_doc = [chunks(d["firmware"], d["spec"]) for d in docs]
    unique = sorted({c for pieces in per_doc for c in pieces})
    table = dict(zip(unique, score_many(unique)))
    return [max((table[c] for c in pieces), default=0.0) for pieces in per_doc]


def save_scores(name: str, data: dict) -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / f"{name}.json").write_text(json.dumps(data))


def test_document_ids(test: list[dict]) -> list[dict]:
    return [{"label": d["label"], "family": d["family"], "source": d["source"]} for d in test]
