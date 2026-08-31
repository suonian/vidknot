"""
VidkNot 统一异常体系

所有模块应从此文件导入异常，禁止抛出裸 Exception。

每个异常可携带 hint（修正建议）：未显式传入时回退到类属性 default_hint，
让错误提示能引导用户自行修正问题，而不是只抛出技术性描述。
"""


class VidkNotError(Exception):
    """VidkNot 基异常"""

    default_hint: str = None

    def __init__(self, message: str, details: str = None, hint: str = None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.hint = hint if hint is not None else self.default_hint

    def __str__(self):
        result = self.message
        if self.details:
            result += f" | 详情: {self.details}"
        if self.hint:
            result += f" | 建议: {self.hint}"
        return result


# ===== 下载相关 =====

class DownloadError(VidkNotError):
    """视频下载失败"""

    default_hint = (
        "请检查链接是否完整有效、网络是否可达；"
        "若为会员专属或付费内容，VidkNot 不支持提取（见 docs/PLATFORMS.md）"
    )


class PlatformNotSupportedError(DownloadError):
    """不支持的视频平台"""

    default_hint = "请查看 docs/PLATFORMS.md 了解支持的平台列表，或使用通用链接重试"


class CookieExportError(DownloadError):
    """Cookie 导出失败"""

    default_hint = (
        "请在浏览器中确认已登录该平台，然后按 COOKIE_GUIDE.md 重新导出 Cookie；"
        "Chrome 需先完全退出再导出"
    )


class AudioExtractError(DownloadError):
    """音频提取失败"""

    default_hint = "请确认已安装 FFmpeg（vidknot --check-env 可检测），或改用有内嵌音频的视频"


# ===== 转录相关 =====

class TranscriptionError(VidkNotError):
    """语音转录失败"""

    default_hint = "可先运行 vidknot --demo 验证转写链路；若持续失败请检查 SILICONFLOW_API_KEY 额度"


class WhisperModelLoadError(TranscriptionError):
    """Whisper 模型加载失败"""

    default_hint = "首次使用需联网下载模型，请检查网络与磁盘空间；国内可配置代理后重试"


class EmptyAudioError(TranscriptionError):
    """音频文件为空或无语音内容"""

    default_hint = "该视频可能没有语音（纯音乐/无声），请更换有人声的内容重试"


class UnsupportedAudioFormatError(TranscriptionError):
    """不支持的音频格式"""

    default_hint = "请确认 FFmpeg 可用，VidkNot 会用它自动转码音频"


# ===== LLM 处理相关 =====

class LLMError(VidkNotError):
    """LLM 调用失败"""

    default_hint = "请检查 LLM 提供方配置与余额；也可在 config.yaml 中切换 provider"


class LLMTimeoutError(LLMError):
    """LLM 请求超时"""

    default_hint = "请稍后重试；长视频可在 config.yaml network.api_timeout 中调大超时"


class LLMAPIError(LLMError):
    """LLM API 返回错误"""

    def __init__(self, message: str, status_code: int = None, details: str = None, hint: str = None):
        super().__init__(message, details, hint)
        self.status_code = status_code


class NoAPIKeyError(VidkNotError):
    """未配置 API Key"""

    default_hint = (
        "请在 .env 或环境变量中设置 SILICONFLOW_API_KEY"
        "（硅基流动官网免费注册获取），参考 docs/CONFIG.md"
    )


# ===== 校正相关 =====

class CorrectionError(VidkNotError):
    """双 ASR 校正失败"""


# ===== 存储相关 =====

class StorageError(VidkNotError):
    """存储操作失败"""

    default_hint = "请检查目标存储后端配置（config.yaml）与网络连通性"


class FeishuAuthError(StorageError):
    """飞书认证失败"""

    default_hint = "请检查 feishu.app_id/app_secret 是否正确，并确认应用已获得文档权限"


class FeishuPermissionError(StorageError):
    """飞书权限不足"""

    default_hint = "请在飞书开放平台为应用开通云文档写入权限，或将机器人加入目标空间"


class FeishuCreateDocError(StorageError):
    """飞书文档创建失败"""

    default_hint = "请确认目标文件夹可写，且应用在该空间有创建权限"


class ObsidianVaultNotFoundError(StorageError):
    """Obsidian Vault 路径不存在"""

    default_hint = "请检查 config.yaml 中 obsidian.vault_path 是否指向有效的 Obsidian 仓库目录"


class ObsidianWriteError(StorageError):
    """Obsidian 写入失败"""

    default_hint = "请检查仓库目录写权限与磁盘空间"


# ===== 管道相关 =====

class PipelineError(VidkNotError):
    """处理管道错误"""


class CacheError(VidkNotError):
    """缓存操作失败"""


# ===== 环境相关 =====

class DependencyError(VidkNotError):
    """环境依赖缺失

    Note: 不使用 EnvironmentError，避免与 Python 内置 EnvironmentError (OSError 别名) 冲突。
    """

    default_hint = "运行 vidknot --check-env 查看缺失依赖及安装指引"


class FFmpegNotFoundError(DependencyError):
    """FFmpeg 未找到"""

    default_hint = (
        "安装方式：brew install ffmpeg / apt install ffmpeg，"
        "或 pip install 'vidknot[bundled-ffmpeg]' 使用内置静态版本"
    )


class ConfigError(VidkNotError):
    """配置错误"""

    default_hint = "请对照 docs/CONFIG.md 检查 config.yaml / .env 的格式与字段名"
