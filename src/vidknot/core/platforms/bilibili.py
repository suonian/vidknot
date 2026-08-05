"""
Bilibili（B站）平台插件

策略：
1. 优先提取 CC 字幕（yt-dlp --write-subs，配置 platforms.bilibili.prefer_subtitles）
2. 失败后 fallback 到 yt-dlp 音频下载 + ASR
"""

from pathlib import Path
from typing import Any

from ...utils.logger import get_logger
from .base import BasePlatform
from .subtitle_utils import fetch_ytdlp_subtitles

logger = get_logger(__name__)


class BilibiliPlatform(BasePlatform):
    """B站平台：字幕优先 + 音频兜底"""

    name = "bilibili"
    domains = ["bilibili.com", "b23.tv"]

    def download(
        self,
        url: str,
        dl: Any,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path | None, dict[str, Any]]:
        prefer_subtitles = dl._config.get(
            "platforms", "bilibili", "prefer_subtitles", default=True
        )

        if not force_audio and prefer_subtitles:
            try:
                text, metadata = self._fetch_subtitles(url, dl)
                if text:
                    metadata["subtitle_text"] = text
                    metadata["transcription_source"] = "bilibili_cc_subtitle"
                    logger.info(f"[Bilibili] 字幕提取成功 ({len(text)} 字符)")
                    return None, metadata
            except Exception as e:
                logger.warning(f"[Bilibili] 字幕提取失败: {str(e)[:150]}")

        # 音频下载兜底（浏览器 Cookie）
        logger.info("[Bilibili] 回退到音频下载 + ASR")
        cookie_file = dl._find_cookie_file("bilibili")
        if cookie_file:
            return dl._yt_dlp_download(url, quality, cookie_file, "bilibili")
        return dl._download_with_browser_cookie(url, quality, "bilibili")

    def fetch_subtitle(self, url: str, dl: Any) -> str | None:
        """仅获取 CC 字幕文本"""
        try:
            text, _ = self._fetch_subtitles(url, dl)
            return text
        except Exception:
            return None

    def _fetch_subtitles(self, url: str, dl: Any) -> tuple[str | None, dict[str, Any]]:
        """提取 B站 CC 字幕"""
        languages = dl._config.get(
            "platforms", "bilibili", "subtitle_languages", default=["zh-CN", "zh", "en"]
        ) or ["zh-CN", "zh", "en"]
        cookie_file = dl._find_cookie_file("bilibili")
        return fetch_ytdlp_subtitles(
            url, dl.output_dir, "bilibili", languages,
            cookie_file=cookie_file, browser_cookie=cookie_file is None,
        )
