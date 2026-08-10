"""SQLite-backed local persistence backend.

Useful for development, testing, and lightweight local-only usage where
no cloud destination is configured. The SQLite database path is taken
from the ``path`` key of the backend config, falling back to the
``VIDKNOT_SQLITE_PATH`` environment variable, then to a sensible
default. No credentials or remote endpoints are involved.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .base import BackendError, BackendStorage, NotePayload, StorageResult

_DEFAULT_PATH = "./vidknot_notes.db"


class SqliteBackend(BackendStorage):
    """Persist notes to a single-table SQLite database.

    Schema::

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source_url TEXT,
            tags TEXT,
            markdown TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """

    name = "sqlite"

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        super().__init__(config)
        path_str = (
            self._config.get("path")
            or os.getenv("VIDKNOT_SQLITE_PATH")
            or _DEFAULT_PATH
        )
        self._path = Path(path_str).expanduser()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_url TEXT,
                    tags TEXT,
                    markdown TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save(self, payload: NotePayload) -> StorageResult:
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO notes(title, source_url, tags, markdown, metadata) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (
                        payload.title,
                        payload.source_url,
                        ",".join(payload.tags),
                        payload.markdown,
                        _json_dumps(payload.metadata),
                    ),
                )
                rowid = cur.lastrowid
        except sqlite3.Error as exc:
            raise BackendError(f"SQLite save failed: {exc}") from exc
        return StorageResult(
            backend_name=self.name,
            location=f"sqlite://{self._path}#{rowid}",
            ok=True,
        )

    def save_many(self, payloads: Iterable[NotePayload]) -> list[StorageResult]:
        items = list(payloads)
        try:
            with self._connect() as conn:
                results: list[StorageResult] = []
                for payload in items:
                    cur = conn.execute(
                        "INSERT INTO notes(title, source_url, tags, markdown, metadata) "
                        "VALUES(?, ?, ?, ?, ?)",
                        (
                            payload.title,
                            payload.source_url,
                            ",".join(payload.tags),
                            payload.markdown,
                            _json_dumps(payload.metadata),
                        ),
                    )
                    results.append(
                        StorageResult(
                            backend_name=self.name,
                            location=f"sqlite://{self._path}#{cur.lastrowid}",
                            ok=True,
                        )
                    )
                conn.commit()
                return results
        except sqlite3.Error as exc:
            raise BackendError(f"SQLite save_many failed: {exc}") from exc


def _json_dumps(meta: Mapping[str, Any]) -> str:
    import json

    return json.dumps(dict(meta), ensure_ascii=False, default=str)
