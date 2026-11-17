"""SHA-256 fingerprint of the frozen benchmark cases.

Method (stable across machines and operating systems):

1. Collect every regular file under bench/cases/, except `.gitkeep`, `.DS_Store` and anything
   under `__pycache__`.
2. Sort the files by their POSIX path relative to bench/cases/ (plain string order, byte-wise).
3. Feed this into one SHA-256, for each file in that order:
   the relative POSIX path (UTF-8), a NUL byte, the file's SHA-256 digest (32 raw bytes), a newline.
   Using each file's own digest means a file boundary can never be confused with file content.
4. The result is the hex digest of that stream.

Usage:
    python bench/freeze_hash.py                       print the hash and the file count of bench/cases/
    python bench/freeze_hash.py --check               exit 1 if it differs from the hash recorded in bench/README.md
    python bench/freeze_hash.py --dir practice        the same fingerprint for bench/practice/, a separate set
    python bench/freeze_hash.py --dir practice --check   compare it with the hash recorded in bench/practice/README.md

The practice set is for tuning and may change on purpose. Its fingerprint only says which version a result belongs to.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
README = HERE / "README.md"
SETS = {"frozen": (CASES, README), "practice": (HERE / "practice", HERE / "practice" / "README.md")}
SKIP_NAMES = {".gitkeep", ".DS_Store"}


def case_files(root: Path = CASES) -> list[Path]:
    files = [
        p for p in root.rglob("*")
        if p.is_file() and p.name not in SKIP_NAMES and "__pycache__" not in p.parts
    ]
    return sorted(files, key=lambda p: p.relative_to(root).as_posix().encode("utf-8"))


def freeze_hash(root: Path = CASES, skip: frozenset[str] = frozenset()) -> tuple[str, int]:
    """`skip` names top-level files that are left out, such as the README that records the hash itself."""
    outer = hashlib.sha256()
    files = [p for p in case_files(root) if p.relative_to(root).as_posix() not in skip]
    for p in files:
        outer.update(p.relative_to(root).as_posix().encode("utf-8"))
        outer.update(b"\0")
        outer.update(hashlib.sha256(p.read_bytes()).digest())
        outer.update(b"\n")
    return outer.hexdigest(), len(files)


def main() -> int:
    which = "practice" if "--dir" in sys.argv and sys.argv[sys.argv.index("--dir") + 1:][:1] == ["practice"] else "frozen"
    root, readme = SETS[which]
    # The practice README lives inside the set and holds its own hash, so it cannot be part of what is hashed.
    digest, n = freeze_hash(root, frozenset({"README.md"}) if which == "practice" else frozenset())
    if "--check" in sys.argv:
        m = re.search(r"freeze_hash\.py[^\n]*?`([0-9a-f]{64})`", readme.read_text())
        recorded = m.group(1) if m else ""
        print(f"computed {digest} ({n} files)\nrecorded {recorded or 'none found in ' + readme.name}")
        return 0 if recorded == digest else 1
    print(f"{digest}  {n} files under {root.relative_to(HERE.parent)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
