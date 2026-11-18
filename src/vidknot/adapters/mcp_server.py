"""
VidkNot MCP Server

基于 FastMCP 3.0 的 Model Context Protocol 实现
支持 Stdio / SSE / HTTP 多种传输方式
用于 OpenClaw / Claude Desktop 等 AI Agent 集成
"""

import json
import signal
import sys
from pathlib import Path
from typing import Any

from .._version import __version__

try:
    from fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    FastMCP = None

from ..utils.exceptions import (
    DependencyError,
    DownloadError,
    LLMError,
    StorageError,
    TranscriptionError,
)
from ..utils.logger import get_logger

logger = get_logger("vidknot.mcp")


class MCPServer:
    """
    MCP Stdio 服务器（Fallback 模式）

    通过标准输入/输出与客户端通信
    支持 OpenClaw / Claude Desktop
    """

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self):
        self.running = False

    def run(self):
        """启动 MCP 服务器"""
        self.running = True

        # MCP stdio 协议要求 UTF-8；Windows 下默认是本地代码页（中文为 GBK）
        from ..utils.stdio import ensure_utf8_stdio
        ensure_utf8_stdio()

        def shutdown_handler(signum, frame):
            logger.info("收到关闭信号，正在退出...")
            self.running = False

        try:
            signal.signal(signal.SIGINT, shutdown_handler)
            signal.signal(signal.SIGTERM, shutdown_handler)
        except (AttributeError, ValueError):
            pass

        logger.info("VidkNot MCP Server 启动中...")

        self._send_notification("initialized", {})

        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    self._send_error(None, "Invalid JSON", -32700)
                    continue

                response = self._handle_request(request)
                if response is not None:
                    self._send_response(response)

            except Exception as e:
                logger.exception(f"处理请求时出错: {e}")
                self._send_error(None, str(e), -32603)

    def _handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """处理 MCP 请求"""
        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "notifications/initialized": self._handle_initialized,
        }

        handler = handlers.get(method)
        if handler:
            return handler(params, req_id)

        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
            "id": req_id,
        }

    def _handle_initialize(self, params: dict, req_id: Any) -> dict[str, Any]:
        """处理初始化请求"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                    "logging": {},
                },
                "serverInfo": {
                    "name": "vidknot",
                    "version": __version__,
                },
            },
            "id": req_id,
        }

    def _handle_initialized(self, params: dict, req_id: Any) -> dict[str, Any] | None:
        """处理初始化完成通知（不需要响应）"""
        logger.info("MCP 客户端初始化完成")
        return None

    def _handle_tools_list(self, params: dict, req_id: Any) -> dict[str, Any]:
        """处理工具列表请求"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": list_tools_schema(),
            },
            "id": req_id,
        }

    def _handle_tools_call(self, params: dict, req_id: Any) -> dict[str, Any]:
        """处理工具调用请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name in ("video_knowledge", "video_to_notes"):
            return self._handle_video_knowledge(arguments, req_id)
        elif tool_name == "batch_process":
            return self._handle_batch_process(arguments, req_id)
        elif tool_name == "platform_status":
            return self._handle_platform_status(req_id)
        elif tool_name == "search_video":
            return self._handle_search_video(arguments, req_id)
        elif tool_name == "video_material":
            return self._handle_video_material(arguments, req_id)
        elif tool_name == "save_note":
            return self._handle_save_note(arguments, req_id)
        else:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}",
                },
                "id": req_id,
            }

    def _handle_video_material(self, arguments: dict, req_id: Any) -> dict[str, Any]:
        """处理 video_material 工具调用（Agent 两段式契约 · 第一段）

        只做确定性采集：下载 → ASR → 双 ASR diff → 待搜证词。
        **不调用任何 LLM、不发起任何联网搜索**——搜证与校正由宿主智能体
        用它自己的搜索工具与模型完成。
        """
        url = arguments.get("url")
        if not url:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "url 参数必填"},
                "id": req_id,
            }

        language = arguments.get("language", "auto")
        with_diff = bool(arguments.get("with_diff", True))
        max_candidates = int(arguments.get("max_candidates", 12))

        logger.info(f"MCP 调用: video_material url={url}")

        try:
            bundle = collect_material_bundle(
                url,
                language=language,
                with_diff=with_diff,
                max_candidates=max_candidates,
            )
            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(bundle, ensure_ascii=False, indent=2),
                        }
                    ]
                },
                "id": req_id,
            }
        except DependencyError as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": f"环境配置错误: {e.message}"},
                "id": req_id,
            }
        except DownloadError as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32002, "message": f"下载失败: {e.message}"},
                "id": req_id,
            }
        except TranscriptionError as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32003, "message": f"转录失败: {e.message}"},
                "id": req_id,
            }
        except Exception as e:
            logger.exception(f"素材包采集错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

    def _handle_save_note(self, arguments: dict, req_id: Any) -> dict[str, Any]:
        """处理 save_note 工具调用（Agent 两段式契约 · 第二段）

        把宿主智能体用自己的模型写好的 Markdown 回存到目的地。
        """
        markdown = arguments.get("markdown")
        if not markdown:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "markdown 参数必填"},
                "id": req_id,
            }

        url = arguments.get("url", "")
        destination = arguments.get("destination", "obsidian")
        title = arguments.get("title") or "视频笔记"
        author = arguments.get("author", "")
        duration = arguments.get("duration", 0)
        tags = arguments.get("tags") or []
        feishu_folder = arguments.get("feishu_folder")

        logger.info(f"MCP 调用: save_note destination={destination}")

        try:
            saved = save_note_markdown(
                markdown,
                url=url,
                title=title,
                author=author,
                duration=duration,
                destination=destination,
                tags=tags,
                feishu_folder=feishu_folder,
                language=arguments.get("language", "auto"),
                source_platform=arguments.get("source_platform", ""),
            )
            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"saved_to": saved, "title": title},
                                ensure_ascii=False,
                                indent=2,
                            ),
                        }
                    ]
                },
                "id": req_id,
            }
        except StorageError as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32005, "message": f"保存失败: {e.message}"},
                "id": req_id,
            }
        except Exception as e:
            logger.exception(f"保存笔记错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

    def _handle_batch_process(self, arguments: dict, req_id: Any) -> dict[str, Any]:
        """处理 batch_process 工具调用"""
        from ..pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        urls = arguments.get("urls") or []
        if not urls or not isinstance(urls, list):
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "urls 参数必填（URL 数组）"},
                "id": req_id,
            }

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
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"total": len(summary),
                                 "success": sum(1 for s in summary if s["success"]),
                                 "results": summary},
                                ensure_ascii=False, indent=2,
                            ),
                        }
                    ]
                },
                "id": req_id,
            }
        except Exception as e:
            logger.exception(f"批量处理错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

    def _handle_platform_status(self, req_id: Any) -> dict[str, Any]:
        """处理 platform_status 工具调用"""
        try:
            payload = get_platform_status()
            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}
                    ]
                },
                "id": req_id,
            }
        except Exception as e:
            logger.exception(f"平台状态查询错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

    def _handle_search_video(self, arguments: dict, req_id: Any) -> dict[str, Any]:
        """处理 search_video 工具调用（预留）"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "search_video 尚未实现（预留接口，依赖平台内搜索搜证链路）。"
                        "当前请直接提供视频 URL 使用 video_to_notes / batch_process。",
                    }
                ]
            },
            "id": req_id,
        }

    def _handle_video_knowledge(self, arguments: dict, req_id: Any) -> dict[str, Any]:
        """处理 video_knowledge 工具调用（同步）"""
        from ..pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        url = arguments.get("url")
        if not url:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "url 参数必填"},
                "id": req_id,
            }

        destination = arguments.get("destination", "obsidian")
        format_mode = arguments.get("format", "structured")
        language = arguments.get("language", "auto")
        feishu_folder = arguments.get("feishu_folder")
        obsidian_tags = arguments.get("obsidian_tags", [])
        notify = arguments.get("notify", True)

        logger.info(f"MCP 调用: url={url}, destination={destination}")

        try:
            pipeline = VideoKnowledgePipeline(
                destination=destination,
                format=format_mode,
                language=language,
            )

            result = pipeline.run(url)

            if destination != "none":
                try:
                    saved = pipeline.save(result, {
                        "feishu_folder": feishu_folder,
                        "obsidian_tags": obsidian_tags,
                    })
                except StorageError as e:
                    # 保存失败但笔记已生成 —— 把成稿一并回传，避免内容丢失
                    logger.error(f"保存失败: {e.message}")
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32005,
                            "message": f"保存失败: {e.message}",
                            "data": {
                                "title": result.get("title", ""),
                                "markdown": result.get("markdown", ""),
                            },
                        },
                        "id": req_id,
                    }
                result["saved_to"] = saved

            if notify:
                saved_str = result.get("saved_to", destination)
                result["notify"] = {
                    "message": f"✅ 笔记已生成！保存到: {saved_str}",
                    "title": result.get("title", "视频笔记"),
                }

            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2),
                        }
                    ]
                },
                "id": req_id,
            }

        except DependencyError as e:
            logger.error(f"环境错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": f"环境配置错误: {e.message}"},
                "id": req_id,
            }
        except DownloadError as e:
            logger.error(f"下载错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32002, "message": f"下载失败: {e.message}"},
                "id": req_id,
            }
        except TranscriptionError as e:
            logger.error(f"转录错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32003, "message": f"转录失败: {e.message}"},
                "id": req_id,
            }
        except LLMError as e:
            logger.error(f"LLM 错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32004, "message": f"笔记生成失败: {e.message}"},
                "id": req_id,
            }
        except StorageError as e:
            logger.error(f"存储错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32005, "message": f"保存失败: {e.message}"},
                "id": req_id,
            }
        except Exception as e:
            logger.exception(f"未知错误: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

    def _send_response(self, response: dict[str, Any]):
        """发送响应"""
        print(json.dumps(response, ensure_ascii=False))
        sys.stdout.flush()

    def _send_notification(self, method: str, params: dict):
        """发送通知（无 id）"""
        print(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}, ensure_ascii=False))
        sys.stdout.flush()

    def _send_error(self, req_id: Any, message: str, code: int):
        """发送错误响应"""
        self._send_response({
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": req_id,
        })


def list_tools_schema() -> list[dict[str, Any]]:
    """
    MCP 工具 schema 列表（供 tools/list 与 Agent 集成使用）

    包含: video_to_notes / batch_process / platform_status / search_video
    以及两段式 Agent 契约: video_material / save_note
    """
    return [
        {
            "name": "video_to_notes",
            "description": (
                "将视频链接转换为结构化笔记（Markdown + 结构化 JSON），"
                "可自动保存到飞书文档或 Obsidian Vault。"
                "支持 YouTube、Bilibili、抖音、小红书、TikTok、Twitter/X 等平台。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "视频链接",
                    },
                    "destination": {
                        "type": "string",
                        "enum": ["feishu", "obsidian", "both", "none"],
                        "description": "笔记保存目的地（默认 obsidian）",
                        "default": "obsidian",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["structured", "raw"],
                        "description": "structured=结构化笔记，raw=仅原始转录",
                        "default": "structured",
                    },
                    "language": {
                        "type": "string",
                        "description": "视频语言: auto/zh/en/ja/ko",
                        "default": "auto",
                    },
                    "feishu_folder": {
                        "type": "string",
                        "description": "飞书文档保存的文件夹名称",
                    },
                    "obsidian_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Obsidian 笔记标签",
                    },
                },
                "required": ["url"],
            },
        },
        {
            "name": "batch_process",
            "description": "批量处理多个视频链接，并发执行（默认 3 并发），返回每个 URL 的处理结果摘要。",
            "inputSchema": {
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
                        "description": "笔记保存目的地（默认 none）",
                        "default": "none",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["structured", "raw"],
                        "default": "structured",
                    },
                    "language": {
                        "type": "string",
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
        {
            "name": "platform_status",
            "description": "查询各视频平台的支持状态（域名、字幕支持、Cookie 配置、转录策略）。",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "search_video",
            "description": "在平台内搜索视频（预留接口，当前未实现）。",
            "inputSchema": {
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
        {
            "name": "video_material",
            "description": (
                "采集视频素材包（Agent 两段式契约 · 第一段）。"
                "只做确定性采集：下载 → 字幕/ASR 转写 → 双 ASR 差异 → 待搜证词，"
                "返回转写全文、差异清单与候选词。"
                "本工具不调用任何大模型、不发起任何联网搜索——"
                "请用你自己的搜索工具对 search_candidates 搜证，"
                "用你自己的模型完成纠错与成稿，最后调用 save_note 落库。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "视频链接",
                    },
                    "language": {
                        "type": "string",
                        "description": "视频语言: auto/zh/en/ja/ko",
                        "default": "auto",
                    },
                    "with_diff": {
                        "type": "boolean",
                        "description": "是否跑 faster-whisper 做对照并产出差异清单",
                        "default": True,
                    },
                    "max_candidates": {
                        "type": "integer",
                        "description": "待搜证词上限（默认 12）",
                        "default": 12,
                    },
                },
                "required": ["url"],
            },
        },
        {
            "name": "save_note",
            "description": (
                "保存已写好的 Markdown 笔记（Agent 两段式契约 · 第二段）。"
                "把宿主智能体用自己的模型生成的成稿回存到飞书/语雀/Notion/Obsidian。"
                "本工具不调用任何大模型，只负责落库。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "markdown": {
                        "type": "string",
                        "description": "笔记正文（Markdown）",
                    },
                    "url": {
                        "type": "string",
                        "description": "视频来源链接（写入 frontmatter）",
                    },
                    "title": {
                        "type": "string",
                        "description": "笔记标题",
                        "default": "视频笔记",
                    },
                    "author": {
                        "type": "string",
                        "description": "视频作者",
                    },
                    "duration": {
                        "type": "integer",
                        "description": "视频时长（秒）",
                        "default": 0,
                    },
                    "source_platform": {
                        "type": "string",
                        "description": "来源平台（如 bilibili/youtube）",
                    },
                    "destination": {
                        "type": "string",
                        "enum": ["feishu", "yuque", "notion", "obsidian", "both", "none"],
                        "description": "保存目的地（默认 obsidian）",
                        "default": "obsidian",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "笔记标签",
                    },
                    "feishu_folder": {
                        "type": "string",
                        "description": "飞书文档保存的文件夹名称",
                    },
                },
                "required": ["markdown"],
            },
        },
    ]


def get_platform_status() -> dict[str, Any]:
    """
    汇总各平台支持状态

    Returns:
        {"transcription_strategy": str, "platforms": [{name, domains,
         subtitle_support, cookie_configured, browser_cookie}, ...]}
    """
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
        cookie_configured = browser_cookie or (cookie_dir / f"{name}.txt").exists()
        platforms.append({
            "name": name,
            "domains": list(platform.domains),
            "subtitle_support": subtitle_supported,
            "cookie_configured": cookie_configured,
            "browser_cookie": browser_cookie,
        })

    return {
        "transcription_strategy": strategy,
        "platform_count": len(platforms),
        "platforms": platforms,
    }


# ===== 两段式 Agent 契约（自研 JSON-RPC 与 FastMCP 共用实现）=====


def collect_material_bundle(
    url: str,
    language: str = "auto",
    with_diff: bool = True,
    max_candidates: int = 12,
) -> dict[str, Any]:
    """采集视频素材包（Agent 两段式契约 · 第一段）。

    只做确定性采集（下载 / 转写 / 双 ASR diff / 待搜证词），
    **不调用任何 LLM、不发起任何联网搜索**。

    Args:
        url: 视频链接
        language: 视频语言
        with_diff: 是否跑 faster-whisper 对照并产出差异清单
        max_candidates: 待搜证词上限

    Returns:
        素材包字典（schema: vidknot.material/1）
    """
    from ..pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

    pipeline = VideoKnowledgePipeline(
        destination="none",
        format="raw",
        language=language,
    )
    return pipeline.collect_material(
        url,
        with_diff=with_diff,
        max_candidates=max_candidates,
    )


def save_note_markdown(
    markdown: str,
    url: str = "",
    title: str = "",
    author: str = "",
    duration: int = 0,
    destination: str = "obsidian",
    tags: list[str] | None = None,
    feishu_folder: str | None = None,
    language: str = "auto",
    source_platform: str = "",
) -> str | list[str]:
    """保存已写好的 Markdown（Agent 两段式契约 · 第二段）。

    本函数只负责落库，**不调用任何大模型**。

    Args:
        markdown: 笔记正文
        url: 视频来源链接
        title: 笔记标题
        author: 视频作者
        duration: 视频时长（秒）
        destination: 保存目的地
        tags: 笔记标签
        feishu_folder: 飞书文件夹名
        language: 视频语言
        source_platform: 来源平台

    Returns:
        保存位置（单一目的地为字符串，多个为列表）
    """
    from ..pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

    pipeline = VideoKnowledgePipeline(
        destination=destination,
        format="structured",
        language=language,
    )
    return pipeline.save_markdown(
        url,
        markdown,
        metadata={
            "title": title or "视频笔记",
            "author": author,
            "duration": duration,
            "source_url": url,
            "source_platform": source_platform,
        },
        options={
            "tags": tags or [],
            "feishu_folder": feishu_folder,
        },
    )


def run_mcp_server():
    """运行 MCP 服务器的入口函数"""
    # 无论走 FastMCP 还是自研 JSON-RPC，都先统一标准流编码
    from ..utils.stdio import ensure_utf8_stdio
    ensure_utf8_stdio()

    if HAS_FASTMCP:
        run_fastmcp_server()
    else:
        server = MCPServer()
        server.run()


def run_fastmcp_server():
    """使用 FastMCP 运行服务器（推荐）"""
    mcp = FastMCP("vidknot")

    @mcp.tool()
    def video_knowledge(
        url: str,
        destination: str = "obsidian",
        format: str = "structured",
        language: str = "auto",
        feishu_folder: str = None,
        obsidian_tags: list = None,
    ) -> str:
        """
        将视频链接转换为结构化笔记，自动保存到飞书文档或 Obsidian Vault。

        Args:
            url: 视频链接（支持 YouTube、Bilibili、抖音、小红书等平台）
            destination: 保存目的地: feishu/obsidian/both/none
            format: structured=结构化笔记，raw=仅原始转录
            language: 视频语言: auto/zh/en/ja/ko
            feishu_folder: 飞书文档保存的文件夹名称
            obsidian_tags: Obsidian 笔记标签列表
        """
        from ..pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        logger.info(f"FastMCP 调用: url={url}")

        pipeline = VideoKnowledgePipeline(
            destination=destination,
            format=format,
            language=language,
        )

        result = pipeline.run(url)

        if destination != "none":
            pipeline.save(result, {
                "feishu_folder": feishu_folder,
                "obsidian_tags": obsidian_tags or [],
            })

        return result.get("markdown", result.get("transcription", ""))

    @mcp.tool()
    def video_to_notes(
        url: str,
        destination: str = "obsidian",
        format: str = "structured",
        language: str = "auto",
        feishu_folder: str = None,
        obsidian_tags: list = None,
    ) -> str:
        """
        将视频链接转换为结构化笔记（video_knowledge 的别名工具）。

        Args:
            url: 视频链接
            destination: 保存目的地: feishu/obsidian/both/none
            format: structured=结构化笔记，raw=仅原始转录
            language: 视频语言: auto/zh/en/ja/ko
            feishu_folder: 飞书文档保存的文件夹名称
            obsidian_tags: Obsidian 笔记标签列表
        """
        return video_knowledge.fn(
            url=url,
            destination=destination,
            format=format,
            language=language,
            feishu_folder=feishu_folder,
            obsidian_tags=obsidian_tags,
        ) if hasattr(video_knowledge, "fn") else video_knowledge(
            url=url,
            destination=destination,
            format=format,
            language=language,
            feishu_folder=feishu_folder,
            obsidian_tags=obsidian_tags,
        )

    @mcp.tool()
    def batch_process(
        urls: list[str],
        destination: str = "none",
        format: str = "structured",
        language: str = "auto",
        max_workers: int = 3,
    ) -> str:
        """
        批量处理多个视频链接（并发执行）。

        Args:
            urls: 视频链接列表
            destination: 保存目的地: feishu/obsidian/both/none
            format: structured=结构化笔记，raw=仅原始转录
            language: 视频语言: auto/zh/en/ja/ko
            max_workers: 并发数（1-8，默认 3）
        """
        from ..pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(
            destination=destination,
            format=format,
            language=language,
        )
        save_options = None if destination == "none" else {}
        results = pipeline.run_batch(
            urls, max_workers=min(max_workers, 8), save_options=save_options
        )
        summary = [
            {
                "url": r.get("url", ""),
                "success": r.get("success", False),
                "title": r.get("title", ""),
                "error": r.get("error"),
            }
            for r in results
        ]
        return json.dumps(
            {
                "total": len(summary),
                "success": sum(1 for s in summary if s["success"]),
                "results": summary,
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def platform_status() -> str:
        """查询各视频平台的支持状态（域名、字幕支持、Cookie 配置、转录策略）。"""
        return json.dumps(get_platform_status(), ensure_ascii=False, indent=2)

    @mcp.tool()
    def search_video(query: str, platform: str = "") -> str:
        """
        在平台内搜索视频（预留接口）。

        Args:
            query: 搜索关键词
            platform: 目标平台（如 youtube/bilibili/douyin）
        """
        return (
            "search_video 尚未实现（预留接口，依赖平台内搜索搜证链路）。"
            "当前请直接提供视频 URL 使用 video_to_notes / batch_process。"
        )

    @mcp.tool()
    def video_material(
        url: str,
        language: str = "auto",
        with_diff: bool = True,
        max_candidates: int = 12,
    ) -> str:
        """
        采集视频素材包（Agent 两段式契约 · 第一段）。

        只做确定性采集：下载 → 字幕/ASR 转写 → 双 ASR 差异 → 待搜证词。
        **本工具不调用任何大模型、不发起任何联网搜索**。

        请用你自己的搜索工具对 search_candidates 搜证，用你自己的模型完成
        纠错与成稿，最后调用 save_note 落库。

        Args:
            url: 视频链接
            language: 视频语言: auto/zh/en/ja/ko
            with_diff: 是否跑 faster-whisper 对照并产出差异清单
            max_candidates: 待搜证词上限
        """
        bundle = collect_material_bundle(
            url,
            language=language,
            with_diff=with_diff,
            max_candidates=max_candidates,
        )
        return json.dumps(bundle, ensure_ascii=False, indent=2)

    @mcp.tool()
    def save_note(
        markdown: str,
        url: str = "",
        title: str = "",
        author: str = "",
        duration: int = 0,
        destination: str = "obsidian",
        tags: list = None,
        feishu_folder: str = None,
        source_platform: str = "",
    ) -> str:
        """
        保存已写好的 Markdown 笔记（Agent 两段式契约 · 第二段）。

        把宿主智能体用自己的模型生成的成稿回存到飞书/语雀/Notion/Obsidian。
        **本工具不调用任何大模型，只负责落库。**

        Args:
            markdown: 笔记正文
            url: 视频来源链接
            title: 笔记标题
            author: 视频作者
            duration: 视频时长（秒）
            destination: 保存目的地: feishu/yuque/notion/obsidian/both/none
            tags: 笔记标签
            feishu_folder: 飞书文档保存的文件夹名称
            source_platform: 来源平台
        """
        saved = save_note_markdown(
            markdown,
            url=url,
            title=title,
            author=author,
            duration=duration,
            destination=destination,
            tags=tags or [],
            feishu_folder=feishu_folder,
            source_platform=source_platform,
        )
        return json.dumps(
            {"saved_to": saved, "title": title or "视频笔记"},
            ensure_ascii=False,
            indent=2,
        )

    mcp.run(transport="stdio")
