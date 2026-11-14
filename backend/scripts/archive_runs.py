"""Mark old runs as archived so the UI hides them. Does not delete rows or traces.

Run from backend/:
  python -m scripts.archive_runs --before 2026-11-13
  HEXORCIST_DB=/path/to.sqlite3 python -m scripts.archive_runs --before 2026-11-13
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from app.config import load_settings
from app.store import Store


def parse_before(value: str) -> float:
    """Midnight UTC on the given calendar day. Runs with created_at before that are archived."""
    try:
        day = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from e
    return day.timestamp()


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive runs created before a date (UI hides them; data stays).")
    parser.add_argument("--before", required=True, type=parse_before, metavar="YYYY-MM-DD", help="Archive runs created before this date (UTC midnight)")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    settings = load_settings()
    store = Store(settings.db_path)
    n = store.count_to_archive(args.before)
    day = datetime.fromtimestamp(args.before, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"Database: {settings.db_path}")
    print(f"Will archive {n} run(s) created before {day} UTC.")
    if n == 0:
        return 0
    if not args.yes:
        reply = input("Type yes to continue: ").strip().lower()
        if reply != "yes":
            print("Aborted.")
            return 1
    archived = store.archive_before(args.before)
    print(f"Archived {archived} run(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
