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
