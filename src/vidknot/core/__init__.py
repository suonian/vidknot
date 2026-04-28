"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot Core 模块
"""

from .downloader import VideoDownloader
from .transcriber import SiliconFlowASR
from .processor import ContentProcessor
from .download_manager import SmartDownloadManager

__all__ = [
    "VideoDownloader",
    "SiliconFlowASR",
    "ContentProcessor",
    "SmartDownloadManager",
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

