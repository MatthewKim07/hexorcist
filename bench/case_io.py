"""Load and list frozen benchmark cases under bench/cases/."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BENCH_ROOT = Path(__file__).resolve().parent
FROZEN_DIR = BENCH_ROOT / "cases"
PRACTICE_DIR = BENCH_ROOT / "practice"
# The frozen v2 set unless BENCH_CASES_DIR or a tool's --dir says otherwise. Only the frozen set is part of the freeze check.
CASES_DIR = Path(os.environ["BENCH_CASES_DIR"]).resolve() if os.environ.get("BENCH_CASES_DIR") else FROZEN_DIR
PROMPTS_DIR = BENCH_ROOT / "prompts"
RESULTS_DIR = BENCH_ROOT / "results"
CACHE_DIR = BENCH_ROOT / "cache"
JUDGEMENTS_DIR = BENCH_ROOT / "judgements"


@dataclass(frozen=True)
class Case:
    id: str
    root: Path
    sketch: str
    reference: str
    spec: str
    pins: list[dict[str, Any]]
    truth: list[dict[str, Any]]
    checks: dict[str, Any]

    @property
    def categories(self) -> list[str]:
        cats = [b.get("category", "") for b in self.truth]
        return cats if cats else ["correct"]

    @property
    def is_correct(self) -> bool:
        return len(self.truth) == 0

    @property
    def truth_check_ids(self) -> set[str]:
        ids: set[str] = set()
        for bug in self.truth:
            for cid in bug.get("check_ids", []):
                ids.add(cid)
        return ids


def resolve_cases_dir(value: str) -> Path:
    """`practice` and `frozen` name the two bundled sets; anything else is a path."""
    named = {"practice": PRACTICE_DIR, "frozen": FROZEN_DIR, "cases": FROZEN_DIR}
    path = named.get(value) or Path(value).resolve()
    if not path.is_dir():
        raise SystemExit(f"no case directory at {path}")
    return path


def use_cases_dir(value: str) -> Path:
    """Point load_case and list_case_ids at another case directory for the rest of this process."""
    global CASES_DIR
    CASES_DIR = resolve_cases_dir(value)
    return CASES_DIR


def add_dir_option(parser) -> None:
    parser.add_argument("--dir", default="", help="case directory: practice, frozen (the default) or a path")


def apply_dir_option(args) -> None:
    if getattr(args, "dir", ""):
        use_cases_dir(args.dir)


def list_case_ids() -> list[str]:
    if not CASES_DIR.is_dir():
        return []
    return sorted(p.name for p in CASES_DIR.iterdir() if p.is_dir() and (p / "truth.json").is_file())


def load_case(case_id: str) -> Case:
    root = CASES_DIR / case_id
    if not root.is_dir():
        raise FileNotFoundError(f"unknown case: {case_id}")
    return Case(
        id=case_id,
        root=root,
        sketch=(root / "sketch.ino").read_text(),
        reference=(root / "reference.ino").read_text(),
        spec=(root / "spec.md").read_text(),
        pins=json.loads((root / "pins.json").read_text()),
        truth=json.loads((root / "truth.json").read_text()),
        checks=json.loads((root / "checks.json").read_text()),
    )


def load_cases(ids: list[str] | None = None) -> list[Case]:
    wanted = ids or list_case_ids()
    return [load_case(i) for i in wanted]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n")
