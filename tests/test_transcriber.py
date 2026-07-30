"""
测试 vidknot.core.transcriber

覆盖：
- SiliconFlowASR: 校验、API 调用、空结果
- FasterWhisperASR: 校验、模型加载、转录输出格式
- get_transcriber: 工厂函数
- UnsupportedAudioFormatError / EmptyAudioError 异常路径
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from vidknot.core.transcriber import (
    SiliconFlowASR,
    FasterWhisperASR,
    get_transcriber,
)
from vidknot.utils.exceptions import (
    TranscriptionError,
    EmptyAudioError,
    UnsupportedAudioFormatError,
    NoAPIKeyError,
)


# ========== SiliconFlowASR 测试 ==========


class TestSiliconFlowASR:
    """测试 SiliconFlowASR 类"""

    def test_supports_common_audio_formats(self):
        """应支持常见的音频格式"""
        expected = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".webm"}
        assert expected.issubset(SiliconFlowASR.SUPPORTED_FORMATS)

    def test_validate_audio_missing_file(self):
        """文件不存在应抛出 UnsupportedAudioFormatError"""
        asr = SiliconFlowASR(api_key="test-key")
        with pytest.raises(UnsupportedAudioFormatError, match="音频文件不存在"):
            asr._validate_audio(Path("/nonexistent/audio.mp3"))

    def test_validate_audio_unsupported_format(self, temp_dir):
        """不支持的格式应抛出 UnsupportedAudioFormatError"""
        asr = SiliconFlowASR(api_key="test-key")
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("not audio")
        with pytest.raises(UnsupportedAudioFormatError, match="不支持的音频格式"):
            asr._validate_audio(txt_file)

    def test_validate_audio_too_small(self, temp_dir):
        """音频文件过小应抛出 EmptyAudioError"""
        asr = SiliconFlowASR(api_key="test-key")
        small_mp3 = temp_dir / "small.mp3"
        small_mp3.write_bytes(b"\x00" * 100)  # < 1024 bytes
        with pytest.raises(EmptyAudioError, match="音频文件过小"):
            asr._validate_audio(small_mp3)

    def test_get_client_no_api_key(self, temp_dir):
        """无 API key 应抛出 NoAPIKeyError"""
        # 确保 config.yaml 和 env 中都没有 key
        with patch.dict(os.environ, {}, clear=True):
            from vidknot.utils.config_manager import ConfigManager
            # Mock config to return empty key
            with patch.object(ConfigManager, "get", return_value=""):
                asr = SiliconFlowASR()
                with pytest.raises(NoAPIKeyError, match="SiliconFlow API Key 未设置"):
                    asr._get_client()

    def test_transcribe_empty_result_raises(self, temp_dir):
        """空转录结果应抛出 EmptyAudioError"""
        asr = SiliconFlowASR(api_key="test-key")
        valid_mp3 = temp_dir / "valid.mp3"
        valid_mp3.write_bytes(b"\x00" * 2048)  # 大于 1024 bytes

        mock_response = MagicMock()
        mock_response.text = "   "  # 空白字符

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        with patch.object(asr, "_get_client", return_value=mock_client):
            with pytest.raises(EmptyAudioError, match="云端转录结果为空"):
                asr.transcribe(str(valid_mp3))

    def test_transcribe_success(self, temp_dir):
        """正常转录返回文本"""
        asr = SiliconFlowASR(api_key="test-key")
        valid_mp3 = temp_dir / "valid.mp3"
        valid_mp3.write_bytes(b"\x00" * 2048)

        mock_response = MagicMock()
        mock_response.text = "  这是测试转录文本  "

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.return_value = mock_response

        with patch.object(asr, "_get_client", return_value=mock_client):
            result = asr.transcribe(str(valid_mp3))
        assert result == "这是测试转录文本"  # 已 strip

    def test_transcribe_wraps_api_errors(self, temp_dir):
        """API 异常应包装为 TranscriptionError"""
        asr = SiliconFlowASR(api_key="test-key")
        valid_mp3 = temp_dir / "valid.mp3"
        valid_mp3.write_bytes(b"\x00" * 2048)

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create.side_effect = Exception("API 503")

        with patch.object(asr, "_get_client", return_value=mock_client):
            with pytest.raises(TranscriptionError, match="硅基流动转录失败"):
                asr.transcribe(str(valid_mp3))


# ========== FasterWhisperASR 测试 ==========


class TestFasterWhisperASR:
    """测试 FasterWhisperASR 类"""

    def test_supports_common_audio_formats(self):
        """应支持常见的音频格式"""
        expected = {".mp3", ".m4a", ".wav", ".flac", ".wma"}
        assert expected.issubset(FasterWhisperASR.SUPPORTED_FORMATS)

    def test_default_config(self):
        """默认配置从 ConfigManager 读取"""
        asr = FasterWhisperASR()
        # 不调用 transcribe 之前不会触发 _get_config
        cfg = asr._get_config()
        # config.yaml 应包含 faster_whisper 块
        assert "model" in cfg
        assert "device" in cfg
        assert "compute_type" in cfg
        assert "beam_size" in cfg
        assert "vad_filter" in cfg

    def test_explicit_kwargs_override_config(self):
        """显式参数覆盖配置文件"""
        asr = FasterWhisperASR(
            model="medium", device="cuda", compute_type="float16",
            beam_size=10, vad_filter=False,
        )
        cfg = asr._get_config()
        assert cfg["model"] == "medium"
        assert cfg["device"] == "cuda"
        assert cfg["compute_type"] == "float16"
        assert cfg["beam_size"] == 10
        assert cfg["vad_filter"] is False

    def test_validate_audio_missing_file(self):
        """文件不存在应抛出 UnsupportedAudioFormatError"""
        asr = FasterWhisperASR()
        with pytest.raises(UnsupportedAudioFormatError, match="音频文件不存在"):
            asr._validate_audio(Path("/nonexistent/audio.mp3"))

    def test_validate_audio_unsupported_format(self, temp_dir):
        """不支持的格式应抛出 UnsupportedAudioFormatError"""
        asr = FasterWhisperASR()
        bad_file = temp_dir / "video.xyz"
        bad_file.write_bytes(b"\x00" * 2048)
        with pytest.raises(UnsupportedAudioFormatError):
            asr._validate_audio(bad_file)

    def test_transcribe_import_error(self, temp_dir):
        """faster-whisper 缺失应给出明确错误"""
        asr = FasterWhisperASR()
        valid_mp3 = temp_dir / "valid.mp3"
        valid_mp3.write_bytes(b"\x00" * 2048)

        # Mock _get_config 返回合法配置
        with patch.object(asr, "_get_config", return_value={
            "model": "small", "device": "cpu", "compute_type": "int8",
            "beam_size": 5, "vad_filter": True,
        }):
            # 通过 sys.modules 屏蔽 faster_whisper
            import sys
            with patch.dict(sys.modules, {"faster_whisper": None}):
                with pytest.raises(TranscriptionError, match="faster-whisper 未安装"):
                    asr.transcribe(str(valid_mp3))

    def test_transcribe_success(self, temp_dir):
        """正常转录返回带时间戳文本"""
        asr = FasterWhisperASR()
        valid_mp3 = temp_dir / "valid.mp3"
        valid_mp3.write_bytes(b"\x00" * 2048)

        # Mock WhisperModel + segments
        mock_segment = MagicMock()
        mock_segment.start = 0.0
        mock_segment.end = 3.4
        mock_segment.text = " 大家好  "

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], None)

        with patch.object(asr, "_get_config", return_value={
            "model": "small", "device": "cpu", "compute_type": "int8",
            "beam_size": 5, "vad_filter": True,
        }):
            with patch("faster_whisper.WhisperModel", return_value=mock_model):
                result = asr.transcribe(str(valid_mp3))

        assert "[   0.0s -    3.4s] 大家好" in result

    def test_transcribe_empty_segments_raises(self, temp_dir):
        """空 segments 应抛出 EmptyAudioError"""
        asr = FasterWhisperASR()
        valid_mp3 = temp_dir / "valid.mp3"
        valid_mp3.write_bytes(b"\x00" * 2048)

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], None)

        with patch.object(asr, "_get_config", return_value={
            "model": "small", "device": "cpu", "compute_type": "int8",
            "beam_size": 5, "vad_filter": True,
        }):
            with patch("faster_whisper.WhisperModel", return_value=mock_model):
                with pytest.raises(EmptyAudioError):
                    asr.transcribe(str(valid_mp3))


# ========== 工厂函数测试 ==========


class TestGetTranscriber:
    """测试 get_transcriber 工厂"""

    def test_get_siliconflow(self):
        asr = get_transcriber("siliconflow")
        assert isinstance(asr, SiliconFlowASR)

    def test_get_faster_whisper(self):
        asr = get_transcriber("faster_whisper")
        assert isinstance(asr, FasterWhisperASR)

    def test_unknown_provider_falls_back(self):
        """未知 provider 应回退到 siliconflow"""
        asr = get_transcriber("unknown_provider")
        assert isinstance(asr, SiliconFlowASR)