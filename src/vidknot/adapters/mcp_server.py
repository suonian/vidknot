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
        else:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}",
                },
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
                saved = pipeline.save(result, {
                    "feishu_folder": feishu_folder,
                    "obsidian_tags": obsidian_tags,
                })
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


def run_mcp_server():
    """运行 MCP 服务器的入口函数"""
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

    mcp.run(transport="stdio")
