"""List models from the OpenAI-compatible endpoint in .env. The key is sent, and is never printed."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip("'\"")
    return values


def main() -> int:
    env_path = Path(".env")
    if not env_path.exists():
        print("No .env in this directory. Follow deploy/README.md.", file=sys.stderr)
        return 1
    env = read_env(env_path)
    base = env.get("LLM_BASE_URL", "").rstrip("/")
    key = env.get("LLM_API_KEY", "")
    if not base or not key:
        print("Set LLM_BASE_URL and LLM_API_KEY in .env first.", file=sys.stderr)
        return 1

    def clean(text: str) -> str:
        return text.replace(key, "[key removed]")

    request = urllib.request.Request(f"{base}/models", headers={"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "hexorcist-deploy"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"{base}/models returned HTTP {exc.code}: {clean(exc.read(400).decode(errors='replace'))}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Could not list models from {base}: {clean(str(exc))}", file=sys.stderr)
        return 1

    models = body.get("data", body) if isinstance(body, dict) else body
    ids = sorted(m["id"] if isinstance(m, dict) else str(m) for m in models)
    if not ids:
        print(f"{base}/models returned no models.", file=sys.stderr)
        return 1
    print(f"{len(ids)} model(s) at {base}:")
    for model_id in ids:
        marker = "  <- LLM_MODEL" if model_id == env.get("LLM_MODEL") else ""
        print(f"  {clean(model_id)}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
