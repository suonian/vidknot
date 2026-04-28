"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot - Video Knowledge, Knotted.

Tie your video knowledge together.
视频知识，结成一网。

Core module for Agent-driven video knowledge pipeline.
"""

__version__ = "0.1.0"
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

