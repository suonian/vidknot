"""
测试 vidknot.utils.exceptions
"""

import pytest

from vidknot.utils.exceptions import (
    ConfigError,
    DependencyError,
    DownloadError,
    EmptyAudioError,
    FeishuAuthError,
    FFmpegNotFoundError,
    LLMAPIError,
    LLMError,
    ObsidianWriteError,
    PlatformNotSupportedError,
    StorageError,
    TranscriptionError,
    VidkNotError,
)


class TestVidkNotError:
    """测试基异常"""

    def test_basic_exception(self):
        e = VidkNotError("测试消息")
        assert str(e) == "测试消息"
        assert e.message == "测试消息"
        assert e.details is None

    def test_exception_with_details(self):
        e = VidkNotError("测试消息", details="附加信息")
        assert str(e) == "测试消息 | 详情: 附加信息"
        assert e.message == "测试消息"
        assert e.details == "附加信息"


class TestDownloadError:
    """测试下载异常体系"""

    def test_download_error_is_vidknot_error(self):
        e = DownloadError("下载失败")
        assert isinstance(e, VidkNotError)

    def test_platform_not_supported(self):
        e = PlatformNotSupportedError("不支持的平台")
        assert isinstance(e, DownloadError)
        assert "不支持的平台" in str(e)


class TestTranscriptionError:
    """测试转录异常体系"""

    def test_transcription_error_hierarchy(self):
        e = TranscriptionError("转录失败")
        assert isinstance(e, VidkNotError)

    def test_empty_audio(self):
        e = EmptyAudioError("音频为空")
        assert isinstance(e, TranscriptionError)

    def test_exception_message_preserved(self):
        e = EmptyAudioError("内容为空", details="文件大小为0")
        assert "内容为空" in str(e)
        assert "文件大小为0" in str(e)


class TestLLMError:
    """测试 LLM 异常体系"""

    def test_llm_error(self):
        e = LLMError("LLM 调用失败")
        assert isinstance(e, VidkNotError)

    def test_llm_api_error_with_status(self):
        e = LLMAPIError("API 返回错误", status_code=429, details="rate limit")
        assert e.status_code == 429
        assert "rate limit" in str(e)

    def test_llm_error_catch_in_parent(self):
        """子类异常应能被父类 except 捕获"""
        with pytest.raises(LLMError):
            raise LLMAPIError("api error")


class TestStorageError:
    """测试存储异常体系"""

    def test_storage_error_hierarchy(self):
        e = StorageError("存储失败")
        assert isinstance(e, VidkNotError)

    def test_feishu_auth_error(self):
        e = FeishuAuthError("认证失败", details="token expired")
        assert isinstance(e, StorageError)

    def test_obsidian_write_error(self):
        e = ObsidianWriteError("写入失败", details="/path/to/file")
        assert isinstance(e, StorageError)


class TestDependencyError:
    """测试环境依赖异常（替代内置 EnvironmentError）"""

    def test_dependency_error_exists(self):
        """确认 DependencyError 存在且与内置 EnvironmentError 不同"""
        e = DependencyError("依赖缺失")
        assert isinstance(e, VidkNotError)
        assert not isinstance(e, OSError)  # 不应与内置 OSError 混淆

    def test_ffmpeg_not_found(self):
        e = FFmpegNotFoundError("FFmpeg 未安装")
        assert isinstance(e, DependencyError)
        assert "FFmpeg" in str(e)


class TestConfigError:
    """测试配置异常"""

    def test_config_error(self):
        e = ConfigError("配置文件不存在", details="/path/to/config.yaml")
        assert isinstance(e, VidkNotError)
        assert "配置文件不存在" in str(e)


class TestHint:
    """测试异常修正建议（hint）机制"""

    def test_explicit_hint_in_str(self):
        e = VidkNotError("出错了", hint="请重试")
        assert str(e) == "出错了 | 建议: 请重试"
        assert e.hint == "请重试"

    def test_hint_with_details(self):
        e = VidkNotError("出错了", details="原因A", hint="请重试")
        assert str(e) == "出错了 | 详情: 原因A | 建议: 请重试"

    def test_no_hint_output_unchanged(self):
        """无 hint 时输出格式与历史版本完全一致"""
        assert str(VidkNotError("纯消息")) == "纯消息"
        assert str(VidkNotError("消息", details="详情X")) == "消息 | 详情: 详情X"

    def test_default_hint_fallback(self):
        e = FFmpegNotFoundError("FFmpeg 未安装")
        assert e.hint is not None
        assert "ffmpeg" in str(e).lower()
        assert "建议" in str(e)

    def test_explicit_hint_overrides_default(self):
        e = FFmpegNotFoundError("FFmpeg 未安装", hint="自定义建议")
        assert e.hint == "自定义建议"
        assert str(e) == "FFmpeg 未安装 | 建议: 自定义建议"

    def test_llm_api_error_hint_passthrough(self):
        e = LLMAPIError("限流", status_code=429, hint="稍后重试")
        assert e.status_code == 429
        assert e.hint == "稍后重试"
        assert "稍后重试" in str(e)

    def test_key_exceptions_have_default_hints(self):
        """高频异常都应预置修正建议"""
        for cls in (DownloadError, EmptyAudioError, FFmpegNotFoundError, DependencyError):
            assert cls.default_hint, f"{cls.__name__} 缺少 default_hint"

    def test_hint_does_not_break_message(self):
        """MCP 端依赖 e.message，hint 不应污染 message"""
        e = DownloadError("下载失败", hint="检查链接")
        assert e.message == "下载失败"
