"""Tests for the post-run dual-source audit script (Hermes iron rule 135)."""

from __future__ import annotations

import sys
from pathlib import Path

# Make scripts/ importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from post_run_audit import (  # noqa: E402
    _audit_doc,
    _load_fw_sf,
    _normalize,
    _strip_ts,
)

# --- normalization ---

def test_strip_ts_basic():
    assert _strip_ts("[   0.0s -    2.4s]  说起近期的热门科技词汇") == "说起近期的热门科技词汇"


def test_strip_ts_no_timestamp():
    assert _strip_ts("无时间戳的普通文本") == "无时间戳的普通文本"


def test_strip_ts_extra_spaces():
    assert _strip_ts("[ 12.5s -  18.0s]  hello   world  ") == "hello   world"


def test_normalize_whitespace():
    s = "你好\n\n世界\r\n\t 多空格"
    assert _normalize(s) == "你好世界多空格"


def test_normalize_full_width_punct():
    s = "你好，世界：hello（world）"
    assert _normalize(s) == "你好,世界:hello(world)"


def test_normalize_full_width_excl_quest():
    assert _normalize("你好！世界？") == "你好!世界?"


def test_normalize_cjk_brackets():
    assert _normalize("《标题》") == "<标题>"


def test_normalize_chinese_quotes():
    """Full-width ASCII quotes (U+201C/D, U+2018/9) → ASCII."""
    s = "\u201chello\u201d \u2018world\u2019"
    assert _normalize(s) == '"hello"\'world\''


# --- audit_doc (without network) ---
# 用三引号字符串, 包含真实 ```` 块

BACKTICK = chr(96) * 3

SAMPLE_MD_OK = f"""# 测试标题

## 元信息
**标题**: 测试

## 六个核心观点
### 创作者的关键定义与强调
{BACKTICK}
[   0.0s -    5.0s] 第一段原文
[   5.0s -   10.0s] 第二段原文
{BACKTICK}

### 创作者的精彩表述
{BACKTICK}
[  10.0s -   15.0s] 第三段原文
{BACKTICK}

## 完整口播稿原文
### 版本 A：faster-whisper 时间戳分段
{BACKTICK}
[   0.0s -    5.0s] 第一段原文
[   5.0s -   10.0s] 第二段原文
[  10.0s -   15.0s] 第三段原文
{BACKTICK}

### 版本 B：SiliconFlow SenseVoiceSmall 全文
{BACKTICK}
🎼第一段原文 第二段原文 第三段原文
{BACKTICK}
"""

FW_NORM = _normalize("\n".join(["第一段原文", "第二段原文", "第三段原文"]))
SF_NORM = _normalize("🎼第一段原文 第二段原文 第三段原文")


def test_audit_doc_all_match():
    r = _audit_doc("test-doc", SAMPLE_MD_OK, FW_NORM, SF_NORM, "test")
    assert r["status"] == "OK", r
    assert r["total"] >= 6
    assert r["matched"] == r["total"]
    assert r["true_miss"] == []


SAMPLE_MD_MISSING = f"""# 测试

## 六个核心观点
### 创作者的关键定义与强调
{BACKTICK}
[   0.0s -    5.0s] 这段不在 fw_corrected 里
{BACKTICK}
"""


def test_audit_doc_missing_returns_mismatch():
    r = _audit_doc("test", SAMPLE_MD_MISSING, FW_NORM, SF_NORM, "test")
    assert r["status"] == "MISMATCH", r
    assert len(r["true_miss"]) >= 1


def test_audit_doc_empty():
    """Empty markdown - all section totals 0, but coverage vacuously OK."""
    r = _audit_doc("test", "# Only title\n\nNo code blocks.", FW_NORM, SF_NORM, "test")
    assert r["status"] == "OK"
    assert r["total"] == 0


# --- fw/sf loading (filesystem) ---

def test_load_fw_sf_basic(tmp_path: Path):
    work = tmp_path / "_work"
    work.mkdir()
    d = work / "_work_01_TEST_VID"
    d.mkdir()
    (d / "fw_corrected.txt").write_text(
        "[   0.0s -    2.0s]  Line one\n"
        "[   2.0s -    4.0s]  Line two\n"
    )
    (d / "sf_corrected.txt").write_text("🎼Line one Line two")

    fw_map, sf_map = _load_fw_sf(work)
    assert "TEST_VID" in fw_map
    assert "TEST_VID" in sf_map
    assert "Lineone" in fw_map["TEST_VID"]
    assert "Lineone" in sf_map["TEST_VID"]


def test_load_fw_sf_skips_missing(tmp_path: Path):
    work = tmp_path / "_work"
    work.mkdir()
    d = work / "_work_02_VID2"
    d.mkdir()
    # Only fw, no sf
    (d / "fw_corrected.txt").write_text("[   0.0s -    2.0s]  Hello\n")
    fw_map, sf_map = _load_fw_sf(work)
    assert "VID2" in fw_map
    assert "VID2" not in sf_map  # gracefully absent


# --- integration test (offline) ---

def test_audit_real_world_scenario(tmp_path: Path):
    """Simulates Hermes实战: fw + sf have same content, doc has extracts."""
    fw_text = (
        "[   0.0s -    2.4s]  你有没有发现 ChatGPT 等AI聊天助手\n"
        "[   2.4s -    5.2s]  有时候像个天才\n"
    )
    sf_text = "🎼你有没有发现 ChatGPT 等AI聊天助手 有时候像个天才"

    fw_norm = _normalize("\n".join(_strip_ts(ln) for ln in fw_text.splitlines() if ln.startswith("[")))
    sf_norm = _normalize(sf_text)

    doc = f"""## 六个核心观点
### 创作者的关键定义与强调
{BACKTICK}
[   0.0s -    2.4s]  你有没有发现 ChatGPT 等AI聊天助手
[   2.4s -    5.2s]  有时候像个天才
{BACKTICK}

## 版本 A：fw 时间戳分段
{BACKTICK}
[   0.0s -    2.4s]  你有没有发现 ChatGPT 等AI聊天助手
[   2.4s -    5.2s]  有时候像个天才
{BACKTICK}

## 版本 B：SiliconFlow 全文
{BACKTICK}
🎼你有没有发现 ChatGPT 等AI聊天助手 有时候像个天才
{BACKTICK}
"""
    r = _audit_doc("test", doc, fw_norm, sf_norm, "test")
    assert r["status"] == "OK", r
    assert r["coverage"] == 100.0


def test_audit_version_b_uses_sf():
    """Version B block content should match sf, not fw."""
    fw_norm = _normalize("fw content only")  # fw has different content
    sf_norm = _normalize("sf content here")

    doc = f"""## 版本 B：SiliconFlow SenseVoiceSmall 全文
{BACKTICK}
🎼sf content here
{BACKTICK}
"""
    r = _audit_doc("test", doc, fw_norm, sf_norm, "test")
    # version B section matches against sf_norm which has "sfcontenthere"
    # doc has "sfcontenthere" (normalized) → should match
    assert r["status"] == "OK", r
