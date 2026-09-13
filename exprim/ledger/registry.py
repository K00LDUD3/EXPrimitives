from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import FILE_REGISTRY_DB

#_: schema

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    relative_path   TEXT NOT NULL,
    fingerprint     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    tags            TEXT NOT NULL DEFAULT '[]',
    notes_count     INTEGER NOT NULL DEFAULT 0,
    final_step      INTEGER,
    failure_reason  TEXT
);

CREATE INDEX IF NOT EXISTS idx_name        ON runs(name);
CREATE INDEX IF NOT EXISTS idx_fingerprint ON runs(fingerprint);
CREATE INDEX IF NOT EXISTS idx_status      ON runs(status);
CREATE INDEX IF NOT EXISTS idx_created_at  ON runs(created_at);
"""

#_: run status values

STATUS_RUNNING  = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED   = "failed"


class Registry:
    """
    SQLite-backed persistent registry of all runs under a runs directory.
    Stores relative paths only — survives moving the runs directory.

    One Registry per runs directory. Lives at runs_dir/ledger.db.
    """

    def __init__(self, runs_dir: Path) -> None:
        self._runs_dir = runs_dir
        self._db_path  = runs_dir / FILE_REGISTRY_DB
        self._conn     = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    #_: write

    def register(
        self,
        run_id:        str,
        name:          str,
        relative_path: str,
        fingerprint:   str,
        tags:          list[str] | None = None,
    ) -> None:
        """Insert a new run record into the registry."""
        now = _now()
        self._conn.execute(
            """
            INSERT INTO runs
                (run_id, name, relative_path, fingerprint, status,
                 created_at, updated_at, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                name,
                relative_path,
                fingerprint,
                STATUS_RUNNING,
                now,
                now,
                json.dumps(tags or []),
            ),
        )
        self._conn.commit()

    def update_status(
        self,
        run_id:         str,
        status:         str,
        failure_reason: str | None = None,
        final_step:     int | None = None,
    ) -> None:
        """Update run status — running / complete / failed."""
        self._conn.execute(
            """
            UPDATE runs
            SET status = ?, updated_at = ?, failure_reason = ?, final_step = ?
            WHERE run_id = ?
            """,
            (status, _now(), failure_reason, final_step, run_id),
        )
        self._conn.commit()

    def update_tags(self, run_id: str, tags: list[str]) -> None:
        """Replace the tag list for a run."""
        self._conn.execute(
            "UPDATE runs SET tags = ?, updated_at = ? WHERE run_id = ?",
            (json.dumps(tags), _now(), run_id),
        )
        self._conn.commit()

    def increment_notes(self, run_id: str) -> None:
        """Increment the notes counter for a run."""
        self._conn.execute(
            "UPDATE runs SET notes_count = notes_count + 1, updated_at = ? WHERE run_id = ?",
            (_now(), run_id),
        )
        self._conn.commit()

    def delete(self, run_id: str) -> None:
        """Remove a run record from the registry."""
        self._conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        self._conn.commit()

    #_: read

    def get(self, run_id: str) -> dict[str, Any] | None:
        """Fetch a single run record by run_id. Returns None if not found."""
        row = self._conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    def find_by_fingerprint(self, fingerprint: str) -> list[dict[str, Any]]:
        """Return all runs with a matching config fingerprint."""
        rows = self._conn.execute(
            "SELECT * FROM runs WHERE fingerprint = ? ORDER BY created_at DESC",
            (fingerprint,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def list_runs(
        self,
        name:   str | None       = None,
        tags:   list[str] | None = None,
        status: str | None       = None,
        after:  str | None       = None,
        before: str | None       = None,
    ) -> list[dict[str, Any]]:
        """
        Query runs with optional filters.

        Args:
            name:   exact experiment name match
            tags:   list of tags — returns runs containing ALL specified tags
            status: "running" | "complete" | "failed"
            after:  ISO date string e.g. "2026-01-01"
            before: ISO date string e.g. "2026-06-01"
        """
        query  = "SELECT * FROM runs WHERE 1=1"
        params: list[Any] = []

        if name:
            query += " AND name = ?"
            params.append(name)
        if status:
            query += " AND status = ?"
            params.append(status)
        if after:
            query += " AND created_at >= ?"
            params.append(after)
        if before:
            query += " AND created_at <= ?"
            params.append(before)

        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        results = [_row_to_dict(r) for r in rows]

        # tag filtering done in Python — SQLite JSON querying is version-dependent
        if tags:
            results = [
                r for r in results
                if all(t in r["tags"] for t in tags)
            ]

        return results

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()


#_: helpers

def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    return d
