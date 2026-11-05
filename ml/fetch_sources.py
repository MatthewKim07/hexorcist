"""Download the public data into ml/.cache. Nothing here is committed.

Sources and licenses, checked on 2026-11-04:
- deepset/prompt-injections, Apache-2.0
- Lakera/gandalf_ignore_instructions, MIT
- arduino/arduino-examples, CC0-1.0
- arduino/ArduinoCore-avr and arduino-libraries/*, library examples, LGPL or similar, used only as
  evaluation data on this machine and never redistributed

Run from the repo root: ml/.venv/bin/python ml/fetch_sources.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx

CACHE = Path(__file__).parent / ".cache"
ROWS = "https://datasets-server.huggingface.co/rows"
DATASETS = {
    "deepset": ("deepset/prompt-injections", "default", ["train", "test"]),
    "gandalf": ("Lakera/gandalf_ignore_instructions", "default", ["train", "validation", "test"]),
}
REPOS = {
    "arduino-examples": "https://github.com/arduino/arduino-examples.git",
    "arduino-core": "https://github.com/arduino/ArduinoCore-avr.git",
    "lib-servo": "https://github.com/arduino-libraries/Servo.git",
    "lib-lcd": "https://github.com/arduino-libraries/LiquidCrystal.git",
    "lib-stepper": "https://github.com/arduino-libraries/Stepper.git",
    "lib-sd": "https://github.com/arduino-libraries/SD.git",
    "lib-ethernet": "https://github.com/arduino-libraries/Ethernet.git",
    "lib-wifi": "https://github.com/arduino-libraries/WiFi.git",
    "lib-wifi101": "https://github.com/arduino-libraries/WiFi101.git",
}


def fetch_dataset(name: str, repo: str, config: str, splits: list[str]) -> None:
    for split in splits:
        out = CACHE / f"{name}_{split}.jsonl"
        if out.exists():
            continue
        rows: list[dict] = []
        offset = 0
        while True:
            response = httpx.get(ROWS, params={"dataset": repo, "config": config, "split": split, "offset": offset, "length": 100}, timeout=60, follow_redirects=True)
            response.raise_for_status()
            page = [r["row"] for r in response.json()["rows"]]
            if not page:
                break
            rows.extend(page)
            offset += len(page)
        out.write_text("".join(json.dumps(r) + "\n" for r in rows))
        print(f"{out.name}: {len(rows)} rows")


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    for name, (repo, config, splits) in DATASETS.items():
        fetch_dataset(name, repo, config, splits)
    for name, url in REPOS.items():
        target = CACHE / name
        if not target.exists():
            subprocess.run(["git", "clone", "--quiet", "--depth", "1", url, str(target)], check=True)
        print(f"{name}: {sum(1 for _ in target.rglob('*.ino'))} sketches")


if __name__ == "__main__":
    main()
