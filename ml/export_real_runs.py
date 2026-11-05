"""Save the real uploads and model-written patches from a running stack, to set the threshold on real usage.

Hostile presets are skipped. Everything else was written by the model or is a preset, so it holds no user data.

Run from the repo root with the stack up: ml/.venv/bin/python ml/export_real_runs.py [api-url]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

OUT = Path(__file__).parent / "corpus" / "real_runs.jsonl"


def main() -> None:
    api = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    client = httpx.Client(base_url=api, timeout=60)
    seen: dict[tuple[str, str], str] = {}
    for run in client.get("/api/runs").json():
        report = client.get(f"/api/runs/{run['id']}").json().get("report") or {}
        if not report or report.get("status") in ("contained", "blocked"):
            continue
        seen.setdefault((report.get("firmware", ""), (report.get("spec") or {}).get("behaviour", "")), "upload")
        for iteration in report.get("iterations", []):
            if iteration.get("patch"):
                seen.setdefault((iteration["patch"], ""), "patch")
    rows = [{"kind": kind, "firmware": firmware, "spec": spec} for (firmware, spec), kind in seen.items()]
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    print(f"wrote {len(rows)} real uploads and patches, {OUT.stat().st_size / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
