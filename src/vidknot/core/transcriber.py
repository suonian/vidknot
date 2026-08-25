"""
VidkNot 语音转录模块

支持多种转录方式：
- SiliconFlowASR: 云端转录（基于阿里 SenseVoice）
- FasterWhisperASR: 本地 CPU 转录（基于 faster-whisper）
- OpenAITranscribeASR: OpenAI Whisper API 云端兜底转录
- SubtitleExtractor: 从 .srt/.vtt 字幕文件解析纯文本

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
import re
from pathlib import Path

from ..utils.exceptions import (
    EmptyAudioError,
    NoAPIKeyError,
    TranscriptionError,
    UnsupportedAudioFormatError,
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
        api_key: str | None = None,
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
        language: str | None = None,
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

            # 自动繁简转换 (Hermes 实战沉淀 2026-08-25):
            # 台湾/香港创作者视频源是繁体中文, SF 输出的繁体字需要转简体
            # 以便后续 LLM 提取和存储使用统一编码
            if self._is_likely_traditional(result):
                result = self._convert_traditional_to_simplified(result)

            logger.info(f"[SiliconFlow] 转录完成: {len(result)} 字符")
            return result.strip()

        except EmptyAudioError:
            raise
        except Exception as e:
            raise TranscriptionError(
                "硅基流动转录失败",
                details=f"model={self.model}, error={e}",
            )

    @staticmethod
    def _is_likely_traditional(text: str) -> bool:
        """检测文本是否可能是繁体中文 (启发式)

        启发式: 包含多个繁体特征字 (經 學 聲 變 對 等) 但简体对应字 (经 学 声 变 对) 出现频次低
        """
        # 简体字远少于对应繁体字 = 极可能是繁体
        trad_chars = "經學聲變對電腦語言頭條開發數據"
        simp_chars = "经学声变对电脑语言头条开发数据"
        trad_count = sum(text.count(c) for c in trad_chars)
        simp_count = sum(text.count(c) for c in simp_chars)
        return trad_count >= 5 and trad_count > simp_count * 2

    @staticmethod
    def _convert_traditional_to_simplified(text: str) -> str:
        """OpenCC t2s 转换（需 opencc-python-reimplemented 包）

        优雅降级: opencc 不可用时跳过转换, 不影响主流程
        """
        try:
            import opencc
            converter = opencc.OpenCC("t2s")
            return converter.convert(text)
        except ImportError:
            logger.warning(
                "[SiliconFlow] opencc-python-reimplemented 未安装, 跳过繁简转换. "
                "pip install opencc-python-reimplemented 启用此功能."
            )
            return text


def get_transcriber(provider: str = "siliconflow", **kwargs):
    """
    获取转录器实例

    Args:
        provider: 转录提供者 ("siliconflow" / "faster_whisper" / "openai_whisper")

    Returns:
        转录器实例
    """
    if provider == "faster_whisper":
        return FasterWhisperASR(**kwargs)
    elif provider == "openai_whisper":
        return OpenAITranscribeASR(**kwargs)
    elif provider == "siliconflow":
        return SiliconFlowASR(**kwargs)
    else:
        logger.warning(f"未知 provider '{provider}'，回退到 siliconflow")
        return SiliconFlowASR(**kwargs)


Transcriber = SiliconFlowASR


class SubtitleExtractor:
    """
    字幕文件解析器

    从 yt-dlp 提取的字幕文件（.srt/.vtt）中解析纯文本，
    去除序号、时间轴和格式标记。
    """

    SUPPORTED_FORMATS = {".srt", ".vtt"}

    def extract(self, subtitle_path: str | Path) -> str:
        """
        解析字幕文件为纯文本

        Args:
            subtitle_path: 字幕文件路径 (.srt 或 .vtt)

        Returns:
            纯文本转录内容
        """
        subtitle_path = Path(subtitle_path)
        if not subtitle_path.exists():
            raise TranscriptionError(f"字幕文件不存在: {subtitle_path}")

        suffix = subtitle_path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise TranscriptionError(
                f"不支持的字幕格式: {suffix}，支持: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        content = subtitle_path.read_text(encoding="utf-8", errors="replace")
        return self._parse(content)

    def _parse(self, content: str) -> str:
        """解析字幕内容为纯文本（去重 + 去格式标记）"""
        lines: list[str] = []
        seen: set[str] = set()

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # 跳过序号行、时间轴行、VTT 头部/样式标记
            if re.fullmatch(r"\d+", line):
                continue
            if "-->" in line:
                continue
            if line.startswith(("WEBVTT", "NOTE", "STYLE", "Kind:", "Language:")):
                continue
            if re.fullmatch(r"\d{2}:\d{2}:\d{2}[.,]\d{3}", line):
                continue
            # 去除内嵌标记：<c>、</c>、<00:00:01.000>、{\an8} 等
            line = re.sub(r"<[^>]+>", "", line)
            line = re.sub(r"\{[^}]*\}", "", line).strip()
            if not line or line in seen:
                continue
            seen.add(line)
            lines.append(line)

        return " ".join(lines).strip()


class OpenAITranscribeASR:
    """
    OpenAI Whisper API 云端兜底转录（$0.006/分钟）

    配置项（来自 config.yaml 的 providers.openai 块）:
      - api_key: OpenAI API Key（或环境变量 OPENAI_API_KEY）
      - base_url: API 基地址（默认 https://api.openai.com/v1）
      - whisper_model: 转录模型（默认 whisper-1）
    """

    # OpenAI Whisper API 支持的格式
    SUPPORTED_FORMATS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key
        self.model = model

    def _get_client(self):
        """获取 OpenAI 客户端"""
        from openai import OpenAI

        from ..utils.config_manager import ConfigManager

        config = ConfigManager()
        key = self.api_key or config.get("providers", "openai", "api_key") or ""
        key = key.strip()

        if not key or key.startswith("YOUR_"):
            raise NoAPIKeyError(
                "OpenAI API Key 未设置，请配置 providers.openai.api_key 或 OPENAI_API_KEY"
            )

        base_url = config.get("providers", "openai", "base_url") or "https://api.openai.com/v1"
        return OpenAI(api_key=key, base_url=base_url)

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
        language: str | None = None,
    ) -> str:
        """
        转录音频文件（OpenAI Whisper API）

        Args:
            audio_path: 音频文件路径
            language: 语言代码（可选，None=自动检测）

        Returns:
            转录文本
        """
        audio_path = Path(audio_path)
        self._validate_audio(audio_path)

        from ..utils.config_manager import ConfigManager

        config = ConfigManager()
        model = self.model or config.get(
            "providers", "openai", "whisper_model", default="whisper-1"
        )

        logger.info(f"[OpenAI Whisper] 开始云端转录: {audio_path.name} - {model}")

        client = self._get_client()

        try:
            with open(audio_path, "rb") as f:
                kwargs = {"model": model, "file": f}
                # language 需要 ISO-639-1 主代码
                if language and language != "auto":
                    kwargs["language"] = language.split("-")[0][:2]
                response = client.audio.transcriptions.create(**kwargs)
            result = response.text

            if not result or not result.strip():
                raise EmptyAudioError(
                    "OpenAI Whisper 转录结果为空，可能是音频无语音内容",
                    details=f"文件: {audio_path.name}",
                )

            logger.info(f"[OpenAI Whisper] 转录完成: {len(result)} 字符")
            return result.strip()

        except EmptyAudioError:
            raise
        except NoAPIKeyError:
            raise
        except Exception as e:
            raise TranscriptionError(
                "OpenAI Whisper 转录失败",
                details=f"model={model}, error={e}",
            )


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
        model: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        beam_size: int | None = None,
        vad_filter: bool | None = None,
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
        language: str | None = "zh",
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
