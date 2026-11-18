"""
VidkNot 素材包（Agent 两段式契约 · 第一段）

设计意图
--------
VidkNot 作为 Agent 技能被使用时，**搜证与校正不必由 VidkNot 内部调用某个
厂商的 LLM**——宿主智能体（Claude Code / MiniMax Code / Cursor / Cline …）
本身就带着模型和搜索工具。

因此本模块提供「素材包」：只做**确定性的部分**（下载、ASR、双 ASR diff、
待搜证词提取），**不调用任何 LLM、不发起任何联网搜索**。宿主智能体拿到
素材包后，用自己的搜索工具搜证、用自己的模型校正并成文，再通过
`save_note` 把成稿落库。

素材包结构（schema: vidknot.material/1）::

    {
      "schema": "vidknot.material/1",
      "title": "...",
      "author": "...",
      "duration": 19,
      "source_url": "...",
      "source_platform": "YouTube",
      "transcription": "SiliconFlow 完整转写（无时间戳）",
      "fw_segments": "[00:00.0 - 00:07.2] faster-whisper 时间戳段",
      "diff_count": 8,
      "diffs": ["[0] replace: SF='...' ↔ FW='...' | ctx: ..."],
      "search_candidates": ["ByteDance", "字节跳动"],
      "notes": "..."
    }

与「一键成稿」模式并存：需要服务端直接出成品笔记时，仍用
`video_knowledge` / `batch_process`（走可配置的 LLM provider）。

待搜证词的提取规则
------------------
从**原文**（而非去标点的归一化文本）上比较两份转写，逐处差异扩展成
「值得搜证的词」：

- **拉丁词**：含大写字母或数字（``ByteDance`` / ``iPhone`` / ``GPT-4`` /
  ``2024``）—— 这类是 ASR 最容易误识别的专有名词与型号；
- **中文**：差异位置前后 2-4 个汉字的词块（``字节跳动`` / ``人工智能``）。

普通英文虚词、整段乱码、纯标点一律过滤掉——搜它们没有意义，
只会把宿主智能体带偏。
"""

import re
from difflib import SequenceMatcher
from typing import Any

from ..utils.logger import get_logger

logger = get_logger(__name__)

SCHEMA = "vidknot.material/1"

# faster-whisper 时间戳前缀，如 "[  0.2s -    7.2s] " / "[00:00.0 - 00:07.2] "
_TIMESTAMP_RE = re.compile(
    r"\[\s*\d{1,2}:\d{2}(?:\.\d+)?\s*-\s*\d{1,2}:\d{2}(?:\.\d+)?\s*\]\s*"
    r"|\[\s*\d+(?:\.\d+)?s\s*-\s*\d+(?:\.\d+)?s\s*\]\s*"
)

# 拉丁词（含内部连字符/点，如 GPT-4、U.S.）
_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.+_-]*")

# 单个汉字
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

# 噪声：纯标点、语气词等
_NOISE_FRAGMENTS = {
    "", "。", "，", "、", "？", "！", "…", "～", "-", "—",
    "嗯", "啊", "哦", "呃", "唉", "这个", "那个", "什么",
}

# 英文里「句首大写」的常见词 —— 它们有大写字母但不是专有名词，
# 搜它们没有价值，只会把宿主智能体带偏。
_COMMON_CAPS = {
    "a", "all", "an", "and", "are", "as", "at", "be", "because", "been",
    "before", "but", "by", "can", "could", "did", "do", "does", "even",
    "for", "from", "had", "has", "have", "he", "her", "here", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "just", "like", "may",
    "might", "must", "my", "no", "not", "now", "of", "oh", "ok", "okay",
    "on", "one", "only", "or", "our", "out", "over", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "to", "too", "up", "very", "was", "we",
    "well", "were", "what", "when", "where", "which", "while", "who", "why",
    "will", "with", "would", "yeah", "yes", "you", "your",
}


def _strip_timestamps(text: str) -> str:
    """去掉 faster-whisper 的时间戳前缀（保留正文）。"""
    return _TIMESTAMP_RE.sub("", text or "")


def _is_cjk(ch: str) -> bool:
    """是否单个汉字。"""
    return bool(ch) and bool(_CJK_RE.match(ch))


def _expand_to_words(text: str, start: int, end: int) -> list[str]:
    """把差异区间 ``[start, end)`` 扩展成可搜证的词。

    Args:
        text: 原文
        start: 差异起始下标
        end: 差异结束下标

    Returns:
        候选词列表（拉丁词 + 中文词块）
    """
    if not text:
        return []
    start = max(0, min(start, len(text)))
    end = max(start, min(end, len(text)))
    if start == end:
        # 单点替换：把相邻一个字符纳入区间
        start = max(0, start - 1)
        end = min(len(text), end + 1)

    out: list[str] = []

    # 拉丁词：取与差异区间相交的完整词（去掉首尾标点）
    for m in _LATIN_WORD_RE.finditer(text):
        if m.start() < end and m.end() > start:
            word = m.group(0).strip(".'’,+-")
            if word:
                out.append(word)

    # 中文：以差异位置为中心取连续汉字窗口（最多 4 字）
    lo = start
    hi = end
    while lo > 0 and _is_cjk(text[lo - 1]):
        lo -= 1
    while hi < len(text) and _is_cjk(text[hi]):
        hi += 1
    if hi > lo:
        # 以**差异位置**为中心取汉字窗口（最多 4 字），而不是整段汉字的中心
        center = (start + end) // 2
        center = max(lo, min(center, hi - 1))
        w_lo = max(lo, center - 2)
        w_hi = min(hi, w_lo + 4)
        w_lo = max(lo, w_hi - 4)
        chunk = text[w_lo:w_hi].strip()
        # 必须真的含汉字，否则这段只是标点/空格碎片，不该成为候选
        if len(chunk) >= 2 and any(_is_cjk(c) for c in chunk):
            out.append(chunk)

    return out


def _is_searchable(word: str) -> bool:
    """判断一个词是否「值得搜证」。

    - 拉丁词：必须含大写字母或数字（专有名词 / 型号 / 年份）；
    - 中文：2-6 个汉字的词块。
    """
    if not word:
        return False
    if len(word) > 40:
        return False
    if word in _NOISE_FRAGMENTS:
        return False
    if _is_cjk(word[0]):
        return 2 <= len(word) <= 6
    # 拉丁 / 数字：像专有名词才值得搜
    if len(word) < 2:
        return False
    has_upper = any(c.isupper() for c in word)
    has_digit = any(c.isdigit() for c in word)
    has_alpha = any(c.isalpha() for c in word)
    if has_upper:
        # 句首大写的常见词不是专有名词
        return word.lower() not in _COMMON_CAPS
    if has_digit and has_alpha:
        return True                       # gpt-4 / 4k / H264
    if word.isdigit():
        return len(word) >= 4             # 2024 / 1999 有意义，单个数字没有
    return False


def extract_search_candidates(
    sf_text: str,
    fw_text: str = "",
    limit: int = 12,
) -> list[str]:
    """从两份转写的差异里提取待搜证词候选（纯算法，不调 LLM）。

    Args:
        sf_text: 主转写原文
        fw_text: 对照转写原文（可为空；为空时退化为「全文专有名词」）
        limit: 最多返回多少个候选

    Returns:
        去重后的候选词列表（保持出现顺序）
    """
    sf_text = (sf_text or "").strip()
    fw_text = _strip_timestamps(fw_text or "").strip()

    if not sf_text:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        value = value.strip()
        if not _is_searchable(value):
            return
        key = value.lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(value)

    if not fw_text:
        # 没有对照转写：退化为「全文里的专有名词」
        for m in _LATIN_WORD_RE.finditer(sf_text):
            _add(m.group(0))
        return candidates[:limit]

    sm = SequenceMatcher(None, sf_text, fw_text)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        # SF 侧与 FW 侧都可能是错的，两侧都纳入
        for word in _expand_to_words(sf_text, i1, i2):
            _add(word)
        for word in _expand_to_words(fw_text, j1, j2):
            _add(word)

    return candidates[:limit]


def build_material_bundle(
    *,
    url: str,
    metadata: dict[str, Any],
    transcription: str,
    fw_segments: str = "",
    diff_lines: list[str] | None = None,
    search_candidates: list[str] | None = None,
    max_candidates: int = 12,
    diff_status: str = "skipped",
    diff_reason: str = "",
) -> dict[str, Any]:
    """组装素材包（不调用任何 LLM / 搜索）。

    Args:
        url: 视频链接
        metadata: 下载阶段拿到的元信息（title/uploader/duration/platform…）
        transcription: 主转录文本（SiliconFlow 或平台字幕）
        fw_segments: faster-whisper 时间戳段（可为空）
        diff_lines: 双 ASR 差异清单（可为空）
        search_candidates: 显式指定候选词；留空则从两份转写的差异里提取
        max_candidates: 候选词上限
        diff_status: 对照转写状态 —— ok(完成) / failed(失败) / skipped(未执行)
        diff_reason: 对照转写的说明或失败原因

    Returns:
        素材包字典
    """
    diff_lines = diff_lines or []
    if search_candidates is None:
        search_candidates = extract_search_candidates(
            transcription, fw_segments, limit=max_candidates
        )

    duration = metadata.get("duration", 0)
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 0

    bundle = {
        "schema": SCHEMA,
        "title": metadata.get("title", "未知标题"),
        "author": metadata.get("uploader", "未知作者"),
        "duration": duration,
        "source_url": url,
        "source_platform": metadata.get("platform", "unknown"),
        "transcription": transcription or "",
        "fw_segments": fw_segments or "",
        "diff_count": len(diff_lines),
        "diffs": diff_lines,
        "diff_status": diff_status,
        "diff_reason": diff_reason,
        "search_candidates": search_candidates,
        "notes": (
            "本素材包只含确定性产物（下载 / ASR / 双 ASR diff / 待搜证词），"
            "不含任何 LLM 调用结果与联网搜索结果。"
            "diff_status 标明对照转写状态：ok=已完成（此时 diff_count=0 表示"
            "两份转写确实一致）、failed=对照失败（无法判断是否存在差异）、"
            "skipped=未执行对照。"
            "请用你自己的搜索工具对 search_candidates 搜证，"
            "并用你自己的模型完成纠错与结构化成稿；"
            "成稿写好后调用 save_note 落库。"
        ),
    }
    logger.info(
        f"[Material] 素材包就绪: {bundle['title']} "
        f"(diff={bundle['diff_count']}, 候选词={len(search_candidates)})"
    )
    return bundle
