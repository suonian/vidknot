"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot 统一日志模块

使用标准 logging，提供结构化日志输出，支持 CLI/FastAPI/MCP 三种运行模式。
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

# 全局 logger 实例
_logger: Optional[logging.Logger] = None


def get_logger(name: str = "vidknot") -> logging.Logger:
    """
    获取 logger 实例（单例）

    Args:
        name: logger 名称，默认 "vidknot"

    Returns:
        配置好的 logger
    """
    global _logger

    if _logger is not None and _logger.name == name:
        return _logger

    logger = logging.getLogger(name)

    # 避免重复配置
    if logger.handlers:
        return logger

    # 从环境变量读取日志级别
    level_name = os.getenv("VIDKNOT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    # ===== 日志格式 =====
    # 检测运行模式
    is_mcp = "--mcp" in sys.argv
    is_api = "uvicorn" in sys.argv[0] if sys.argv else False
    is_cli = not is_mcp and not is_api

    if is_mcp:
        # MCP 模式：抑制日志，避免干扰 JSON-RPC 协议
        # 仅输出 ERROR 及以上到 stderr
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            "[%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    elif is_api:
        # API 模式：结构化 JSON 日志（方便日志收集）
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        # CLI 模式：人类友好的彩色格式
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        formatter = _ColoredFormatter(
            "%(asctime)s  %(message)s",
            datefmt="%H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # 抑制第三方库噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)

    _logger = logger
    return logger


class _ColoredFormatter(logging.Formatter):
    """CLI 彩色日志格式化器"""

    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",    # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def log_step(logger: logging.Logger, step: str, status: str = "start"):
    """记录管道步骤（CLI 友好）"""
    symbols = {
        "start": "⏳",
        "ok": "✅",
        "error": "❌",
        "skip": "⏭️",
        "progress": "🔄",
    }
    sym = symbols.get(status, "•")
    logger.info(f"{sym} [{step}]")


def log_download_progress(logger: logging.Logger, downloaded: int, total: int, speed: str):
    """记录下载进度（CLI 友好）"""
    pct = min(100, int(downloaded / total * 100)) if total > 0 else 0
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    logger.info(f"  [{bar}] {pct}%  {speed}")


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

