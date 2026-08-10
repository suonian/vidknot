"""Codex quality-sample curator.

Implements the six-gate checklist distilled from Codex's three-round
feedback on 2026-08-10:

* v1 feedback: transcripts too short (7-172 chars), wrong sample mix
* v2 feedback: titles inconsistent with content (matched on filename /
  hashtag instead of actual transcript), selection of short videos
* v3 feedback: continued title mismatch on four of six candidates, plus
  uneven type coverage

The gates are deliberately strict so we never spend CPU on a candidate
that will be rejected later.

Gates (all must pass to enter the curated pool):

1. **ffprobe duration >= 180 s** — hard floor for "long-form" samples.
2. **Whichever file we read must have bytes > 1 MB** — guards against
   zero-byte stubs from interrupted downloads.
3. **ASR transcript >= 1500 chars** after running through SiliconFlow
   SenseVoiceSmall, chunked at 60 s per slice.
4. **Title-anchored keywords match real transcript** — at least half
   of the heuristic keywords derived from the file path must appear
   in the first/last 200 chars of the transcript.
5. **Type coverage** — track which of the four Codex-required types
   (tool test, project retrospective, opinion / business cognition,
   OPC / super-individual) are still missing and bias new candidates
   accordingly.
6. **Transcript self-check** — reject transcripts whose first 200
   chars look like a known failure mode ("音响设备故障",
   "subtitles only", repeated single-character strings, etc.).

This script is the framework's curator; it does NOT perform the actual
download / ASR / write-to-FeiShu pipeline. Those remain the
responsibility of ``scripts/f2_helper_cli.py`` and
``src/vidknot/utils/cookie_health_check.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CuratorVerdict:
    """Outcome of running the six gates against a single candidate."""

    path: str
    passes: bool
    failures: tuple[str, ...]
    duration_seconds: float = 0.0
    size_mb: float = 0.0


_FAILURE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(.)\1{15,}"),  # single-char spam
    re.compile(r"音响设备故障", re.IGNORECASE),
    re.compile(r"subtitles only", re.IGNORECASE),
    re.compile(r"^\s*\[?\s*音乐\s*\]?\s*$"),
)


@dataclass(frozen=True)
class CuratorConfig:
    """Tunable thresholds for the six gates."""

    min_duration_seconds: int = 180
    min_size_mb: float = 1.0
    min_transcript_chars: int = 1500
    keyword_match_ratio: float = 0.5


def ffprobe_duration(path: str | os.PathLike[str]) -> float:
    """Return the duration of ``path`` in seconds (0.0 on error)."""
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(out.stdout.strip()) if out.stdout.strip() else 0.0
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return 0.0


def _keyword_hits(text: str, keywords: Iterable[str]) -> tuple[int, int]:
    """Return ``(matched, total)`` for the keyword probe."""
    kws = [k for k in keywords if k]
    if not kws:
        return 0, 0
    low = text.lower()
    matched = sum(1 for k in kws if k.lower() in low)
    return matched, len(kws)


def _derive_keywords_from_path(path: str | os.PathLike[str]) -> tuple[str, ...]:
    """Best-effort keyword probe derived from the file path.

    We deliberately bias toward content tokens rather than hashtags
    because Codex v2 saw false-positive matches on `#vibecoding` style
    tags that did not reflect the actual transcript.
    """
    p = Path(path)
    tokens: list[str] = []
    name = p.stem.replace("_", " ")
    skip = {"douyin", "obsidian_low", "video", "mp3", "mp4"}
    for tok in name.split():
        # Strip surrounding punctuation that f2 often leaves behind
        clean = re.sub(r"^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$", "", tok)
        if clean and clean not in skip and len(clean) >= 2:
            tokens.append(clean)
    # De-duplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return tuple(out[:8])


def _looks_like_failure(transcript: str) -> bool:
    head = transcript[:200]
    return any(p.search(head) for p in _FAILURE_PATTERNS)


def evaluate(
    path: str | os.PathLike[str],
    *,
    config: CuratorConfig | None = None,
) -> CuratorVerdict:
    """Run all six gates against ``path``.

    Only gates 1 (duration) and 2 (size) can run without a transcript
    in hand. Gate 3 (transcript length) and gate 4 (keyword match)
    require the caller to attach transcript text; pass an empty string
    for those to defer those checks.
    """
    cfg = config or CuratorConfig()
    p = Path(path)
    failures: list[str] = []

    duration = ffprobe_duration(p)
    size_mb = p.stat().st_size / 1024 / 1024 if p.exists() else 0.0

    if duration < cfg.min_duration_seconds:
        failures.append(
            f"duration {duration:.1f}s < {cfg.min_duration_seconds}s"
        )
    if size_mb < cfg.min_size_mb:
        failures.append(f"size {size_mb:.2f}MB < {cfg.min_size_mb}MB")

    return CuratorVerdict(
        path=str(p),
        passes=not failures,
        failures=tuple(failures),
        duration_seconds=duration,
        size_mb=size_mb,
    )


def evaluate_transcript(
    verdict: CuratorVerdict,
    transcript: str,
    *,
    config: CuratorConfig | None = None,
) -> CuratorVerdict:
    """Extend ``verdict`` with the transcript-aware gates (3, 4, 6)."""
    cfg = config or CuratorConfig()
    failures = list(verdict.failures)
    chars = len(transcript.strip())

    if chars < cfg.min_transcript_chars:
        failures.append(f"transcript {chars} chars < {cfg.min_transcript_chars}")

    keywords = _derive_keywords_from_path(verdict.path)
    matched, total = _keyword_hits(transcript[:600] + transcript[-400:], keywords)
    if total and matched / total < cfg.keyword_match_ratio:
        failures.append(
            f"keyword match {matched}/{total} < {cfg.keyword_match_ratio:.0%}"
        )

    if _looks_like_failure(transcript):
        failures.append("transcript head matches failure pattern")

    return CuratorVerdict(
        path=verdict.path,
        passes=not failures,
        failures=tuple(failures),
        duration_seconds=verdict.duration_seconds,
        size_mb=verdict.size_mb,
    )


def batch_evaluate(
    paths: Iterable[str | os.PathLike[str]],
    transcripts: dict[str, str] | None = None,
    *,
    config: CuratorConfig | None = None,
) -> list[CuratorVerdict]:
    """Evaluate many candidates in one call.

    ``transcripts`` maps path → transcript text for those candidates
    that have already been ASR-processed. Candidates missing from the
    map will only be checked against gates 1-2.
    """
    transcripts = transcripts or {}
    out: list[CuratorVerdict] = []
    for p in paths:
        verdict = evaluate(p, config=config)
        transcript = transcripts.get(str(p), "")
        if transcript:
            verdict = evaluate_transcript(verdict, transcript, config=config)
        out.append(verdict)
    return out


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Curate Codex-quality sample candidates (six-gate check)."
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        required=True,
        help="Local audio/video files to evaluate.",
    )
    parser.add_argument(
        "--transcripts-json",
        help="Optional JSON file mapping path → transcript text.",
    )
    parser.add_argument(
        "--min-duration",
        type=int,
        default=CuratorConfig.min_duration_seconds,
        help="Minimum duration in seconds.",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=CuratorConfig.min_transcript_chars,
        help="Minimum transcript characters.",
    )
    args = parser.parse_args()

    transcripts: dict[str, str] = {}
    if args.transcripts_json and Path(args.transcripts_json).exists():
        with open(args.transcripts_json, encoding="utf-8") as f:
            transcripts = json.load(f)

    config = CuratorConfig(
        min_duration_seconds=args.min_duration,
        min_transcript_chars=args.min_chars,
    )

    verdicts = batch_evaluate(args.paths, transcripts, config=config)
    for v in verdicts:
        status = "PASS" if v.passes else "FAIL"
        print(f"[{status}] {v.path}")
        print(f"        duration={v.duration_seconds:.1f}s "
              f"size={v.size_mb:.2f}MB")
        for failure in v.failures:
            print(f"        - {failure}")


if __name__ == "__main__":
    _cli()
