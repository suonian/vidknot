"""
平台插件基类

所有视频平台插件继承 BasePlatform，实现 download() 方法。
YtDlpPlatform 提供基于 yt-dlp 的通用下载实现，大部分平台可直接继承。

平台插件通过 dl 参数（VideoDownloader 实例）访问共享下载工具：
- dl.output_dir: 输出目录
- dl._yt_dlp_download(): yt-dlp 下载
- dl._extract_audio(): FFmpeg 音频提取
- dl._try_export_cookies(): Cookie 导出
- dl._config: ConfigManager 实例
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ...utils.logger import get_logger

logger = get_logger(__name__)


class BasePlatform(ABC):
    """平台插件抽象基类"""

    #: 平台名称（唯一标识）
    name: str = "unknown"

    #: URL 匹配域名列表（小写子串匹配）
    domains: list[str] = []

    def can_handle(self, url: str) -> bool:
        """检测 URL 是否属于本平台"""
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.domains)

    @abstractmethod
    def download(
        self,
        url: str,
        dl: Any,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path | None, dict[str, Any]]:
        """
        下载并返回 (audio_path, metadata)

        Args:
            url: 视频 URL
            dl: VideoDownloader 实例（提供共享下载工具）
            quality: 下载质量
            force_audio: 强制下载音频（跳过字幕优先等捷径）

        Returns:
            (audio_path, metadata) 元组。
            audio_path 可为 None —— 当平台通过字幕直接提供了
            转录文本（metadata["subtitle_text"]）且无需音频时。
        """
        raise NotImplementedError

    def fetch_subtitle(self, url: str, dl: Any) -> str | None:
        """尝试直接获取字幕文本（默认不支持，返回 None）"""
        return None


class YtDlpPlatform(BasePlatform):
    """
    基于 yt-dlp 的通用平台实现

    大部分平台直接继承此类即可，仅需设置 name/domains。
    需要浏览器 Cookie 的平台（如 YouTube/TikTok）设置
    use_browser_cookie = True。
    """

    #: 是否使用浏览器 Cookie（yt-dlp --cookies-from-browser chrome）
    use_browser_cookie: bool = False

    #: 自定义 yt-dlp format（None = 默认音频优先）
    download_format: str | None = None

    def download(
        self,
        url: str,
        dl: Any,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path | None, dict[str, Any]]:
        if self.use_browser_cookie:
            logger.info(f"[{self.name}] 使用浏览器 Cookie 下载")
            return dl._download_with_browser_cookie(url, quality, self.name)

        cookie_file = dl._try_export_cookies(self.name)
        logger.info(f"[{self.name}] Cookie: {cookie_file or '无'}")
        try:
            return dl._yt_dlp_download(url, quality, cookie_file, self.name)
        finally:
            if cookie_file and "temp_cookies" in cookie_file and Path(cookie_file).exists():
                try:
                    Path(cookie_file).unlink()
                except Exception:
                    pass
