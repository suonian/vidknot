"""Batch driver.

Thin glue over :meth:`VideoKnowledgePipeline.run_batch` plus URL
collection helpers. No URL lists or user data are baked in.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from ...pipeline.video_knowledge_pipeline import VideoKnowledgePipeline
from ..source import SourcesFile, load_sources_file


@dataclass(frozen=True)
class BatchSummary:
    total: int
    success: int
    failed: int
    results: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "results": list(self.results),
        }


def collect_urls(
    cli_urls: Sequence[str],
    *,
    urls_file: str | None = None,
    sources_file: str | None = None,
) -> list[str]:
    """Collect URLs from CLI args, a plain-text file, or a sources file."""
    if cli_urls:
        return [u.strip() for u in cli_urls if u.strip()]

    if urls_file:
        text = Path(urls_file).read_text(encoding="utf-8")
        urls: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            urls.append(stripped)
        return urls

    if sources_file:
        bundle: SourcesFile = load_sources_file(sources_file)
        return [s.url for s in bundle.sources if s.url]

    return []


def run_batch(
    pipeline: VideoKnowledgePipeline,
    urls: Iterable[str],
    *,
    max_workers: int = 3,
    save_options: dict | None = None,
) -> BatchSummary:
    url_list = list(urls)
    if not url_list:
        return BatchSummary(total=0, success=0, failed=0)

    results = pipeline.run_batch(
        urls=url_list,
        max_workers=max_workers,
        save_options=save_options,
    )
    success = sum(1 for r in results if r.get("success"))
    failed = len(results) - success
    return BatchSummary(
        total=len(results),
        success=success,
        failed=failed,
        results=tuple(results),
    )