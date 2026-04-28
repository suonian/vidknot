"""
VidkNot 语音转录模块

基于 SiliconFlow 云端 ASR：
- 使用阿里 SenseVoice 模型
- 中文识别准确率 95%+
- 速度快（约 20 秒处理 7MB 音频）

用法:
    from vidknot.core.transcriber import SiliconFlowASR
    transcriber = SiliconFlowASR()
    text = transcriber.transcribe("audio.mp3")
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


def get_transcriber(provider: str = "siliconflow", **kwargs) -> SiliconFlowASR:
    """
    获取转录器实例

    Args:
        provider: 转录提供者（仅支持 "siliconflow"）

    Returns:
        SiliconFlowASR 实例
    """
    if provider == "siliconflow":
        return SiliconFlowASR(**kwargs)
    else:
        logger.warning(f"本地 ASR 已移除，使用云端模式: siliconflow")
        return SiliconFlowASR(**kwargs)


Transcriber = SiliconFlowASR
