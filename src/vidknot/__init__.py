"""
VidkNot - Video Knowledge, Knotted.

Tie your video knowledge together.
视频知识，结成一网。

Core module for Agent-driven video knowledge pipeline.
"""

from ._version import __version__

__author__ = "VidkNot Team"
__license__ = "MIT"

from .core.downloader import VideoDownloader
from .core.transcriber import SiliconFlowASR, get_transcriber
from .core.processor import ContentProcessor
from .pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

__all__ = [
    "VideoDownloader",
    "SiliconFlowASR",
    "get_transcriber",
    "ContentProcessor",
    "VideoKnowledgePipeline",
]
