"""
VidkNot Agent 桥接模块

提供 OpenAI Function Calling Schema 定义
用于 OpenAI / Claude 等 AI Agent 集成

工具清单:
- video_knowledge / video_to_notes: 单视频转笔记
- batch_process: 批量处理多个视频
- platform_status: 平台支持状态查询
- search_video: 平台内搜索（预留）
"""

from typing import Any


def get_tool_metadata() -> dict[str, Any]:
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


def get_all_tools_metadata() -> list[dict[str, Any]]:
    """
    获取所有 VidkNot 工具的 OpenAI Function Calling Schema 列表

    Returns:
        OpenAI tool schema 列表（video_knowledge / batch_process /
        platform_status / search_video）
    """
    return [
        get_tool_metadata(),
        {
            "type": "function",
            "function": {
                "name": "batch_process",
                "description": "批量处理多个视频链接，并发执行（默认 3 并发），返回每个 URL 的处理结果摘要。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "视频链接列表",
                        },
                        "destination": {
                            "type": "string",
                            "enum": ["feishu", "obsidian", "both", "none"],
                            "description": "笔记保存目的地",
                            "default": "none",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["structured", "raw"],
                            "default": "structured",
                        },
                        "language": {
                            "type": "string",
                            "description": "视频语言：auto/zh/en/ja/ko",
                            "default": "auto",
                        },
                        "max_workers": {
                            "type": "integer",
                            "description": "并发数（1-8，默认 3）",
                            "default": 3,
                        },
                    },
                    "required": ["urls"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "platform_status",
                "description": "查询各视频平台的支持状态（域名、字幕支持、Cookie 配置、转录策略）。",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_video",
                "description": "在平台内搜索视频（预留接口，当前未实现）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词",
                        },
                        "platform": {
                            "type": "string",
                            "description": "目标平台（如 youtube/bilibili/douyin）",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    ]


def execute_tool(arguments: dict[str, Any], tool: str = "video_knowledge") -> dict[str, Any]:
    """
    执行指定工具（按工具名路由）

    Args:
        arguments: 工具参数
        tool: 工具名（video_knowledge/video_to_notes/batch_process/
              platform_status/search_video）

    Returns:
        工具执行结果
    """
    if tool == "batch_process":
        return _execute_batch_process(arguments)
    if tool == "platform_status":
        return _execute_platform_status()
    if tool == "search_video":
        return _execute_search_video(arguments)
    # video_knowledge / video_to_notes
    return _execute_video_knowledge(arguments)


def _execute_batch_process(arguments: dict[str, Any]) -> dict[str, Any]:
    """执行 batch_process 工具"""
    from ..pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

    urls = arguments.get("urls") or []
    if not urls or not isinstance(urls, list):
        return {"success": False, "error": "urls 参数必填（URL 数组）"}

    destination = arguments.get("destination", "none")
    format_mode = arguments.get("format", "structured")
    language = arguments.get("language", "auto")
    max_workers = min(int(arguments.get("max_workers", 3)), 8)

    try:
        pipeline = VideoKnowledgePipeline(
            destination=destination,
            format=format_mode,
            language=language,
        )
        save_options = None if destination == "none" else {}
        results = pipeline.run_batch(urls, max_workers=max_workers, save_options=save_options)
        summary = [
            {
                "url": r.get("url", ""),
                "success": r.get("success", False),
                "title": r.get("title", ""),
                "error": r.get("error"),
            }
            for r in results
        ]
        return {
            "success": True,
            "total": len(summary),
            "success_count": sum(1 for s in summary if s["success"]),
            "results": summary,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "error_type": e.__class__.__name__}


def _execute_platform_status() -> dict[str, Any]:
    """执行 platform_status 工具"""
    try:
        from pathlib import Path

        from ..core.platforms import PlatformRegistry
        from ..core.platforms.base import BasePlatform
        from ..utils.config_manager import ConfigManager

        project_root = Path(__file__).parent.parent.parent.parent
        cookie_dir = project_root / "cookies"
        config = ConfigManager()
        strategy = config.get("platforms", "transcription", "strategy") or "subtitle_first"

        platforms: list[dict[str, Any]] = []
        for name in PlatformRegistry.list_platforms():
            platform = PlatformRegistry.get(name)
            if platform is None:
                continue
            subtitle_supported = type(platform).fetch_subtitle is not BasePlatform.fetch_subtitle
            browser_cookie = bool(getattr(platform, "use_browser_cookie", False))
            platforms.append({
                "name": name,
                "domains": list(platform.domains),
                "subtitle_support": subtitle_supported,
                "cookie_configured": browser_cookie or (cookie_dir / f"{name}.txt").exists(),
                "browser_cookie": browser_cookie,
            })

        return {
            "success": True,
            "transcription_strategy": strategy,
            "platform_count": len(platforms),
            "platforms": platforms,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "error_type": e.__class__.__name__}


def _execute_search_video(arguments: dict[str, Any]) -> dict[str, Any]:
    """执行 search_video 工具（预留）"""
    query = arguments.get("query", "")
    if not query:
        return {"success": False, "error": "query 参数必填"}
    return {
        "success": False,
        "error": "search_video 尚未实现（预留接口），请直接提供视频 URL 使用 video_to_notes / batch_process。",
        "implemented": False,
    }


def _execute_video_knowledge(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    执行 video_knowledge / video_to_notes 工具（同步）

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

        result = pipeline.run(url)

        if destination != "none":
            saved = pipeline.save(result, {
                "feishu_folder": feishu_folder,
                "obsidian_tags": obsidian_tags,
            })
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
