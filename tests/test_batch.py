"""Tests for the batch driver."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vidknot.core.batch import BatchSummary, collect_urls, run_batch


def test_collect_urls_from_cli():
    urls = collect_urls(["https://a", "  https://b  ", ""])
    assert urls == ["https://a", "https://b"]


def test_collect_urls_from_file(tmp_path: Path):
    f = tmp_path / "urls.txt"
    f.write_text(
        "# comment line\n"
        "https://example.com/a\n"
        "\n"
        "https://example.com/b\n"
    )
    assert collect_urls([], urls_file=str(f)) == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_collect_urls_from_sources_file(tmp_path: Path):
    f = tmp_path / "sources.yaml"
    f.write_text(
        "sources:\n"
        "  - name: a\n"
        "    platform: youtube\n"
        "    url: https://example.com/a\n"
        "    kind: channel\n"
        "  - name: b\n"
        "    platform: douyin\n"
        "    url: https://example.com/b\n"
        "  - name: c\n"
        "    platform: yt\n"
        "    url: https://example.com/c\n"
        "    kind: hashtag\n"
        "  - name: d-no-url\n"
        "    platform: yt\n"
    )
    urls = collect_urls([], sources_file=str(f))
    # All entries with non-empty url are returned (any kind).
    # Entry 'd-no-url' has no url and is skipped.
    assert urls == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_collect_urls_empty_returns_empty():
    assert collect_urls([]) == []


def test_run_batch_aggregates_results():
    pipeline = MagicMock()
    pipeline.run_batch.return_value = [
        {"url": "u1", "success": True},
        {"url": "u2", "success": False, "error": "boom"},
        {"url": "u3", "success": True},
    ]
    summary = run_batch(pipeline, ["u1", "u2", "u3"])
    assert summary.total == 3
    assert summary.success == 2
    assert summary.failed == 1
    assert len(summary.results) == 3
    pipeline.run_batch.assert_called_once_with(
        urls=["u1", "u2", "u3"],
        max_workers=3,
        save_options=None,
    )


def test_run_batch_empty():
    pipeline = MagicMock()
    summary = run_batch(pipeline, [])
    assert summary.total == 0
    assert pipeline.run_batch.call_count == 0


def test_run_batch_passes_max_workers():
    pipeline = MagicMock()
    pipeline.run_batch.return_value = []
    run_batch(pipeline, ["u"], max_workers=8)
    _, kwargs = pipeline.run_batch.call_args
    assert kwargs["max_workers"] == 8


def test_batch_summary_to_dict():
    s = BatchSummary(total=2, success=2, failed=0, results=({"a": 1}, {"b": 2}))
    out = s.to_dict()
    assert out["total"] == 2
    assert out["results"] == [{"a": 1}, {"b": 2}]