"""Assemble train, val and test documents, each one a firmware and spec pair, into ml/dataset/.

Every attack sits inside a realistic benign carrier from the same split, so the model cannot pass by
learning "Arduino code is benign". Test carriers, test benign text and held-out attack styles never
appear in training. The output is reproducible from the seed and is not committed.

Run from the repo root: ml/.venv/bin/python ml/build_dataset.py
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(HERE))

from app.guard_model import normalize  # noqa: E402
from app.presets import PRESETS  # noqa: E402
from families import HARD_NEGATIVES, HELD_OUT_FAMILIES, LINE_FAMILIES, TRAIN_FAMILIES  # noqa: E402
from tests.fixtures import CORRECT_FIRMWARE  # noqa: E402

CACHE = HERE / ".cache"
OUT = HERE / "dataset"
SEED = 20261104
TRAIN_PER_FAMILY = 150
VAL_PER_FAMILY = 30
TEST_PER_FAMILY = 70
TEST_LIBRARIES = ["arduino-core", "lib-servo", "lib-lcd", "lib-stepper", "lib-sd", "lib-ethernet", "lib-wifi", "lib-wifi101"]


def doc(split: str, label: int, family: str, source: str, firmware: str, spec: str, payload: str = "") -> dict:
    return {"split": split, "label": label, "family": family, "source": source, "firmware": firmware, "spec": spec, "payload": payload}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def inject(carrier: dict, text: str, where: str, rng: random.Random) -> tuple[str, str]:
    firmware, spec = carrier["firmware"], carrier["spec"]
    if where == "spec":
        parts = spec.split(". ")
        parts.insert(rng.randint(0, len(parts)), text.rstrip("."))
        return firmware, ". ".join(parts)
    lines = firmware.splitlines()
    position = rng.choice([0, rng.randint(0, len(lines)), len(lines)])
    if where == "string":
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        insert = [f'const char NOTE[] = "{escaped}";']
    elif where == "code":
        insert = text.splitlines()
        position = rng.randint(0, min(5, len(lines)))
    elif "\n" in text:
        insert = ["/*", *text.splitlines(), "*/"]
    else:
        insert = [f"// {text}"]
    return "\n".join(lines[:position] + insert + lines[position:]) + "\n", spec


def attack_docs(split: str, family: str, source: str, texts: list[str], carriers: list[dict], rng: random.Random) -> list[dict]:
    out = []
    for text in texts:
        where = "code" if family in LINE_FAMILIES else rng.choice(["comment", "comment", "spec", "string"])
        firmware, spec = inject(rng.choice(carriers), text, where, rng)
        out.append(doc(split, 1, family, source, firmware, spec, text))
    return out


def sketches(repo: str) -> list[Path]:
    return sorted((CACHE / repo).rglob("*.ino"))


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(exist_ok=True)
    llm = read_jsonl(HERE / "corpus" / "llm_benign.jsonl")
    carriers: dict[str, list[dict]] = {s: [{"firmware": p["firmware"], "spec": p["spec"]} for p in llm if p["split"] == s] for s in ("train", "val", "test")}
    docs: list[dict] = []

    # ---- benign
    for split, projects in carriers.items():
        docs.extend(doc(split, 0, "llm_project", "llm", p["firmware"], p["spec"]) for p in projects)
    examples = sketches("arduino-examples")
    rng.shuffle(examples)
    # A quarter go to validation, so the threshold is set on real human code the model did not train on.
    cut = len(examples) // 4
    for i, path in enumerate(examples):
        docs.append(doc("val" if i < cut else "train", 0, "arduino_example", "arduino-examples", path.read_text(errors="replace"), ""))
    for preset in PRESETS:
        if preset["id"] != "containment":
            docs.append(doc("train", 0, "preset", "presets", preset["firmware"], preset["behaviour"]))
            docs.append(doc("train", 0, "preset", "presets", CORRECT_FIRMWARE[preset["id"]], preset["behaviour"]))
    # Real prompts labelled benign, so generic English is not read as an attack. These have no sketch.
    deepset_train = read_jsonl(CACHE / "deepset_train.jsonl")
    docs.extend(doc("train", 0, "public_benign", "deepset", "", r["text"]) for r in deepset_train if r["label"] == 0)
    for repo in TEST_LIBRARIES:
        for path in sketches(repo):
            docs.append(doc("test", 0, "arduino_library", repo, path.read_text(errors="replace"), ""))
    for split, sentences in HARD_NEGATIVES.items():
        for sentence in sentences:
            family = "hard_negative"
            where = "code" if sentence.startswith(("#include", "char ", "Serial.")) else rng.choice(["comment", "spec"])
            firmware, spec = inject(rng.choice(carriers[split]), sentence, where, rng)
            docs.append(doc(split, 0, family, "handwritten", firmware, spec))

    # Harmless uses of attack words, by another author. Split by sentence and shuffled with a fixed seed.
    written = read_jsonl(HERE / "corpus" / "llm_hard_negatives.jsonl")
    random.Random(SEED + 1).shuffle(written)
    train_end, val_end = int(len(written) * 0.6), int(len(written) * 0.8)
    for split, rows in (("train", written[:train_end]), ("val", written[train_end:val_end]), ("test", written[val_end:])):
        for row in rows:
            firmware, spec = inject(rng.choice(carriers[split]), row["text"], rng.choice(["comment", "spec"]), rng)
            docs.append(doc(split, 0, "llm_hard_negative", "llm", firmware, spec))

    # Real uploads and model patches from earlier runs set the threshold, since they are what it will face.
    for row in read_jsonl(HERE / "corpus" / "real_runs.jsonl"):
        docs.append(doc("val", 0, "real_run", row["kind"], row["firmware"], row["spec"]))

    # ---- attacks in training styles
    for family, make in TRAIN_FAMILIES.items():
        for split, count in (("train", TRAIN_PER_FAMILY), ("val", VAL_PER_FAMILY)):
            docs.extend(attack_docs(split, family, "handwritten", [make(rng) for _ in range(count)], carriers[split], rng))
    public = [r["text"] for r in read_jsonl(CACHE / "gandalf_train.jsonl")] + [r["text"] for r in deepset_train if r["label"] == 1]
    docs.extend(attack_docs("train", "public_injection", "gandalf+deepset", public, carriers["train"], rng))
    public_val = [r["text"] for r in read_jsonl(CACHE / "gandalf_validation.jsonl")]
    docs.extend(attack_docs("val", "public_injection", "gandalf", public_val, carriers["val"], rng))

    # ---- held-out attack styles, test only
    for family, make in HELD_OUT_FAMILIES.items():
        docs.extend(attack_docs("test", family, "handwritten", [make(rng) for _ in range(TEST_PER_FAMILY)], carriers["test"], rng))
    llm_attacks = read_jsonl(HERE / "corpus" / "llm_attacks.jsonl")
    for sample in llm_attacks:
        where = {"spec": "spec", "string": "string"}.get(sample["where"], "comment")
        firmware, spec = inject(rng.choice(carriers["test"]), sample["text"], where, rng)
        docs.append(doc("test", 1, f"llm_{sample['style']}", "llm", firmware, spec, sample["text"]))
    # Unseen samples of a seen style, so this one is not a new style. It is reported as such.
    public_test = [r["text"] for r in read_jsonl(CACHE / "gandalf_test.jsonl")]
    docs.extend(attack_docs("test", "public_injection", "gandalf", public_test, carriers["test"], rng))

    # ---- no payload seen in training may reappear in test
    seen = {normalize(d["payload"]).lower() for d in docs if d["split"] == "train" and d["label"] == 1}
    before = len(docs)
    docs = [d for d in docs if d["split"] != "test" or d["label"] == 0 or normalize(d["payload"]).lower() not in seen]
    print(f"removed {before - len(docs)} test attacks whose exact text was in training")

    for split in ("train", "val", "test"):
        rows = [d for d in docs if d["split"] == split]
        rng.shuffle(rows)
        (OUT / f"{split}.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in rows))
        counts = Counter((d["label"], d["family"]) for d in rows)
        print(f"\n{split}: {len(rows)} documents, {sum(d['label'] for d in rows)} malicious")
        for (label, family), n in sorted(counts.items()):
            print(f"  {'attack' if label else 'benign'}  {family:<20} {n}")


if __name__ == "__main__":
    main()
