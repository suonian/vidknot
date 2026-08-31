"""
VidkNot 视频下载器

平台插件架构：
- 各平台下载策略位于 core/platforms/*.py（BasePlatform 插件）
- 本类提供共享下载工具（yt-dlp / FFmpeg / Cookie 管理）
- _download_sync() 委托给 PlatformRegistry.detect(url).download()

支持平台: YouTube, Bilibili, 抖音, 小红书, TikTok, Twitter/X,
快手, 微博, Vimeo, Instagram, 微信视频号, 通用 yt-dlp 兜底
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp

from ..utils.config_manager import ConfigManager
from ..utils.exceptions import AudioExtractError, DownloadError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VideoDownloader:
    """
    视频下载器

    下载策略由各平台插件（core/platforms/）实现，
    本类提供共享的 yt-dlp / FFmpeg / Cookie 工具。
    """

    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "vidknot"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._config = ConfigManager()

    def download_audio_with_metadata(
        self,
        url: str,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path | None, dict[str, Any]]:
        """下载视频音频并返回元数据（同步）

        Args:
            url: 视频 URL
            quality: 下载质量
            force_audio: 强制下载音频（跳过字幕优先策略）

        Returns:
            (audio_path, metadata)。字幕优先策略成功时 audio_path
            可能为 None，此时 metadata["subtitle_text"] 含转录文本。
        """
        return self._download_sync(url, quality, force_audio)

    def _download_sync(
        self, url: str, quality: str, force_audio: bool = False
    ) -> tuple[Path | None, dict[str, Any]]:
        """同步下载：委托给平台插件"""
        from .platforms import PlatformRegistry

        platform = PlatformRegistry.detect(url)
        logger.info(f"[Download] 平台: {platform.name}")
        return platform.download(url, self, quality, force_audio=force_audio)

    # ===== yt-dlp 通用下载 =====

    def _get_download_format(self, quality: str, platform: str) -> str:
        """获取下载格式，优先下载音频"""
        if platform == "youtube":
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif platform == "bilibili":
            return "bestaudio/best"
        else:
            return f"{quality}/best"

    def _get_js_runtime_path(self) -> str | None:
        """获取 JavaScript 运行时路径"""
        deno_path = os.path.expanduser("~/.deno/bin/deno.exe")
        if os.path.exists(deno_path):
            return deno_path
        import shutil

        return shutil.which("node")

    def _yt_dlp_download(
        self,
        url: str,
        quality: str,
        cookie_file: str | None = None,
        platform: str = "unknown",
    ) -> tuple[Path, dict[str, Any]]:
        """使用 yt-dlp 下载（内部通用方法）"""
        output_template = str(self.output_dir / f"{platform}_video.%(ext)s")

        ydl_opts: dict[str, Any] = {
            "format": self._get_download_format(quality, platform),
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "extract_audio": True,
            "audio_format": "mp3",
            "audioquality": "0",
            "prefer_ffmpeg": True,
            "gettitle": True,
            "getuploader": True,
            "getduration": True,
            "getthumbnail": True,
            "getdescription": True,
            "ignoreerrors": False,
            "no_color": True,
        }

        js_runtime = self._get_js_runtime_path()
        if js_runtime:
            ydl_opts["js_runtimes"] = {"deno": {"path": js_runtime}}
            logger.info(f"[yt-dlp] 使用 JS 运行时: {js_runtime}")

        from ..utils.env_check import get_ffmpeg_path

        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path:
            ydl_opts["ffmpeg_location"] = str(Path(ffmpeg_path).parent)

        if cookie_file and Path(cookie_file).exists():
            ydl_opts["cookiefile"] = cookie_file
            logger.info(f"[yt-dlp] 使用 Cookie: {cookie_file}")

        metadata: dict[str, Any] = {}
        audio_path: Path | None = None

        def hook(d: dict[str, Any]) -> None:
            nonlocal audio_path
            if d["status"] == "finished":
                audio_path = Path(d["filename"])
            elif d["status"] == "error":
                raise DownloadError(f"下载失败: {d.get('error', '未知错误')}")

        ydl_opts["progress_hooks"] = [hook]

        try:
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
                        "platform": platform,
                    }
                    if audio_path is None:
                        for ext in ["mp3", "m4a", "webm", "wav", "flac"]:
                            candidates = list(self.output_dir.glob(f"*{info.get('id', '')}.{ext}"))
                            if candidates:
                                audio_path = candidates[0]
                                break
        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e)
            if "cookies" in err_msg.lower() or "s_v_web_id" in err_msg:
                raise DownloadError(
                    f"Cookie 无效或已过期: {err_msg[-300:]}",
                    hint="请在浏览器中重新登录该平台，然后按 COOKIE_GUIDE.md 重新导出 Cookie",
                )
            raise DownloadError(f"yt-dlp 下载失败: {err_msg[-300:]}")

        if audio_path is None or not audio_path.exists():
            raise AudioExtractError("下载完成但未找到音频文件")

        return audio_path, metadata

    def _download_with_browser_cookie(self, url: str, quality: str, platform: str) -> tuple[Path, dict[str, Any]]:
        """使用浏览器 Cookie 下载（通过命令行）"""
        logger.info(f"[Download] 尝试使用浏览器 Cookie 下载: {platform}")

        from ..utils.env_check import get_ffmpeg_path
        from ..utils.retry import get_network_config

        download_timeout = get_network_config(self._config)["download_timeout"]

        output_path = self.output_dir / f"{platform}_video.%(ext)s"
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", "chrome",
            "-o", str(output_path),
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            url,
        ]

        ffmpeg_path = get_ffmpeg_path()
        if ffmpeg_path:
            cmd.extend(["--ffmpeg-location", str(Path(ffmpeg_path).parent)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=download_timeout,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise DownloadError(
                    f"yt-dlp 下载失败: {error_msg[-500:]}",
                    hint=(
                        "请确认已在 Chrome 中登录该平台；"
                        "或将 Cookie 导出为文件后放到 cookies/ 目录（见 COOKIE_GUIDE.md）"
                    ),
                )

            title = ""
            uploader = ""
            duration = 0

            for line in result.stdout.split("\n"):
                if "[download] Destination:" in line or "[download] Merging formats" in line:
                    continue

            audio_files = list(self.output_dir.glob(f"{platform}_video.*"))
            audio_files = [f for f in audio_files if f.suffix in [".mp3", ".m4a", ".webm", ".wav", ".flac"]]

            if not audio_files:
                video_files = list(self.output_dir.glob(f"{platform}_video.*"))
                if video_files:
                    audio_file = self._extract_audio(video_files[0], f"{platform}_video")
                    audio_files = [audio_file]

            if not audio_files:
                raise DownloadError("未找到下载的音频文件")

            audio_path = audio_files[0]

            info = result.stdout
            title_match = re.search(r"\[download\] (?:Destination|Merging formats)\s+(.+)", info)
            if not title_match:
                title = f"{platform}_video"

            metadata = {
                "title": title or f"{platform}_video",
                "uploader": uploader,
                "duration": duration,
                "thumbnail": "",
                "description": "",
                "url": url,
                "id": platform,
                "platform": platform,
            }

            logger.info(f"[Download] 下载完成: {audio_path.name}")
            return audio_path, metadata

        except subprocess.CalledProcessError as e:
            raise DownloadError(f"yt-dlp 下载失败: {e.stderr[-500:]}")
        except subprocess.TimeoutExpired as e:
            raise DownloadError(
                f"yt-dlp 下载超时（{download_timeout} 秒）",
                hint="请检查网络连接后重试；长视频可在 config.yaml network.download_timeout 中调大超时",
            ) from e
        except Exception as e:
            raise DownloadError(f"下载失败: {e}")

    # ===== 工具方法 =====

    def _extract_audio(self, video_path: Path, base_name: str) -> Path:
        """用 FFmpeg 将视频文件转换为音频"""
        from ..utils.env_check import get_ffmpeg_path
        from ..utils.exceptions import FFmpegNotFoundError
        from ..utils.retry import get_network_config

        ffmpeg_bin = get_ffmpeg_path()
        if not ffmpeg_bin:
            raise FFmpegNotFoundError("FFmpeg 未找到，无法转码音频")

        download_timeout = get_network_config(self._config)["download_timeout"]
        audio_path = self.output_dir / f"{base_name}.mp3"
        try:
            result = subprocess.run(
                [
                    ffmpeg_bin, "-y", "-i", str(video_path),
                    "-vn", "-acodec", "libmp3lame", "-q:a", "0",
                    str(audio_path),
                ],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=download_timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise AudioExtractError(
                f"FFmpeg 转码超时（{download_timeout} 秒）",
                hint="大文件转码耗时较长，可在 config.yaml network.download_timeout 中调大超时",
            ) from e
        if result.returncode != 0:
            raise AudioExtractError(f"FFmpeg 转换失败: {result.stderr[-200:]}")
        try:
            video_path.unlink()
        except Exception:
            pass
        return audio_path

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名禁止字符（含 emoji 等非 ASCII）"""
        import unicodedata
        name = unicodedata.normalize("NFKC", name)
        name = re.sub(r'[<>"/\\|?*\x00-\x1f]', "_", name, flags=0).strip()[:50]
        name = name.encode("ascii", "replace").decode("ascii")
        name = re.sub(r'[<>"/\\|?*\x00-\x1f]', "_", name, flags=0).strip()
        return name or "video"

    def _try_export_cookies(self, platform: str = "unknown") -> str | None:
        """尝试获取 Cookie 文件"""
        cookie_file = self._find_cookie_file(platform)
        if cookie_file:
            logger.info(f"[Cookie] 使用本地 Cookie 文件: {cookie_file}")
            return cookie_file

        try:
            import browser_cookie3
            temp_cookie_file = str(self.output_dir / "temp_cookies.txt")
            for name, getter in [
                ("chrome", lambda: browser_cookie3.chrome(domain_name=None)),
                ("firefox", lambda: browser_cookie3.firefox(domain_name=None)),
                ("edge", lambda: browser_cookie3.edge(domain_name=None)),
            ]:
                try:
                    cookies = getter()
                    if cookies:
                        with open(temp_cookie_file, "w", encoding="utf-8") as f:
                            for c in cookies:
                                f.write(
                                    f"{c.domain}\tTRUE\t{c.path}\t"
                                    f"{'TRUE' if c.expires > 0 else 'FALSE'}\t"
                                    f"{c.expires}\t{c.name}\t{c.value}\n"
                                )
                        return temp_cookie_file
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _find_cookie_file(self, platform: str) -> str | None:
        """查找本地 Cookie 文件"""
        project_root = Path(__file__).parent.parent.parent.parent
        cookie_dir = project_root / "cookies"

        platform_map = {
            "youtube": "youtube.txt",
            "bilibili": "bilibili.txt",
            "douyin": "douyin.txt",
            "xiaohongshu": "xiaohongshu.txt",
            "kuaishou": "kuaishou.txt",
            "weibo": "weibo.txt",
        }

        cookie_file_name = platform_map.get(platform)
        if not cookie_file_name:
            for name, filename in platform_map.items():
                cookie_path = cookie_dir / filename
                if cookie_path.exists():
                    return str(cookie_path)
            return None

        cookie_path = cookie_dir / cookie_file_name
        if cookie_path.exists():
            return str(cookie_path)

        generic_cookie = cookie_dir / f"{platform}.txt"
        if generic_cookie.exists():
            return str(generic_cookie)

        return None

    def _detect_platform(self, url: str) -> str:
        """检测视频平台（委托 PlatformRegistry，保留以兼容旧调用）"""
        from .platforms import PlatformRegistry

        platform = PlatformRegistry.detect(url)
        return "unknown" if platform.name == "generic" else platform.name
