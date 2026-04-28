"""
VidkNot 统一异常体系

所有模块应从此文件导入异常，禁止抛出裸 Exception。
"""


class VidkNotError(Exception):
    """VidkNot 基异常"""

    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self):
        if self.details:
            return f"{self.message} | 详情: {self.details}"
        return self.message


# ===== 下载相关 =====

class DownloadError(VidkNotError):
    """视频下载失败"""
    pass


class PlatformNotSupportedError(DownloadError):
    """不支持的视频平台"""
    pass


class CookieExportError(DownloadError):
    """Cookie 导出失败"""
    pass


class AudioExtractError(DownloadError):
    """音频提取失败"""
    pass


# ===== 转录相关 =====

class TranscriptionError(VidkNotError):
    """语音转录失败"""
    pass


class WhisperModelLoadError(TranscriptionError):
    """Whisper 模型加载失败"""
    pass


class EmptyAudioError(TranscriptionError):
    """音频文件为空或无语音内容"""
    pass


class UnsupportedAudioFormatError(TranscriptionError):
    """不支持的音频格式"""
    pass


# ===== LLM 处理相关 =====

class LLMError(VidkNotError):
    """LLM 调用失败"""
    pass


class LLMTimeoutError(LLMError):
    """LLM 请求超时"""
    pass


class LLMAPIError(LLMError):
    """LLM API 返回错误"""

    def __init__(self, message: str, status_code: int = None, details: str = None):
        super().__init__(message, details)
        self.status_code = status_code


class NoAPIKeyError(VidkNotError):
    """未配置 API Key"""
    pass


# ===== 存储相关 =====

class StorageError(VidkNotError):
    """存储操作失败"""
    pass


class FeishuAuthError(StorageError):
    """飞书认证失败"""
    pass


class FeishuPermissionError(StorageError):
    """飞书权限不足"""
    pass


class FeishuCreateDocError(StorageError):
    """飞书文档创建失败"""
    pass


class ObsidianVaultNotFoundError(StorageError):
    """Obsidian Vault 路径不存在"""
    pass


class ObsidianWriteError(StorageError):
    """Obsidian 写入失败"""
    pass


# ===== 管道相关 =====

class PipelineError(VidkNotError):
    """处理管道错误"""
    pass


class CacheError(VidkNotError):
    """缓存操作失败"""
    pass


# ===== 环境相关 =====

class DependencyError(VidkNotError):
    """环境依赖缺失

    Note: 不使用 EnvironmentError，避免与 Python 内置 EnvironmentError (OSError 别名) 冲突。
    """
    pass


class FFmpegNotFoundError(DependencyError):
    """FFmpeg 未找到"""
    pass


class ConfigError(VidkNotError):
    """配置错误"""
    pass
