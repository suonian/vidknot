"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot MCP Server

基于 FastMCP 3.0 的 Model Context Protocol 实现
支持 Stdio / SSE / HTTP 多种传输方式
用于 OpenClaw / Claude Desktop 等 AI Agent 集成
"""

import json
import sys
import signal
from typing import Dict, Any, Optional

try:
    from fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    FastMCP = None

from ..utils.logger import get_logger
from ..utils.exceptions import (
    DownloadError,
    TranscriptionError,
    LLMError,
    StorageError,
    DependencyError,
)

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

    def _handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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

    def _handle_initialize(self, params: Dict, req_id: Any) -> Dict[str, Any]:
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
                    "version": "0.1.0",
                },
            },
            "id": req_id,
        }

    def _handle_initialized(self, params: Dict, req_id: Any) -> Optional[Dict[str, Any]]:
        """处理初始化完成通知（不需要响应）"""
        logger.info("MCP 客户端初始化完成")
        return None

    def _handle_tools_list(self, params: Dict, req_id: Any) -> Dict[str, Any]:
        """处理工具列表请求"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "video_knowledge",
                        "description": (
                            "将视频链接转换为结构化笔记，自动保存到飞书文档或 Obsidian Vault。"
                            "适用于用户转发视频链接后自动生成学习笔记的场景。"
                            "支持 YouTube、Bilibili、抖音、小红书等 10+ 平台。"
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "视频链接（支持 YouTube、Bilibili、抖音、小红书等平台）",
                                },
                                "destination": {
                                    "type": "string",
                                    "enum": ["feishu", "obsidian", "both", "none"],
                                    "description": "笔记保存目的地",
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
                                    "description": "视频语言：auto/zh/en/ja/ko",
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
                                "notify": {
                                    "type": "boolean",
                                    "description": "处理完成后是否发送通知",
                                    "default": True,
                                },
                            },
                            "required": ["url"],
                        },
                    },
                ],
            },
            "id": req_id,
        }

    def _handle_tools_call(self, params: Dict, req_id: Any) -> Dict[str, Any]:
        """处理工具调用请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "video_knowledge":
            return self._handle_video_knowledge(arguments, req_id)
        else:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}",
                },
                "id": req_id,
            }

    def _handle_video_knowledge(self, arguments: Dict, req_id: Any) -> Dict[str, Any]:
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

    def _send_response(self, response: Dict[str, Any]):
        """发送响应"""
        print(json.dumps(response, ensure_ascii=False))
        sys.stdout.flush()

    def _send_notification(self, method: str, params: Dict):
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

    mcp.run(transport="stdio")


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

