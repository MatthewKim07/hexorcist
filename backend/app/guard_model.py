"""Inference for the trained guard classifier. Standard library only.

The control layer holds the LLM key and the Docker socket, so it loads a plain JSON file of weights,
not a pickle, and takes on no ML dependencies. ml/train_baseline.py trains with these same functions.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Optional

MODEL_PATH = Path(__file__).with_name("guard_model.json")

# A chunk is short so that one injected line cannot be diluted by a long sketch.
CHUNK_CHARS = 400
CHUNK_OVERLAP = 80
WINDOW_LINES = 3
WINDOW_STRIDE = 2
MAX_CHUNKS = 2000

_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­᠎"), None)
# Letters that look Latin. Fold only these, so real Cyrillic or Greek text stays distinguishable.
_CONFUSABLES = str.maketrans(
    "аеорсухіјѕԁԍԛԝАВЕКМНОРСТХІЈЅοαιυκνΑΒΕΗΙΚΜΝΟΡΤΥΧ",
    "aeopcyxijsdgqwABEKMHOPCTXIJSoaiuknABEHIKMNOPTYX",
)
_WORD = re.compile(r"\w\w+")
_SENTENCE = re.compile(r"(?<=[.!?:;])\s+|\n+")


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_INVISIBLE).translate(_CONFUSABLES)


def _split_long(text: str) -> list[str]:
    if len(text) <= CHUNK_CHARS:
        return [text]
    step = CHUNK_CHARS - CHUNK_OVERLAP
    return [text[i : i + CHUNK_CHARS] for i in range(0, len(text) - CHUNK_OVERLAP, step)]


def chunks(firmware: str, spec: str) -> list[str]:
    """Overlapping windows of code lines and of spec sentences, without duplicates."""
    found: dict[str, None] = {}
    lines = [line.strip() for line in normalize(firmware).splitlines() if line.strip()]
    for i in range(0, max(len(lines), 1), WINDOW_STRIDE):
        window = "\n".join(lines[i : i + WINDOW_LINES])
        for piece in _split_long(window):
            if piece:
                found[piece] = None
        if i + WINDOW_LINES >= len(lines):
            break
    sentences = [s.strip() for s in _SENTENCE.split(normalize(spec)) if s.strip()]
    for i in range(len(sentences)):
        for piece in _split_long(" ".join(sentences[i : i + 2])):
            found[piece] = None
    return list(found)[:MAX_CHUNKS]


def features(text: str) -> list[str]:
    """Words, word pairs and 3 to 5 character n-grams. Must stay in step with the saved vocabulary."""
    low = text.lower()
    words = _WORD.findall(low)
    out = [f"w:{w}" for w in words]
    out.extend(f"b:{a} {b}" for a, b in zip(words, words[1:]))
    squeezed = " ".join(low.split())
    for n in (3, 4, 5):
        out.extend(f"c:{squeezed[i : i + n]}" for i in range(len(squeezed) - n + 1))
    return out


class GuardModel:
    def __init__(self, data: dict) -> None:
        self.vocab: dict[str, tuple[float, float]] = {k: (v[0], v[1]) for k, v in data["vocab"].items()}
        self.intercept: float = data["intercept"]
        self.threshold: float = data["threshold"]
        self.version: str = data.get("version", "unknown")

    def score_chunk(self, text: str) -> float:
        norm = 0.0
        dot = 0.0
        for feature, count in Counter(features(text)).items():
            entry = self.vocab.get(feature)
            if entry is None:
                continue
            value = (1.0 + math.log(count)) * entry[0]
            norm += value * value
            dot += value * entry[1]
        z = self.intercept + (dot / math.sqrt(norm) if norm > 0 else 0.0)
        return 1.0 / (1.0 + math.exp(-z))

    def score(self, firmware: str, spec: str) -> tuple[float, str]:
        """The worst chunk decides, since one hostile line makes the whole upload hostile."""
        best = 0.0
        worst_chunk = ""
        for chunk in chunks(firmware, spec):
            value = self.score_chunk(chunk)
            if value > best:
                best = value
                worst_chunk = chunk
        return best, worst_chunk


def load_model(path: Path = MODEL_PATH) -> Optional[GuardModel]:
    """None if there is no usable model. The regex rules and the sandbox still stand without one."""
    try:
        return GuardModel(json.loads(path.read_text()))
    except (OSError, ValueError, KeyError, TypeError):
        return None
