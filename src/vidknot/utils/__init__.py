"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""VidkNot 工具模块"""

from .cache_manager import CacheManager
from .config_manager import ConfigManager
from .env_check import (
    check_ffmpeg,
    check_python_version,
    check_yt_dlp,
    check_whisper,
    check_all_requirements,
    get_install_guide,
)
from .logger import get_logger, log_step, log_download_progress
from .exceptions import (
    VidkNotError,
    DownloadError,
    PlatformNotSupportedError,
    AudioExtractError,
    TranscriptionError,
    EmptyAudioError,
    UnsupportedAudioFormatError,
    LLMError,
    LLMTimeoutError,
    LLMAPIError,
    NoAPIKeyError,
    StorageError,
    FeishuAuthError,
    FeishuPermissionError,
    FeishuCreateDocError,
    ObsidianVaultNotFoundError,
    ObsidianWriteError,
    DependencyError,
    FFmpegNotFoundError,
    ConfigError,
)

__all__ = [
    # Cache
    "CacheManager",
    # Config
    "ConfigManager",
    # Env
    "check_ffmpeg",
    "check_python_version",
    "check_yt_dlp",
    "check_whisper",
    "check_all_requirements",
    "get_install_guide",
    # Logging
    "get_logger",
    "log_step",
    "log_download_progress",
    # Exceptions
    "VidkNotError",
    "DownloadError",
    "PlatformNotSupportedError",
    "AudioExtractError",
    "TranscriptionError",
    "EmptyAudioError",
    "UnsupportedAudioFormatError",
    "LLMError",
    "LLMTimeoutError",
    "LLMAPIError",
    "NoAPIKeyError",
    "StorageError",
    "FeishuAuthError",
    "FeishuPermissionError",
    "FeishuCreateDocError",
    "ObsidianVaultNotFoundError",
    "ObsidianWriteError",
    "DependencyError",
    "FFmpegNotFoundError",
    "ConfigError",
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

