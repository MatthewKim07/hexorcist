"""SQLite persistence for runs, their event logs and their traces."""
from __future__ import annotations

import gzip
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    finished_at REAL,
    mode TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    firmware TEXT NOT NULL,
    spec TEXT NOT NULL,
    guard TEXT NOT NULL,
    report TEXT,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS traces (
    run_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    scenario_id TEXT NOT NULL,
    payload BLOB NOT NULL,
    PRIMARY KEY (run_id, iteration, scenario_id)
);
CREATE TABLE IF NOT EXISTS reviews (
    run_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    payload TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)
            self._migrate()
            # A restart kills in-flight runs, so do not leave them claiming to be running.
            self._db.execute("UPDATE runs SET status='interrupted', finished_at=? WHERE status='running'", (time.time(),))
            self._db.commit()

    def _migrate(self) -> None:
        """Add columns that older databases are missing. Never drops data."""
        cols = {row[1] for row in self._db.execute("PRAGMA table_info(runs)").fetchall()}
        if "archived" not in cols:
            self._db.execute("ALTER TABLE runs ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")

    def create_run(self, run_id: str, mode: str, title: str, firmware: str, spec: dict, guard: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO runs (id, created_at, mode, title, status, firmware, spec, guard) VALUES (?, ?, ?, ?, 'running', ?, ?, ?)",
                (run_id, time.time(), mode, title, firmware, json.dumps(spec), json.dumps(guard)),
            )
            self._db.commit()

    def finish_run(self, run_id: str, status: str, report: Optional[dict]) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE runs SET status=?, finished_at=?, report=? WHERE id=?",
                (status, time.time(), json.dumps(report) if report is not None else None, run_id),
            )
            self._db.commit()

    def add_event(self, run_id: str, seq: int, event: dict) -> None:
        with self._lock:
            self._db.execute("INSERT INTO events (run_id, seq, payload) VALUES (?, ?, ?)", (run_id, seq, json.dumps(event)))
            self._db.commit()

    def events(self, run_id: str, after: int = 0) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT payload FROM events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after)).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def add_trace(self, run_id: str, iteration: int, scenario_id: str, trace: dict) -> None:
        blob = gzip.compress(json.dumps(trace).encode(), compresslevel=5)
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO traces (run_id, iteration, scenario_id, payload) VALUES (?, ?, ?, ?)",
                (run_id, iteration, scenario_id, blob),
            )
            self._db.commit()

    def get_trace(self, run_id: str, iteration: int, scenario_id: str) -> Optional[dict]:
        with self._lock:
            row = self._db.execute(
                "SELECT payload FROM traces WHERE run_id=? AND iteration=? AND scenario_id=?",
                (run_id, iteration, scenario_id),
            ).fetchone()
        return json.loads(gzip.decompress(row["payload"])) if row else None

    def save_review(self, run_id: str, review: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO reviews (run_id, created_at, payload) VALUES (?, ?, ?)", (run_id, time.time(), json.dumps(review)))
            self._db.commit()

    def get_review(self, run_id: str) -> Optional[dict]:
        with self._lock:
            row = self._db.execute("SELECT payload FROM reviews WHERE run_id=?", (run_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def get_run(self, run_id: str) -> Optional[dict]:
        with self._lock:
            row = self._db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "finished_at": row["finished_at"],
            "mode": row["mode"],
            "title": row["title"],
            "status": row["status"],
            "firmware": row["firmware"],
            "spec": json.loads(row["spec"]),
            "guard": json.loads(row["guard"]),
            "report": json.loads(row["report"]) if row["report"] else None,
        }

    def list_runs(self, limit: int = 100) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, created_at, finished_at, mode, title, status, report FROM runs WHERE archived = 0 ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            report = json.loads(r["report"]) if r["report"] else {}
            out.append(
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "finished_at": r["finished_at"],
                    "mode": r["mode"],
                    "title": r["title"],
                    "status": r["status"],
                    "score": report.get("score"),
                }
            )
        return out

    def count_to_archive(self, before_ts: float) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT COUNT(*) AS n FROM runs WHERE archived = 0 AND created_at < ?",
                (before_ts,),
            ).fetchone()
        return int(row["n"])

    def archive_before(self, before_ts: float) -> int:
        """Mark runs created before before_ts as archived. Rows and traces stay."""
        with self._lock:
            cur = self._db.execute(
                "UPDATE runs SET archived = 1 WHERE archived = 0 AND created_at < ?",
                (before_ts,),
            )
            self._db.commit()
            return cur.rowcount
