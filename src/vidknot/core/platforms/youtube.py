"""
YouTube 平台插件

三级转录策略：
1. youtube-transcript-api — 直接拉取官方字幕（零成本、最准确）
2. yt-dlp 字幕提取 — --write-sub --write-auto-sub
3. yt-dlp 音频下载 + ASR — 兜底
"""

import re
from pathlib import Path
from typing import Any

from ...utils.logger import get_logger
from .base import BasePlatform
from .subtitle_utils import fetch_ytdlp_subtitles

logger = get_logger(__name__)


class YouTubePlatform(BasePlatform):
    """YouTube 平台：字幕优先策略"""

    name = "youtube"
    domains = ["youtube.com", "youtu.be"]

    def download(
        self,
        url: str,
        dl: Any,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path | None, dict[str, Any]]:
        prefer_subtitles = dl._config.get(
            "platforms", "youtube", "prefer_subtitles", default=True
        )
        languages = dl._config.get(
            "platforms", "youtube", "subtitle_languages", default=["zh", "en", "ja", "ko"]
        ) or ["zh", "en", "ja", "ko"]

        if force_audio or not prefer_subtitles:
            # 显式 force_audio 或 prefer_subtitles=False 时: 直接走最稳的路径
            # (跳过 SABR-only bypass, 因为 force_audio 是用户显式强制, 应该走最可靠的 Cookie 嗅探)
            return self._download_audio_direct(url, dl, quality)

        # ---- Level 1: youtube-transcript-api ----
        try:
            segments = self._fetch_via_transcript_api(url, languages)
            if segments:
                text = " ".join(s["text"] for s in segments).strip()
                metadata = self._fetch_metadata_only(url, dl)
                metadata["subtitle_text"] = text
                metadata["subtitle_segments"] = segments
                metadata["transcription_source"] = "youtube_transcript_api"
                logger.info(f"[YouTube] Level1 成功: youtube-transcript-api ({len(text)} 字符)")
                return None, metadata
        except Exception as e:
            logger.warning(f"[YouTube] Level1 (transcript-api) 失败: {str(e)[:150]}")

        # ---- Level 2: yt-dlp 字幕提取 ----
        try:
            cookie_file = dl._find_cookie_file("youtube")
            text, metadata = fetch_ytdlp_subtitles(
                url, dl.output_dir, "youtube", languages,
                cookie_file=cookie_file, browser_cookie=cookie_file is None,
            )
            if text:
                metadata["subtitle_text"] = text
                metadata["transcription_source"] = "yt_dlp_subtitle"
                logger.info(f"[YouTube] Level2 成功: yt-dlp 字幕 ({len(text)} 字符)")
                return None, metadata
        except Exception as e:
            logger.warning(f"[YouTube] Level2 (yt-dlp 字幕) 失败: {str(e)[:150]}")

        # ---- Level 3: 音频下载 + ASR 兜底 ----
        logger.info("[YouTube] 无可用字幕，回退到音频下载 + ASR")
        return self._download_audio(url, dl, quality)

    def fetch_subtitle(self, url: str, dl: Any) -> str | None:
        """仅获取字幕文本（Level 1 + Level 2）"""
        languages = dl._config.get(
            "platforms", "youtube", "subtitle_languages", default=["zh", "en", "ja", "ko"]
        ) or ["zh", "en", "ja", "ko"]
        try:
            segments = self._fetch_via_transcript_api(url, languages)
            if segments:
                return " ".join(s["text"] for s in segments).strip()
        except Exception as e:
            logger.warning(f"[YouTube] transcript-api 失败: {str(e)[:150]}")
        try:
            cookie_file = dl._find_cookie_file("youtube")
            text, _ = fetch_ytdlp_subtitles(
                url, dl.output_dir, "youtube", languages,
                cookie_file=cookie_file, browser_cookie=cookie_file is None,
            )
            return text
        except Exception:
            return None

    def _download_audio(self, url: str, dl: Any, quality: str) -> tuple[Path, dict[str, Any]]:
        """Level 3: 下载音频 (字幕提取失败后的 fallback)

        优先级 (Hermes 实战沉淀, 2026-08-25):
        1. 本地 cookies/youtube.txt 文件
        2. **--extractor-args "youtube:player_client=android,web"** 绕过 Chrome cookies
           (yt-dlp 2026+ 默认 SABR-only 必须用此参数, 否则 web client 拒签)
        """
        cookie_file = dl._find_cookie_file("youtube")

        # 优先 1: 显式 cookie 文件
        if cookie_file:
            try:
                return dl._yt_dlp_download(url, quality, cookie_file, "youtube")
            except Exception as e:
                logger.warning(f"[YouTube] Cookie 文件失败 ({str(e)[:100]}), 回退到无 cookie 模式")

        # 优先 2: 无 cookie + SABR-only 兼容 (新增)
        logger.info("[YouTube] 无本地 Cookie，使用 SABR-only 兼容 extractor-args")
        try:
            return self._download_audio_no_cookie(url, dl, quality)
        except Exception as e:
            logger.warning(f"[YouTube] 无 Cookie 模式失败 ({str(e)[:100]}), 回退到浏览器 Cookie 嗅探")
            return dl._download_with_browser_cookie(url, quality, "youtube")

    def _download_audio_direct(self, url: str, dl: Any, quality: str) -> tuple[Path, dict[str, Any]]:
        """force_audio / prefer_subtitles=False 时的直接下载路径

        Hermes 实战沉淀: 用户显式 force_audio=True 时, 不需要 SABR-only bypass
        试探, 直接走 Cookie 嗅探 (最稳定, 因为 force_audio 是显式请求).
        """
        cookie_file = dl._find_cookie_file("youtube")
        if cookie_file:
            return dl._yt_dlp_download(url, quality, cookie_file, "youtube")
        return dl._download_with_browser_cookie(url, quality, "youtube")

    def _download_audio_no_cookie(
        self, url: str, dl: Any, quality: str
    ) -> tuple[Path, dict[str, Any]]:
        """Level 3 fallback: 无 Cookie 下载（绕过 SABR-only 限制）

        Hermes 实战沉淀 (2026-08-25): Lin Lili @linliliya AI 大模型科普课 7 条
        全部用此模式跑通。关键参数:
        - `--extractor-args "youtube:player_client=android,web"` 指定 Android + Web client
        - 跳过 web client 默认的 SABR-only streaming 限制
        - 不需要浏览器 Cookie
        """
        import yt_dlp

        output_template = str(dl.output_dir / "youtube_video.%(ext)s")

        ydl_opts: dict[str, Any] = {
            "format": "18/bestaudio/best",  # format 18 = legacy mp4 480p, 兜底
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "ignoreerrors": False,
            # 关键: 绕过 Chrome cookies + SABR-only
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
        }

        from ...utils.env_check import get_ffmpeg_path

        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path:
            ydl_opts["ffmpeg_location"] = str(Path(ffmpeg_path).parent)

        metadata: dict[str, Any] = {}
        audio_path: Path | None = None

        def hook(d: dict[str, Any]) -> None:
            nonlocal audio_path
            if d["status"] == "finished":
                # yt-dlp 会把 ext 改成 .mp3 (FFmpegExtractAudio postprocessor)
                audio_path = Path(d["filename"]).with_suffix(".mp3")

        ydl_opts["progress_hooks"] = [hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                metadata = {
                    "title": info.get("title", ""),
                    "uploader": info.get("uploader", ""),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "description": info.get("description", ""),
                    "url": url,
                    "id": info.get("id", ""),
                    "platform": "youtube",
                    "transcription_source": "yt_dlp_sabr_bypass",
                }
                if audio_path is None or not audio_path.exists():
                    # Fallback: 按 video_id 找
                    for ext in ["mp3", "m4a", "webm", "wav", "flac"]:
                        candidates = list(dl.output_dir.glob(f"*{info.get('id', '')}.{ext}"))
                        if candidates:
                            audio_path = candidates[0]
                            break

        if audio_path is None or not audio_path.exists():
            from ..utils.exceptions import AudioExtractError
            raise AudioExtractError("SABR-only bypass 下载完成但未找到音频文件")

        logger.info(f"[YouTube] SABR-only bypass 成功: {audio_path.name}")
        return audio_path, metadata


    def _fetch_metadata_only(self, url: str, dl: Any) -> dict[str, Any]:
        """仅提取元数据（不下载）"""
        import yt_dlp

        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "ignoreerrors": True,
        }
        cookie_file = dl._find_cookie_file("youtube")
        if cookie_file and Path(cookie_file).exists():
            ydl_opts["cookiefile"] = cookie_file
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return {
                        "title": info.get("title", ""),
                        "uploader": info.get("uploader", ""),
                        "duration": info.get("duration", 0),
                        "thumbnail": info.get("thumbnail", ""),
                        "description": info.get("description", ""),
                        "url": url,
                        "id": info.get("id", ""),
                        "platform": "youtube",
                    }
        except Exception as e:
            logger.warning(f"[YouTube] 元数据提取失败: {str(e)[:150]}")
        return {"title": "", "url": url, "platform": "youtube"}

    def _fetch_via_transcript_api(
        self, url: str, languages: list[str]
    ) -> list[dict[str, Any]] | None:
        """Level 1: 使用 youtube-transcript-api 拉取官方字幕（含时间戳）

        Returns:
            [{"start": float, "end": float, "text": str}, ...] 或 None
        """
        video_id = self._extract_video_id(url)
        if not video_id:
            logger.warning(f"[YouTube] 无法从 URL 提取 video_id: {url}")
            return None

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            logger.warning("[YouTube] youtube-transcript-api 未安装，跳过 Level1")
            return None

        def _normalize(raw_segments) -> list[dict[str, Any]]:
            result = []
            for seg in raw_segments:
                if hasattr(seg, "text"):
                    start = float(getattr(seg, "start", 0.0))
                    duration = float(getattr(seg, "duration", 0.0))
                    text = seg.text
                else:
                    start = float(seg.get("start", 0.0))
                    duration = float(seg.get("duration", 0.0))
                    text = seg.get("text", "")
                result.append({"start": start, "end": start + duration, "text": text})
            return result

        try:
            # 新版 API (>=1.0): 实例方法 fetch()
            fetched = YouTubeTranscriptApi().fetch(video_id, languages=languages)
            segments = _normalize(list(fetched))
            return segments or None
        except TypeError:
            # 旧版 API (<1.0): 类方法 get_transcript()
            try:
                segments = _normalize(
                    YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
                )
                return segments or None
            except Exception as e:
                logger.debug(f"[YouTube] get_transcript 失败: {str(e)[:150]}")
                return None
        except Exception as e:
            err = str(e)
            logger.debug(f"[YouTube] fetch 失败: {err[:150]}")
            # 新版 API 的异常对象可能直接包含可用字幕信息，尝试 list_transcripts
            try:
                api = YouTubeTranscriptApi()
                transcript_list = api.list(video_id)
                for transcript in transcript_list:
                    fetched = transcript.fetch()
                    segments = _normalize(list(fetched))
                    if segments:
                        return segments
            except Exception:
                return None
            return None

    @staticmethod
    def _extract_video_id(url: str) -> str | None:
        """从各种 YouTube URL 格式提取 video_id"""
        patterns = [
            r"[?&]v=([-\w]{11})",          # youtube.com/watch?v=xxx
            r"youtu\.be/([-\w]{11})",       # youtu.be/xxx
            r"/shorts/([-\w]{11})",         # youtube.com/shorts/xxx
            r"/embed/([-\w]{11})",          # youtube.com/embed/xxx
            r"/live/([-\w]{11})",           # youtube.com/live/xxx
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
