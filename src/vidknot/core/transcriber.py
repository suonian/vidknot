"""
VidkNot 语音转录模块

支持双 ASR 模式：
- SiliconFlowASR: 云端转录（基于阿里 SenseVoice）
- FasterWhisperASR: 本地 CPU 转录（基于 faster-whisper）

用法:
    from vidknot.core.transcriber import SiliconFlowASR, FasterWhisperASR

    # 云端
    transcriber = SiliconFlowASR()
    text = transcriber.transcribe("audio.mp3")

    # 本地
    transcriber = FasterWhisperASR()
    text_with_timestamps = transcriber.transcribe("audio.mp3")
"""

import os
from pathlib import Path
from typing import Optional

from ..utils.exceptions import (
    TranscriptionError,
    EmptyAudioError,
    UnsupportedAudioFormatError,
    NoAPIKeyError,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SiliconFlowASR:
    """
    硅基流动云端 ASR

    基于 OpenAI-compatible API，使用阿里 SenseVoice 模型。
    特点:
    - 中文识别快 5 倍+
    - 准确率 95%+
    - 自动标点
    - 支持多种语言
    """

    SUPPORTED_FORMATS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".webm", ".aac", ".amr", ".wma", ".mka"}

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "FunAudioLLM/SenseVoiceSmall",
    ):
        self.api_key = api_key
        self.model = model

    def _get_client(self):
        """获取 OpenAI-compatible 客户端"""
        from openai import OpenAI
        from ..utils.config_manager import ConfigManager

        if self.api_key:
            key = self.api_key.strip()
        else:
            config = ConfigManager()
            key = config.get("providers", "siliconflow", "api_key") or ""
            key = (key or os.getenv("SILICONFLOW_API_KEY", "")).strip()

        if not key:
            raise NoAPIKeyError(
                "SiliconFlow API Key 未设置，请配置 SILICONFLOW_API_KEY"
            )

        return OpenAI(
            api_key=key,
            base_url="https://api.siliconflow.cn/v1",
        )

    def _validate_audio(self, audio_path: Path) -> None:
        """验证音频文件"""
        if not audio_path.exists():
            raise UnsupportedAudioFormatError(f"音频文件不存在: {audio_path}")

        suffix = audio_path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise UnsupportedAudioFormatError(
                f"不支持的音频格式: {suffix}，支持的格式: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        size = audio_path.stat().st_size
        if size < 1024:
            raise EmptyAudioError(f"音频文件过小 ({size} bytes)，可能为空或损坏")

    def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = None,
        timeout: int = 300,
    ) -> str:
        """
        转录音频文件（云端模式）

        Args:
            audio_path: 音频文件路径
            language: 语言 (None=自动检测, zh/en/ja/ko/yue)
            timeout: 超时秒数

        Returns:
            转录文本
        """
        audio_path = Path(audio_path)
        self._validate_audio(audio_path)

        logger.info(f"[SiliconFlow] 开始云端转录: {audio_path.name} - {self.model}")

        client = self._get_client()

        try:
            with open(audio_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    model=self.model,
                    file=f,
                    timeout=timeout,
                )
            result = response.text

            if not result or not result.strip():
                raise EmptyAudioError(
                    "云端转录结果为空，可能是音频无语音内容",
                    details=f"文件: {audio_path.name}",
                )

            logger.info(f"[SiliconFlow] 转录完成: {len(result)} 字符")
            return result.strip()

        except EmptyAudioError:
            raise
        except Exception as e:
            raise TranscriptionError(
                f"硅基流动转录失败",
                details=f"model={self.model}, error={e}",
            )


def get_transcriber(provider: str = "siliconflow", **kwargs) -> "SiliconFlowASR | FasterWhisperASR":
    """
    获取转录器实例

    Args:
        provider: 转录提供者 ("siliconflow" 或 "faster_whisper")

    Returns:
        转录器实例
    """
    if provider == "faster_whisper":
        return FasterWhisperASR(**kwargs)
    elif provider == "siliconflow":
        return SiliconFlowASR(**kwargs)
    else:
        logger.warning(f"未知 provider '{provider}'，回退到 siliconflow")
        return SiliconFlowASR(**kwargs)


Transcriber = SiliconFlowASR


class FasterWhisperASR:
    """
    本地 faster-whisper ASR

    基于 Systran/faster-whisper-* 模型（CPU/GPU 通用）。
    特点:
    - 带时间戳分段输出（适合双 ASR 差异对齐）
    - 不依赖云端 API
    - 准确度依赖模型规模（small/medium/large-v3）

    配置项（来自 config.yaml 的 faster_whisper 块）:
      - model: small | medium | large-v3
      - device: cpu | cuda
      - compute_type: int8 | float16 | float32
      - beam_size: beam search 宽度（默认 5）
      - vad_filter: 是否启用 VAD 过滤静音（默认 True）
    """

    SUPPORTED_FORMATS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".webm", ".aac", ".amr", ".wma", ".mka"}

    def __init__(
        self,
        model: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        beam_size: Optional[int] = None,
        vad_filter: Optional[bool] = None,
    ):
        self.model = model
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.vad_filter = vad_filter

    def _get_config(self) -> dict:
        """从 ConfigManager 读 faster_whisper 配置"""
        from ..utils.config_manager import ConfigManager
        config = ConfigManager()
        cfg = config.get("faster_whisper") or {}
        return {
            "model": self.model or cfg.get("model", "small"),
            "device": self.device or cfg.get("device", "cpu"),
            "compute_type": self.compute_type or cfg.get("compute_type", "int8"),
            "beam_size": self.beam_size or cfg.get("beam_size", 5),
            "vad_filter": self.vad_filter if self.vad_filter is not None else cfg.get("vad_filter", True),
        }

    def _validate_audio(self, audio_path: Path) -> None:
        """验证音频文件"""
        if not audio_path.exists():
            raise UnsupportedAudioFormatError(f"音频文件不存在: {audio_path}")
        suffix = audio_path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise UnsupportedAudioFormatError(
                f"不支持的音频格式: {suffix}，支持的格式: {', '.join(self.SUPPORTED_FORMATS)}"
            )
        size = audio_path.stat().st_size
        if size < 1024:
            raise EmptyAudioError(f"音频文件过小 ({size} bytes)，可能为空或损坏")

    def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = "zh",
    ) -> str:
        """
        转录音频文件（本地模式），输出带时间戳的文本

        Args:
            audio_path: 音频文件路径
            language: 语言代码（默认 "zh"）

        Returns:
            带时间戳分段的文本，格式：
            "[  X.Xs -  Y.Ys] 文本"
        """
        audio_path = Path(audio_path)
        self._validate_audio(audio_path)

        cfg = self._get_config()
        logger.info(
            f"[FasterWhisper] 开始本地转录: {audio_path.name} "
            f"(model={cfg['model']}, device={cfg['device']}, compute_type={cfg['compute_type']})"
        )

        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(
                cfg["model"],
                device=cfg["device"],
                compute_type=cfg["compute_type"],
            )
            segments, _ = model.transcribe(
                str(audio_path),
                language=language,
                beam_size=cfg["beam_size"],
                vad_filter=cfg["vad_filter"],
            )

            out_lines = []
            for seg in segments:
                out_lines.append(f"[{seg.start:6.1f}s - {seg.end:6.1f}s] {seg.text.strip()}")

            result = "\n".join(out_lines)
            if not result.strip():
                raise EmptyAudioError(
                    "本地转录结果为空，可能是音频无语音内容",
                    details=f"文件: {audio_path.name}",
                )

            logger.info(f"[FasterWhisper] 转录完成: {len(result)} 字符, {len(out_lines)} 段")
            return result

        except EmptyAudioError:
            raise
        except ImportError:
            raise TranscriptionError(
                "faster-whisper 未安装",
                details="pip install faster-whisper",
            )
        except Exception as e:
            raise TranscriptionError(
                "本地 faster-whisper 转录失败",
                details=f"model={cfg['model']}, error={e}",
            )
