"""Tests for the backend abstraction layer."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from vidknot.core.backend import (
    BackendRegistry,
    BackendStorage,
    NotePayload,
    StorageResult,
    build_default_registry,
)
from vidknot.core.backend.base import BackendError
from vidknot.core.backend.sqlite import SqliteBackend


def _sample_payload(title: str = "Test Note") -> NotePayload:
    return NotePayload(
        title=title,
        markdown="# " + title + "\n\nBody content.",
        source_url="https://example.com/video",
        metadata={"duration": 293, "author": "tester"},
        tags=("test", "demo"),
    )


class TestNotePayload:
    def test_defaults_are_empty(self):
        p = NotePayload(title="t", markdown="m", source_url="s")
        assert p.tags == ()
        assert dict(p.metadata) == {}

    def test_frozen(self):
        p = _sample_payload()
        with pytest.raises(Exception):
            p.title = "other"  # type: ignore[misc]


class TestRegistry:
    def test_register_and_build(self):
        reg = BackendRegistry()

        class MyBackend(BackendStorage):
            name = "demo"

            def save(self, payload: NotePayload) -> StorageResult:
                return StorageResult(backend_name=self.name, location="mem://x", ok=True)

        reg.register(MyBackend)
        assert "demo" in reg.names()
        backend = reg.build("demo")
        result = backend.save(_sample_payload())
        assert result.ok is True
        assert result.location == "mem://x"

    def test_register_rejects_abstract(self):
        reg = BackendRegistry()
        with pytest.raises(ValueError):
            reg.register(BackendStorage)

    def test_build_unknown_raises(self):
        reg = BackendRegistry()
        with pytest.raises(BackendError):
            reg.build("nope")


class TestSqliteBackend:
    def test_save_persists_row(self, tmp_path: Path):
        db_path = tmp_path / "notes.db"
        backend = SqliteBackend({"path": str(db_path)})
        result = backend.save(_sample_payload())
        assert result.ok is True
        assert "sqlite://" in result.location
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute("SELECT title, tags, markdown FROM notes").fetchall()
        assert len(rows) == 1
        title, tags, markdown = rows[0]
        assert title == "Test Note"
        assert tags == "test,demo"
        assert markdown.startswith("# Test Note")

    def test_save_many_batches(self, tmp_path: Path):
        backend = SqliteBackend({"path": str(tmp_path / "many.db")})
        results = backend.save_many([_sample_payload(f"N{i}") for i in range(3)])
        assert all(r.ok for r in results)
        assert len(results) == 3
        with sqlite3.connect(str(tmp_path / "many.db")) as conn:
            count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        assert count == 3

    def test_default_path_from_env(self, monkeypatch, tmp_path):
        db_path = tmp_path / "env.db"
        monkeypatch.setenv("VIDKNOT_SQLITE_PATH", str(db_path))
        backend = SqliteBackend()
        backend.save(_sample_payload())
        assert db_path.exists()


class TestFactory:
    def test_default_registry_includes_sqlite(self):
        reg = build_default_registry()
        assert reg.has("sqlite")
        assert "sqlite" in reg.names()