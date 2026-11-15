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
    python bench/freeze_hash.py            print the hash and the file count
    python bench/freeze_hash.py --check    exit 1 if it differs from the hash recorded in bench/README.md
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

CASES = Path(__file__).resolve().parent / "cases"
README = Path(__file__).resolve().parent / "README.md"
SKIP_NAMES = {".gitkeep", ".DS_Store"}


def case_files() -> list[Path]:
    files = [
        p for p in CASES.rglob("*")
        if p.is_file() and p.name not in SKIP_NAMES and "__pycache__" not in p.parts
    ]
    return sorted(files, key=lambda p: p.relative_to(CASES).as_posix().encode("utf-8"))


def freeze_hash() -> tuple[str, int]:
    outer = hashlib.sha256()
    files = case_files()
    for p in files:
        outer.update(p.relative_to(CASES).as_posix().encode("utf-8"))
        outer.update(b"\0")
        outer.update(hashlib.sha256(p.read_bytes()).digest())
        outer.update(b"\n")
    return outer.hexdigest(), len(files)


def main() -> int:
    digest, n = freeze_hash()
    if "--check" in sys.argv:
        m = re.search(r"freeze_hash\.py[^\n]*?`([0-9a-f]{64})`", README.read_text())
        recorded = m.group(1) if m else ""
        print(f"computed {digest} ({n} files)\nrecorded {recorded or 'none found in bench/README.md'}")
        return 0 if recorded == digest else 1
    print(f"{digest}  {n} files under bench/cases/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
