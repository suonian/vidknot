"""
VidkNot 适配器模块
"""

from .agent_bridge import execute_tool, get_all_tools_metadata, get_tool_metadata
from .mcp_server import MCPServer, get_platform_status, list_tools_schema, run_mcp_server

__all__ = [
    "MCPServer",
    "run_mcp_server",
    "list_tools_schema",
    "get_platform_status",
    "get_tool_metadata",
    "get_all_tools_metadata",
    "execute_tool",
]
