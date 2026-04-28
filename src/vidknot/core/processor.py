"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot 内容处理模块

调用 LLM 生成结构化 Markdown 笔记
支持: OpenAI / ZhipuAI / 兼容 OpenAI 格式的 API
"""

import os
from datetime import date
from typing import Dict, Any, Optional

from ..utils.config_manager import ConfigManager
from ..utils.exceptions import LLMError, LLMAPIError, LLMTimeoutError, NoAPIKeyError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ContentProcessor:
    """
    LLM 内容处理器

    将转录文本转换为结构化 Markdown 笔记
    支持多 LLM 提供商（适配器模式）
    """

    SYSTEM_PROMPT = """你是一个专业的视频笔记助手。你需要完成两个任务：

【任务一：校验和修正转录】
1. 检查转录内容是否完整、有无明显错误或遗漏
2. 修正ASR识别错误（如谐音字、多音字错误）
3. 补全被截断的句子
4. 如果有重大问题，在结尾用【转录质量问题】标注

【任务二：生成结构化笔记】
根据修正后的转录内容，生成详细、结构化的 Markdown 笔记。

要求：
1. 完整保留原文重要细节，不要遗漏信息
2. 准确提取：作者/UP主、主题、关键人物/事件/概念
3. 生成有意义的标签（5-10个）
4. 笔记要详尽，覆盖所有重要内容
5. 输出纯 Markdown 格式

输出格式：
```markdown
---
title: [视频标题]
author: [作者/UP主名称]
source: [视频原始链接]
platform: [平台名称: YouTube/B站/抖音等]
duration: [视频时长]
date: [处理日期]
tags: [标签列表，用逗号分隔]
topics: [核心主题列表]
summary: [一句话总结视频内容]
---

# [视频标题]

## 核心信息

- **作者/UP主**: [作者名称]
- **发布时间**: [如有则填，无则写"未标注"]
- **视频时长**: [时长]
- **核心主题**: [主要讨论的话题]

## 关键要点

1. [要点1]
2. [要点2]
3. [要点3]
...（根据内容适当增减）

## 详细内容

[按视频逻辑顺序，详细展开各个主题/章节]
- 子要点1
- 子要点2
...

## 重要引用/金句

[视频中值得记录的重要观点、原话、数据等]

## 专业术语/概念解释

[视频中出现的专业术语及解释]

## 相关资源

[视频中提到的工具、网址、书籍等]

## 完整转录（已修正）

[完整保留修正后的原始转录内容，不要删减]

【转录质量问题】（如有）
[描述转录中的问题]
```
"""

    SIMPLE_PROMPT = """请将以下视频转录内容整理为简洁的 Markdown 笔记格式：

{transcription}

请直接输出 Markdown，不要有其他说明。"""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None,
                 max_tokens: Optional[int] = None):
        """
        初始化处理器

        Args:
            provider: LLM 提供商 (openai/zhipuai/openai-compatible)
            model: 模型名称
            max_tokens: LLM 最大输出 token 数（None=从配置/环境变量读取，默认 4000）
        """
        self.provider = provider or self._load_default_provider()
        self.model = model or self._load_default_model()
        self._max_tokens = self._resolve_max_tokens(max_tokens)
        self._client = None

    def _resolve_max_tokens(self, explicit: Optional[int]) -> int:
        """从优先级: explicit > env > config > 默认值 解析 max_tokens"""
        if explicit is not None:
            return explicit
        env_val = os.getenv("VIDKNOT_MAX_TOKENS")
        if env_val:
            try:
                return int(env_val)
            except ValueError:
                logger.warning(f"VIDKNOT_MAX_TOKENS 值无效: {env_val}，使用默认值 4000")
        config_val = ConfigManager().get("providers", self.provider, "max_tokens")
        if config_val:
            try:
                return int(config_val)
            except ValueError:
                logger.warning(f"配置 max_tokens 无效: {config_val}，使用默认值 4000")
        return 4000

    def _load_default_provider(self) -> str:
        """从配置加载默认提供商"""
        config = ConfigManager()
        provider = config.get("providers", "default_provider")
        if provider:
            return provider
        return os.getenv("VIDKNOT_LLM_PROVIDER", "openai")

    def _load_default_model(self) -> str:
        """从配置加载默认模型"""
        config = ConfigManager()
        model = config.get("providers", self.provider, "model")
        if model:
            return model
        return os.getenv("VIDKNOT_LLM_MODEL", "gpt-4o")

    def _get_client(self):
        """获取 LLM 客户端（优先从 ConfigManager 读取，fallback 到环境变量）"""
        if self._client is None:
            config = ConfigManager()
            provider_config = config.get_provider(self.provider) or {}

            if self.provider == "openai":
                from openai import OpenAI
                api_key = (provider_config.get("api_key") or os.getenv("OPENAI_API_KEY", "")).strip()
                base_url = (provider_config.get("base_url") or os.getenv("OPENAI_BASE_URL", "")).strip() or "https://api.openai.com/v1"
                if not api_key:
                    raise NoAPIKeyError("OpenAI API Key 未设置，请配置 OPENAI_API_KEY 或 providers.openai.api_key")
                self._client = OpenAI(api_key=api_key, base_url=base_url)

            elif self.provider == "zhipuai":
                from zhipuai import ZhipuAI
                api_key = (provider_config.get("api_key") or os.getenv("ZHIPUAI_API_KEY", "")).strip()
                if not api_key:
                    raise NoAPIKeyError("智谱 AI API Key 未设置，请配置 ZHIPUAI_API_KEY 或 providers.zhipuai.api_key")
                self._client = ZhipuAI(api_key=api_key)

            elif self.provider == "openai-compatible":
                from openai import OpenAI
                api_key = (provider_config.get("api_key") or os.getenv("LLM_API_KEY", "")).strip()
                base_url = (provider_config.get("base_url") or os.getenv("LLM_BASE_URL", "")).strip()
                if not api_key:
                    raise NoAPIKeyError(
                        "OpenAI-compatible API Key 未设置，请配置 providers.openai-compatible 或 LLM_API_KEY"
                    )
                self._client = OpenAI(api_key=api_key, base_url=base_url or None)

            else:
                raise LLMError(f"不支持的 LLM 提供商: {self.provider}")

        return self._client

    def summarize(
        self,
        transcription: str,
        metadata: Dict[str, Any],
        max_transcription_length: int = 8000,
    ) -> Dict[str, Any]:
        """
        生成结构化笔记（同步）

        Args:
            transcription: 转录文本
            metadata: 视频元数据
            max_transcription_length: 最大输入长度（防止超出上下文）

        Returns:
            {"markdown": str, "transcription": str}
        """
        # 截断过长转录
        if len(transcription) > max_transcription_length:
            transcription = transcription[:max_transcription_length] + "\n[内容已截断...]"

        # 构建 user prompt
        user_prompt = self._build_prompt(transcription, metadata)

        # 调用 LLM（同步）
        markdown = self._call_llm(user_prompt)

        return {
            "markdown": markdown,
            "transcription": transcription,
        }

    def _build_prompt(self, transcription: str, metadata: Dict[str, Any]) -> str:
        """构建 prompt"""
        prompt = self.SYSTEM_PROMPT

        title = metadata.get("title", "未知标题")
        uploader = metadata.get("uploader", "未知作者")
        url = metadata.get("url", metadata.get("source_url", ""))
        duration = metadata.get("duration", 0)
        platform = metadata.get("platform", "unknown")

        platform_map = {
            "youtube": "YouTube",
            "bilibili": "B站",
            "douyin": "抖音",
            "tiktok": "TikTok",
            "xiaohongshu": "小红书",
            "twitter": "Twitter/X",
            "instagram": "Instagram",
            "vimeo": "Vimeo",
            "unknown": "未知平台",
        }
        platform_display = platform_map.get(platform, platform)

        if duration:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            duration_str = "未知"

        today = date.today().isoformat()

        prompt = prompt.replace("[视频标题]", title)
        prompt = prompt.replace("[作者/UP主名称]", uploader)
        prompt = prompt.replace("[作者/UP主]", uploader)
        prompt = prompt.replace("[视频原始链接]", url)
        prompt = prompt.replace("[视频链接]", url)
        prompt = prompt.replace("[视频时长]", duration_str)
        prompt = prompt.replace("[时长，格式 HH:MM:SS]", duration_str)
        prompt = prompt.replace("[处理日期]", today)
        prompt = prompt.replace("[当前日期]", today)
        prompt = prompt.replace("[平台名称: YouTube/B站/抖音等]", platform_display)

        prompt += f"\n\n## 视频转录内容\n\n{transcription}"

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM（同步）"""
        client = self._get_client()

        try:
            if self.provider in ("openai", "openai-compatible"):
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=self._max_tokens,
                )
                return response.choices[0].message.content

            elif self.provider == "zhipuai":
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=self._max_tokens,
                )
                return response.choices[0].message.content

            else:
                raise LLMError(f"不支持的 LLM 提供商: {self.provider}")

        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"LLM 调用失败: {e}", details=f"provider={self.provider}, model={self.model}")


# -----------------------------------------------------------------------------
# VidkNot - Video Knowledge, Knotted.
# -----------------------------------------------------------------------------
# Copyright (c) 2026 VidkNot Team
# 
# This software is licensed under the MIT License.
# See LICENSE file in the project root for details.
# 
# Repository: https://github.com/suonian/vidknot
# -----------------------------------------------------------------------------

