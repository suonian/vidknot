"""
VidkNot 双 ASR 校正模块

输入：
  - faster-whisper 转录文本（带时间戳分段）
  - SiliconFlow 转录文本（无时间戳）

处理流程：
  1. SequenceMatcher 找出所有差异
  2. mmx search query 搜证疑似专有名词
  3. mmx text chat (MiniMax-M3) 校正

支持版本：
  - v4 (默认): 保守原则——只改搜证确认/明显成语/明显错字
  - v3: 激进版——会改更多但可能引入新错

用法:
    from vidknot.core.corrector import DualASRCorrector

    corrector = DualASRCorrector(version="v4")
    corrected = corrector.correct(
        fw_text=faster_whisper_output,
        sf_text=siliconflow_output,
        video_title="视频标题",
    )
"""

import json
import os
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .transcriber import SiliconFlowASR, FasterWhisperASR
from ..utils.exceptions import CorrectionError, LLMError
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ========== 工具函数 ==========

def _normalize(text: str) -> str:
    """去掉标点/空格/数字/emoji，用于 SequenceMatcher"""
    if not text:
        return ""
    return re.sub(
        r'[\s，。！？；：、""\'\'《》（）()【】\[\]…—\-—,.!?;:\'"<>《》()/\d🎼😊🎵🎶🔔]',
        '',
        text,
    )


def _strip_timestamps(text: str) -> str:
    """去掉 [time - time] 前缀"""
    return re.sub(r'\[\s*\d+\.?\d*s\s*-\s*\d+\.?\d*s\]\s*', '', text)


def _mmx_search(query: str, limit: int = 3) -> str:
    """mmx search query - 返回简洁摘要"""
    try:
        r = subprocess.run(
            ["mmx", "search", "query", "--q", query, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return f"（搜索失败：{r.stderr[:60]}）"
        data = json.loads(r.stdout)
        items = data.get("organic", [])[:limit]
        if not items:
            return "（无结果）"
        return " | ".join(
            f"[{item.get('title', '')[:50]}] {item.get('snippet', '')[:150]}"
            for item in items
        )
    except subprocess.TimeoutExpired:
        return "（搜索超时）"
    except FileNotFoundError:
        return "（mmx CLI 未安装）"
    except Exception as e:
        return f"（异常：{str(e)[:60]}）"


def _mmx_chat(message: str, max_tokens: int = 32000, timeout: int = 600) -> str:
    """mmx text chat - 调用 MiniMax-M3"""
    try:
        r = subprocess.run(
            [
                "mmx", "text", "chat",
                "--model", "MiniMax-M3",
                "--max-tokens", str(max_tokens),
                "--message", message,
                "--output", "json",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode != 0:
            raise LLMError(f"mmx 调用失败: {r.stderr[:200]}")
        data = json.loads(r.stdout)
        return "".join(
            c.get("text", "")
            for c in data.get("content", [])
            if c.get("type") == "text"
        )
    except subprocess.TimeoutExpired:
        raise LLMError("mmx 调用超时")
    except FileNotFoundError:
        raise LLMError("mmx CLI 未安装")
    except Exception as e:
        raise LLMError(f"mmx 调用异常: {str(e)[:200]}")


def _make_diff(fw_text: str, sf_text: str):
    """
    用 SequenceMatcher 找出所有差异
    返回 (diff_lines, fw_norm, sf_norm)
    """
    fw_norm = _normalize(_strip_timestamps(fw_text))
    sf_norm = _normalize(sf_text)
    sm = SequenceMatcher(None, sf_norm, fw_norm)
    opcodes = list(sm.get_opcodes())

    diff_lines = []
    for i, (t, i1, i2, j1, j2) in enumerate(opcodes):
        if t == "equal":
            continue
        sf_s = sf_norm[i1:i2]
        fw_s = fw_norm[j1:j2]
        ctx_start = max(0, min(i1, j1) - 10)
        ctx_end = min(len(sf_norm), max(i2, j2) + 10)
        ctx = sf_norm[ctx_start:ctx_end]
        diff_lines.append(
            f"[{i}] {t}: SF='{sf_s}' ↔ FW='{fw_s}' | ctx: ...{ctx}..."
        )
    return diff_lines, fw_norm, sf_norm


def _extract_corrected_transcript(llm_output: str) -> str:
    """从 LLM 输出里抽取 ===CORRECTED=== 块"""
    m = re.search(r"===CORRECTED===(.*?)===END===", llm_output, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Fallback: 找最长的连续时间戳段
    lines = llm_output.split("\n")
    ts_lines = [
        i
        for i, l in enumerate(lines)
        if re.match(r"^\s*\[\s*\d+\.\d+s\s*-\s*\d+\.\d+s\]", l)
    ]
    if not ts_lines:
        return llm_output
    gaps = [(i, ts_lines[i] - ts_lines[i - 1]) for i in range(1, len(ts_lines))]
    gaps.sort(key=lambda x: -x[1])
    start_line = ts_lines[gaps[0][0]]
    return "\n".join(lines[start_line:]).strip()


# ========== 校正器 ==========

class DualASRCorrector:
    """
    双 ASR 校正器

    输入 faster-whisper + SiliconFlow 两份转录，
    输出经 mmx search 搜证、mmx LLM 校正后的完整文本。
    """

    PROMPT_V4 = """你是中文 ASR 错别字校正专家，**采用保守原则**。

## 关键约束

### 1. 保守原则（最高优先级）

**只有满足以下条件之一才修改 faster-whisper 原文：**
- ✅ **搜证确认**：下面"搜证结果"里明确显示某专有名词是 XX
- ✅ **明显成语/固定表达**：如 "遗老遗少"、"物以群分"、"劣币驱逐良币"、"逐鹿中原"
- ✅ **明显错字**：识别结果完全无语义（如 "瞞"→"瞒"、"心脏"→"新浪"）

**其他情况一律保留 faster-whisper 原词，不要修改：**
- ❌ 语气词差异（呢/啊/哎/那么/就是）：**不修改**
- ❌ 同义/近义词选择：**不修改**
- ❌ 单字替换但搜不到证据：**不修改**

### 2. 主动采用搜证结果
- 下面"搜证结果"是 mmx search 已执行的真实结果
- 搜证到的，果断采用；搜证不到的，保留 FW 原词

### 3. 完整保留所有时间戳段
- faster-whisper 转录的所有段都必须保留（从 [0.0s] 到结尾）
- 输出第一段必须从 [0.0s] 开始
- 时间戳格式严格按 `[  X.Xs -  Y.Ys]`（两位小数、对齐空格）
- 每段只能有一句话

## 视频信息
- 标题：{title}

## 搜证结果（mmx search 已执行）
{search_summary}

## Diff 清单（{n_diffs} 条）
{diff_text}

## faster-whisper 完整转录（带时间戳）
{fw_text}

## SiliconFlow 完整转录（无时间戳）
{sf_text}

## 输出格式

先输出"逐条校正决定表"（Markdown 表格，**只列实际修改的项**），然后输出：

```
===CORRECTED===
[  0.0s -    3.4s] （校正后的第一段）
... （共 N 段，全部保留）
===END===
```

开始校正。"""

    PROMPT_V3 = """你是中文 ASR 错别字校正专家。

## 关键约束

### 1. 完整保留所有时间戳段
- faster-whisper 转录的所有段都必须保留
- 时间戳格式：`[  X.Xs -  Y.Ys]`
- 每段只能有一句话

### 2. 整段语义还原
- ASR 两边都识别错的整段要还原（如 "瞞了整整8年" 是 "瞒了整整8年"）
- FW/SF 都有连续错误（如 "原始股闷"）要还原成完整正确短语

### 3. 成语/固定表达识别
- "遗老遗少"、"物以群分"、"劣币驱逐良币"、"逐鹿中原" 等

### 4. 主动采用搜证结果
- 下面"搜证结果"是 mmx search 已执行的真实结果
- 搜证到的果断采用；搜证不到的保留 FW 原词

## 视频信息
- 标题：{title}

## 搜证结果（mmx search 已执行）
{search_summary}

## Diff 清单（{n_diffs} 条）
{diff_text}

## faster-whisper 完整转录（带时间戳）
{fw_text}

## SiliconFlow 完整转录（无时间戳）
{sf_text}

## 输出格式

先输出"逐条校正决定表"，然后输出：

```
===CORRECTED===
[  0.0s -    3.4s] （第一段）
... （全部段）
===END===
```

开始校正。"""

    def __init__(self, version: str = "v4"):
        if version not in ("v3", "v4"):
            raise CorrectionError(f"未知 version: {version}（仅支持 v3/v4）")
        self.version = version

    def correct(
        self,
        fw_text: str,
        sf_text: str,
        video_title: str,
        max_searches: int = 15,
    ) -> dict:
        """
        执行双 ASR 校正

        Args:
            fw_text: faster-whisper 转录（带时间戳）
            sf_text: SiliconFlow 转录（无时间戳）
            video_title: 视频标题
            max_searches: 最大搜证项数

        Returns:
            {
                "corrected_text": "校正后的完整转录",
                "search_evidence": {...},
                "diff_count": int,
                "decision_table": "...",
                "llm_raw_output": "...",
            }
        """
        # Step 1: diff
        logger.info(f"[Corrector] v{self.version[-1]} 模式：开始双 ASR diff")
        diff_lines, fw_norm, sf_norm = _make_diff(fw_text, sf_text)
        n_diffs = len(diff_lines)
        logger.info(f"[Corrector] 找到 {n_diffs} 处差异")

        if n_diffs == 0:
            logger.info("[Corrector] 两份转录完全一致，无需校正")
            return {
                "corrected_text": fw_text,
                "search_evidence": {},
                "diff_count": 0,
                "decision_table": "",
                "llm_raw_output": "",
            }

        # Step 2: 让 LLM 识别需要搜证的关键项
        logger.info("[Corrector] 让 LLM 识别搜证项...")
        evidence_prompt = (
            f"你是中文 ASR 错别字校正专家。从以下 diff 清单（{n_diffs} 条）中"
            f"识别需要搜证的关键专有名词（公司名/产品名/人名/英文术语），只输出搜证清单：\n\n"
            f"视频标题：{video_title}\n\n"
            f"Diff 清单（前 100 条）：\n"
            + "\n".join(diff_lines[:100])
            + "\n\n输出格式：\n"
            "1. 搜证 [关键词] - [为什么需要搜证]\n"
            "2. 搜证 ...\n"
            f"（最多 {max_searches} 条）"
        )
        evidence_output = _mmx_chat(evidence_prompt, max_tokens=4000, timeout=120)

        # 解析搜证项
        searches = []
        for line in evidence_output.split("\n"):
            m = re.match(r"^\s*\d+[\.、]\s*(?:搜证|搜索)?\s*(.+?)\s*[-—]\s*(.+)", line)
            if m and len(searches) < max_searches:
                searches.append((m.group(1).strip(), m.group(2).strip()))

        logger.info(f"[Corrector] 识别出 {len(searches)} 个搜证项")

        # Step 3: 执行搜证
        search_results = {}
        for query, label in searches:
            logger.info(f"[Corrector] 🔍 搜证: {query[:50]}")
            search_results[label] = _mmx_search(query)

        search_summary = "\n".join(
            f"### {k}\n{v}\n" for k, v in search_results.items()
        )

        # Step 4: 校正
        prompt_template = self.PROMPT_V4 if self.version == "v4" else self.PROMPT_V3
        prompt = prompt_template.format(
            title=video_title,
            search_summary=search_summary,
            n_diffs=n_diffs,
            diff_text="\n".join(diff_lines[:100]),
            fw_text=fw_text,
            sf_text=sf_text,
        )

        logger.info(f"[Corrector] 调用 mmx LLM 校正（{self.version}）...")
        llm_output = _mmx_chat(prompt, max_tokens=32000, timeout=600)

        # 抽取校正结果
        corrected_text = _extract_corrected_transcript(llm_output)

        # 抽取校正决定表（从 ===CORRECTED=== 之前的内容）
        decision_table_match = re.search(
            r"(.+?)(?====CORRECTED===|\Z)", llm_output, re.DOTALL
        )
        decision_table = (
            decision_table_match.group(1).strip() if decision_table_match else ""
        )

        n_segments = len(
            [l for l in corrected_text.split("\n") if re.match(r"^\s*\[\s*\d+\.\d+s", l)]
        )
        logger.info(
            f"[Corrector] ✅ 校正完成：{len(corrected_text)} 字符, {n_segments} 段"
        )

        return {
            "corrected_text": corrected_text,
            "search_evidence": search_results,
            "diff_count": n_diffs,
            "decision_table": decision_table,
            "llm_raw_output": llm_output,
            "n_segments": n_segments,
        }


def run_correction_pipeline(
    audio_path: str,
    video_title: str = "",
    version: str = "v4",
) -> dict:
    """
    一站式：跑双 ASR + 校正

    Args:
        audio_path: 音频文件路径
        video_title: 视频标题
        version: 校正版本（v3/v4）

    Returns:
        DualASRCorrector.correct() 的结果，并额外带 fw_text / sf_text
    """
    logger.info(f"[Pipeline] 开始双 ASR + 校正流程: {audio_path}")

    # 双 ASR
    fw = FasterWhisperASR()
    sf = SiliconFlowASR()

    fw_text = fw.transcribe(audio_path)
    sf_text = sf.transcribe(audio_path)

    # 校正
    corrector = DualASRCorrector(version=version)
    result = corrector.correct(fw_text, sf_text, video_title)
    result["fw_text"] = fw_text
    result["sf_text"] = sf_text
    result["version"] = version
    return result