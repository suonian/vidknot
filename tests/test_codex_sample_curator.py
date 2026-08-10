"""Tests for the Codex sample curator (six-gate check)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.codex_sample_curator import (
    CuratorConfig,
    CuratorVerdict,
    batch_evaluate,
    evaluate,
    evaluate_transcript,
    ffprobe_duration,
)


# 满足全部 6 关的假转录（>= 1500 字符 + 关键词匹配 + 非失败模式）
GOOD_TRANSCRIPT = (
    "这是一段关于AI Agent多智能体实战的口播内容。"
    "今天我们要讨论如何用图来编排多agent任务。"
    + "YAML Handoff Tester QualifyGate 这些英文术语贯穿全文。" * 60
)


# 命中关键词（_derive_keywords_from_path 会从文件名提取）
GOOD_PATH = "/tmp/test_douyin_Agent_yaml_Handoff_实战_video.mp4"


def test_ffprobe_duration_handles_missing_file(tmp_path: Path):
    assert ffprobe_duration(tmp_path / "missing.mp4") == 0.0


def test_evaluate_passes_minimum(tmp_path: Path):
    # 创建 ≥180s + ≥1MB 的假文件
    f = tmp_path / "test_douyin_Agent_yaml_video.mp4"
    f.write_bytes(b"x" * (2 * 1024 * 1024))
    # 改 mtime/时长 → 用真文件做 ffprobe 测试
    # 这里用 monkeypatch
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.codex_sample_curator.ffprobe_duration",
            lambda p: 200.0,
        )
        verdict = evaluate(f)
    assert verdict.passes
    assert verdict.failures == ()


def test_evaluate_fails_short_duration(tmp_path: Path):
    f = tmp_path / "test_douyin_Agent_video.mp4"
    f.write_bytes(b"x" * (2 * 1024 * 1024))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.codex_sample_curator.ffprobe_duration",
            lambda p: 60.0,
        )
        verdict = evaluate(f)
    assert not verdict.passes
    assert any("duration" in f for f in verdict.failures)


def test_evaluate_fails_small_size(tmp_path: Path):
    f = tmp_path / "test_douyin_Agent_video.mp4"
    f.write_bytes(b"x" * 1024)  # 1KB
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.codex_sample_curator.ffprobe_duration",
            lambda p: 200.0,
        )
        verdict = evaluate(f)
    assert not verdict.passes
    assert any("size" in f for f in verdict.failures)


def test_evaluate_transcript_passes_good_input(tmp_path: Path):
    f = tmp_path / "test_douyin_Agent_yaml_Handoff_实战_video.mp4"
    f.write_bytes(b"x" * (2 * 1024 * 1024))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.codex_sample_curator.ffprobe_duration",
            lambda p: 200.0,
        )
        verdict = evaluate(f)
        verdict = evaluate_transcript(verdict, GOOD_TRANSCRIPT)
    assert verdict.passes, verdict.failures


def test_evaluate_transcript_fails_short(tmp_path):
    f = Path("/tmp/x.mp4")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.codex_sample_curator.ffprobe_duration",
            lambda p: 200.0,
        )
        verdict = evaluate(f)
        verdict = evaluate_transcript(verdict, "only " * 50)  # 300 chars
    assert not verdict.passes
    assert any("transcript" in f for f in verdict.failures)


def test_evaluate_transcript_detects_failure_pattern():
    verdict = CuratorVerdict(
        path="/tmp/x.mp4",
        passes=True,
        failures=(),
        duration_seconds=300.0,
        size_mb=2.0,
    )
    bad = "🎼🎼🎼🎼🎼" * 200  # 1000 chars but pure emoji spam
    verdict = evaluate_transcript(verdict, bad)
    assert not verdict.passes


def test_evaluate_transcript_detects_keyword_mismatch():
    verdict = CuratorVerdict(
        path="/tmp/test_douyin_Claude_Code_CoT_Workflow_video.mp4",
        passes=True,
        failures=(),
        duration_seconds=300.0,
        size_mb=2.0,
    )
    # 长度达标但完全无关内容
    irrelevant = "今天讲炒菜放盐糖醋酱油什么时候放，按个人口味来调整。" * 60
    verdict = evaluate_transcript(verdict, irrelevant)
    assert not verdict.passes
    assert any("keyword" in f for f in verdict.failures)


def test_batch_evaluate_handles_missing_transcripts(tmp_path: Path):
    f = tmp_path / "test_douyin_Agent_video.mp4"
    f.write_bytes(b"x" * (2 * 1024 * 1024))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "scripts.codex_sample_curator.ffprobe_duration",
            lambda p: 200.0,
        )
        verdicts = batch_evaluate([f])
    # 没有 transcript 时只跑 gate 1-2
    assert len(verdicts) == 1
    assert verdicts[0].passes


def test_keyword_extraction_skips_generic_tokens():
    from scripts.codex_sample_curator import _derive_keywords_from_path

    keywords = _derive_keywords_from_path(
        "/tmp/douyin_木子不写代码_Claude_Code_零基础终极教程_video.mp4"
    )
    assert "douyin" not in keywords
    assert "video" not in keywords
    assert "木子" in keywords or "不写代码" in keywords or "Claude" in keywords


def test_curator_config_defaults():
    cfg = CuratorConfig()
    assert cfg.min_duration_seconds == 180
    assert cfg.min_transcript_chars == 1500
    assert cfg.keyword_match_ratio == 0.5