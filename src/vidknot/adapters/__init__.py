"""
VidkNot 适配器模块
"""

from .mcp_server import MCPServer, run_mcp_server
from .agent_bridge import get_tool_metadata, execute_tool

__all__ = [
    "MCPServer",
    "run_mcp_server",
    "get_tool_metadata",
    "execute_tool",
]
