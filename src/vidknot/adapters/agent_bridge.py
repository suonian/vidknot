"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot Agent 桥接模块

提供 OpenAI Function Calling Schema 定义
用于 OpenAI / Claude 等 AI Agent 集成
"""

import asyncio
import json
from typing import Dict, Any, Optional


def get_tool_metadata() -> Dict[str, Any]:
    """
    获取 VidkNot 工具的 OpenAI Function Calling Schema

    Returns:
        OpenAI tool schema dict
    """
    return {
        "type": "function",
        "function": {
            "name": "video_knowledge",
            "description": """将视频链接转换为结构化笔记，并自动保存到飞书文档或 Obsidian Vault。

适用于以下场景：
- 用户转发视频链接后，AI Agent 自动生成学习笔记
- 将视频内容整理为可搜索的 Markdown 笔记
- 自动提取视频要点、章节、关键信息

支持的平台：YouTube、Bilibili、抖音、小红书、微博、Twitter/X 等 20+ 平台

输出：结构化的 Markdown 笔记，包含 YAML Frontmatter（标题、作者、时长、标签等）""",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "视频链接，支持 YouTube、Bilibili、抖音、小红书、微博、Twitter/X 等平台"
                    },
                    "destination": {
                        "type": "string",
                        "enum": ["feishu", "obsidian", "both", "none"],
                        "description": "笔记保存目的地：feishu=飞书云文档，obsidian=本地 Obsidian Vault，both=两者同时，none=仅返回内容",
                        "default": "obsidian"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["structured", "raw"],
                        "description": "structured=结构化笔记（含要点、详细内容、标签），raw=仅原始转录",
                        "default": "structured"
                    },
                    "language": {
                        "type": "string",
                        "description": "视频语言：auto（自动检测）/ zh / en / ja / ko",
                        "default": "auto"
                    },
                    "feishu_folder": {
                        "type": "string",
                        "description": "飞书文档保存的文件夹名称（如：视频笔记、学习资料）"
                    },
                    "obsidian_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Obsidian 笔记标签（自动添加到 YAML Frontmatter 的 tags 字段）"
                    },
                    "notify": {
                        "type": "boolean",
                        "description": "处理完成后是否发送通知（通过 Agent 消息回复用户）",
                        "default": True
                    }
                },
                "required": ["url"]
            }
        }
    }


def execute_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行 video_knowledge 工具

    Args:
        arguments: 工具参数

    Returns:
        工具执行结果
    """
    from ..pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

    url = arguments.get("url")
    destination = arguments.get("destination", "obsidian")
    format_mode = arguments.get("format", "structured")
    language = arguments.get("language", "auto")
    feishu_folder = arguments.get("feishu_folder")
    obsidian_tags = arguments.get("obsidian_tags", [])
    notify = arguments.get("notify", True)

    if not url:
        return {
            "success": False,
            "error": "URL is required"
        }

    try:
        pipeline = VideoKnowledgePipeline(
            destination=destination,
            format=format_mode,
            language=language,
        )

        result = asyncio.run(pipeline.run(url))

        if destination != "none":
            saved = asyncio.run(
                pipeline.save(result, {
                    "feishu_folder": feishu_folder,
                    "obsidian_tags": obsidian_tags,
                })
            )
            result["saved_to"] = saved

        if notify:
            dest_label = {
                "feishu": "飞书文档",
                "obsidian": "Obsidian Vault",
                "both": "飞书文档和 Obsidian",
            }.get(destination, destination)
            result["notify_message"] = f"✅ 笔记已生成并保存到 {dest_label}！"

        return result

    except Exception as e:
        # 分类异常，返回结构化错误
        from ..utils.exceptions import VidkNotError
        if isinstance(e, VidkNotError):
            return {
                "success": False,
                "error": e.message,
                "error_details": e.details,
                "error_type": e.__class__.__name__,
            }
        return {
            "success": False,
            "error": str(e),
            "error_type": e.__class__.__name__,
        }


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

