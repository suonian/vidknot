"""
TikTok 平台插件

策略（按优先级）：
1. cobalt API（可选，配置 platforms.tiktok.cobalt_api_url）
2. yt-dlp + 浏览器 Cookie

Evil0ctal/Douyin_TikTok_Download_API 预留（配置 platforms.tiktok.api_base_url）。
"""

from pathlib import Path
from typing import Any

from ...utils.exceptions import DownloadError
from ...utils.logger import get_logger
from .base import YtDlpPlatform

logger = get_logger(__name__)


class TikTokPlatform(YtDlpPlatform):
    """TikTok 国际版"""

    name = "tiktok"
    domains = ["tiktok.com"]
    use_browser_cookie = True

    def download(
        self,
        url: str,
        dl: Any,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path | None, dict[str, Any]]:
        # 可选 cobalt API 优先（需自行配置 API 地址）
        cobalt_url = dl._config.get("platforms", "tiktok", "cobalt_api_url")
        if cobalt_url:
            try:
                return self._download_via_cobalt(url, dl, cobalt_url)
            except Exception as e:
                logger.warning(f"[TikTok] cobalt API 失败: {str(e)[:150]}，回退 yt-dlp")

        return super().download(url, dl, quality, force_audio)

    def _download_via_cobalt(self, url: str, dl: Any, cobalt_url: str) -> tuple[Path, dict[str, Any]]:
        """通过 cobalt API 获取视频直链并下载"""
        import httpx

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                cobalt_url,
                json={"url": url, "downloadMode": "audio", "filenameStyle": "basic"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") not in ("tunnel", "redirect", "stream"):
            raise DownloadError(f"cobalt 返回异常状态: {data.get('status')}: {str(data)[:200]}")

        media_url = data.get("url")
        if not media_url:
            raise DownloadError("cobalt 未返回媒体地址")

        logger.info(f"[TikTok] cobalt 获取到媒体地址: {media_url[:80]}...")

        video_path = dl.output_dir / "tiktok_cobalt.mp4"
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            with client.stream("GET", media_url) as resp:
                resp.raise_for_status()
                with open(video_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        f.write(chunk)

        # cobalt downloadMode=audio 时可能直接是音频
        if video_path.stat().st_size > 0 and video_path.suffix == ".mp4":
            try:
                audio_path = dl._extract_audio(video_path, "tiktok_cobalt")
            except Exception:
                # 可能本身就是音频文件
                audio_path = video_path.rename(video_path.with_suffix(".mp3"))
        else:
            audio_path = video_path

        metadata = {
            "title": "tiktok_video_cobalt",
            "uploader": "",
            "duration": 0,
            "thumbnail": "",
            "url": url,
            "id": "tiktok_cobalt",
            "platform": "tiktok",
        }
        return audio_path, metadata
