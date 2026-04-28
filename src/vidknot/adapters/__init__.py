"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

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

