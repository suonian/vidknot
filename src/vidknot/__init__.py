"""
VidkNot — Video Knowledge, Knotted.

A general research platform framework:
1. Download video audio from 11+ platforms (YouTube, Bilibili, Douyin, Xiaohongshu, ...)
2. Transcribe via dual-ASR cross-validation (SiliconFlow + faster-whisper)
3. Generate structured Markdown notes via OpenAI-compatible LLM
4. Persist via pluggable backend (Obsidian / Feishu / Notion / Yuque / SQLite / custom)
5. Coordinate via async periodic scheduler (core/monitor) and batch runner (core/batch)
6. Subscribe from YAML/JSON sources with credential-leak protection (core/source)

视频知识，结成一网。通用研究平台框架。

Interfaces: CLI / FastAPI / MCP / Python API
"""

from ._version import __version__

__author__ = "VidkNot Team"
__license__ = "MIT"

from .core.downloader import VideoDownloader
from .core.processor import ContentProcessor
from .core.transcriber import SiliconFlowASR, get_transcriber
from .pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

__all__ = [
    "__version__",
    "VideoDownloader",
    "SiliconFlowASR",
    "get_transcriber",
    "ContentProcessor",
    "VideoKnowledgePipeline",
]
