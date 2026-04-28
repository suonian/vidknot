"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot 视频下载器

多策略下载（三层 Fallback）：
┌─────────────────────────────────────────────────────────────┐
│ 第一层: 无 Cookie 快速解析（curl_cffi/httpx + 移动端指纹）     │
│  - 使用 douyin_parser 解析视频直链                            │
│  - 直接下载（最快路径，0 用户干预）                           │
│  - 若成功 → 直接返回                                         │
│  - 若失败 → 自动进入第二层                                   │
├─────────────────────────────────────────────────────────────┤
│ 第二层: Cookie 解析通道（yt-dlp Python API）                  │
│  - 自动获取 Cookie（文件 / CDP / browser_cookie3）            │
│  - 使用 yt-dlp 提取器（最成熟，自动处理签名/重定向）          │
│  - 若成功 → 下载完成                                         │
│  - 若失败 → 自动进入第三层                                   │
├─────────────────────────────────────────────────────────────┤
│ 第三层: 第三方 API 兜底                                       │
│  - apibyte → 残像API → ALAPI → TikHub（按优先级）             │
│  - 获取视频直链后下载                                        │
│  - 若全部失败 → 返回详细错误报告                             │
└─────────────────────────────────────────────────────────────┘

支持平台: YouTube, Bilibili, 抖音, Twitter/X, Vimeo, Instagram 等
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List

import yt_dlp

from ..utils.config_manager import ConfigManager
from ..utils.exceptions import DownloadError, AudioExtractError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class VideoDownloader:
    """
    视频下载器

    抖音使用三层 fallback 策略，其他平台统一使用 yt-dlp。
    """

    # 第三方 API 配置（按优先级）
    DEFAULT_THIRD_PARTY_APIS = [
        {
            "name": "apibyte",
            "url": "https://apibyte.cn/api/douyinparse",
            "method": "GET",
            "param_name": "url",
            "response_path": ["data", "video_url"],
            "timeout": 15,
        },
        {
            "name": "canxiang",
            "url": "https://apicx.asia/api/douyin_parser",
            "method": "GET",
            "param_name": "url",
            "response_path": ["data", "url"],
            "timeout": 15,
        },
        {
            "name": "alapi",
            "url": "https://www.alapi.cn/api/68/",
            "method": "GET",
            "param_name": "url",
            "response_path": ["data", "video_url"],
            "timeout": 15,
        },
    ]

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "vidknot"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._config = ConfigManager()

    def download_audio_with_metadata(
        self,
        url: str,
        quality: str = "bestaudio/best",
    ) -> Tuple[Path, Dict[str, Any]]:
        """下载视频音频并返回元数据（同步）"""
        return self._download_sync(url, quality)

    def _download_sync(self, url: str, quality: str) -> Tuple[Path, Dict[str, Any]]:
        """同步下载"""
        platform = self._detect_platform(url)

        # 抖音使用三层 fallback
        if platform == "douyin":
            return self._download_douyin_with_fallback(url, quality)

        # 小红书特殊处理：优先下载图片（纯图片笔记）
        if platform == "xiaohongshu":
            try:
                return self._download_xiaohongshu_images(url)
            except Exception as e:
                logger.warning(f"[XiaoHongShu] 图片下载失败: {e}，尝试视频下载...")

        # 其他平台使用 yt-dlp
        return self._download_yt_dlp_sync(url, quality)

    # ===== 抖音三层 Fallback =====

    def _download_douyin_with_fallback(self, url: str, quality: str) -> Tuple[Path, Dict[str, Any]]:
        """抖音下载：三层 fallback 策略"""
        errors: List[str] = []

        # ---- 第一层: 无 Cookie 快速解析 ----
        try:
            logger.info(f"[Douyin] 第一层: 尝试无 Cookie 解析...")
            return self._layer1_parse_and_download(url)
        except Exception as e:
            err = f"第一层(无Cookie解析): {str(e)[:200]}"
            errors.append(err)
            logger.warning(f"[Douyin] {err}")

        # ---- 第二层: yt-dlp + Cookie ----
        try:
            logger.info(f"[Douyin] 第二层: 尝试 yt-dlp + Cookie...")
            return self._layer2_yt_dlp_with_cookie(url, quality)
        except Exception as e:
            err = f"第二层(yt-dlp+Cookie): {str(e)[:200]}"
            errors.append(err)
            logger.warning(f"[Douyin] {err}")

        # ---- 第三层: 第三方 API ----
        if self._config.get("douyin", "enable_third_party", default=False):
            try:
                logger.info(f"[Douyin] 第三层: 尝试第三方 API...")
                return self._layer3_third_party_api(url, quality)
            except Exception as e:
                err = f"第三方API: {str(e)[:200]}"
                errors.append(err)
                logger.warning(f"[Douyin] {err}")

        # ---- 全部失败 ----
        error_report = "\n".join(f"  - {e}" for e in errors)
        raise DownloadError(
            f"抖音视频下载失败，所有策略均已尝试:\n{error_report}\n\n"
            f"建议:\n"
            f"1. 导出浏览器 Cookie 为 Netscape 格式保存到 cookies/douyin.txt\n"
            f"2. 或开启浏览器 Remote Debugging 端口让 CDP 自动获取\n"
            f"3. 或在 config.yaml 中配置第三方 API Key"
        )

    def _layer1_parse_and_download(self, url: str) -> Tuple[Path, Dict[str, Any]]:
        """第一层: 使用 douyin_parser 解析直链并下载"""
        from . import douyin_parser

        info = douyin_parser.parse(url)
        video_url = info.get("video_url", "")
        if not video_url:
            raise DownloadError("解析成功但未获取到视频地址")

        logger.info(f"[Douyin-L1] 获取到视频地址: {video_url[:80]}...")

        # 使用 httpx 下载视频
        import httpx

        video_path = self.output_dir / f"douyin_{info.get('author', 'unknown')}_{self._sanitize_filename(info.get('title', 'video'))}.mp4"
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            with client.stream("GET", video_url, headers={"User-Agent": douyin_parser.ANDROID_CHROME_UA}) as resp:
                resp.raise_for_status()
                with open(video_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        f.write(chunk)

        # 提取音频
        audio_path = self._extract_audio(video_path, video_path.stem)

        metadata = {
            "title": info.get("title", "douyin_video"),
            "uploader": info.get("author", ""),
            "duration": info.get("duration", 0),
            "thumbnail": info.get("cover_url", ""),
            "url": url,
            "id": info.get("sec_uid", "douyin"),
            "platform": "douyin",
        }
        return audio_path, metadata

    def _layer2_yt_dlp_with_cookie(self, url: str, quality: str) -> Tuple[Path, Dict[str, Any]]:
        """第二层: 使用 yt-dlp + 自动获取的 Cookie"""
        from .cookie_provider import get_douyin_cookie_file, cleanup_temp_cookie

        # 获取 Cookie 文件
        explicit_cookie = self._config.get("douyin", "cookie_file")
        cookie_file, strategy = get_douyin_cookie_file(
            explicit_path=explicit_cookie,
            enable_cdp=self._config.get("douyin", "enable_cdp", default=True),
            enable_browser_cookie3=self._config.get("douyin", "enable_browser_cookie3", default=True),
        )

        if not cookie_file:
            raise DownloadError("无法获取抖音 Cookie（所有策略均失败）")

        logger.info(f"[Douyin-L2] 使用 Cookie 策略: {strategy}")

        try:
            result = self._yt_dlp_download(url, quality, cookie_file, "douyin")
            return result
        finally:
            cleanup_temp_cookie(cookie_file)

    def _layer3_third_party_api(self, url: str, quality: str) -> Tuple[Path, Dict[str, Any]]:
        """第三层: 使用第三方 API 获取直链并下载"""
        import httpx

        apis = self._config.get("douyin", "third_party_apis") or self.DEFAULT_THIRD_PARTY_APIS

        tikhub_key = self._config.get("douyin", "tikhub", "api_key")
        if tikhub_key:
            apis = [
                {
                    "name": "tikhub",
                    "url": "https://api.tikhub.io/api/v1/douyin/web/fetch_one_video_by_share_url",
                    "method": "GET",
                    "param_name": "share_url",
                    "headers": {"Authorization": f"Bearer {tikhub_key}"},
                    "response_path": ["data", "aweme_detail", "video", "play_addr", "url_list", 0],
                    "timeout": 20,
                }
            ] + list(apis)

        last_error = None
        for api in apis:
            try:
                video_url = self._call_third_party_api(url, api)
                if not video_url:
                    continue

                logger.info(f"[Douyin-L3] {api['name']} 获取到直链: {video_url[:80]}...")

                # 下载视频
                video_path = self.output_dir / f"douyin_thirdparty_{api['name']}.mp4"
                with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                    with client.stream("GET", video_url) as resp:
                        resp.raise_for_status()
                        with open(video_path, "wb") as f:
                            for chunk in resp.iter_bytes(chunk_size=8192):
                                f.write(chunk)

                audio_path = self._extract_audio(video_path, f"douyin_{api['name']}")

                metadata = {
                    "title": f"douyin_video_{api['name']}",
                    "uploader": "",
                    "duration": 0,
                    "thumbnail": "",
                    "url": url,
                    "id": f"douyin_{api['name']}",
                    "platform": "douyin",
                }
                return audio_path, metadata

            except Exception as e:
                last_error = f"{api['name']}: {str(e)[:150]}"
                logger.warning(f"[Douyin-L3] {last_error}")
                continue

        raise DownloadError(f"所有第三方 API 均失败。最后错误: {last_error}")

    def _call_third_party_api(self, url: str, api: Dict[str, Any]) -> Optional[str]:
        """调用单个第三方 API 获取视频直链"""
        import httpx

        name = api["name"]
        api_url = api["url"]
        method = api.get("method", "GET").upper()
        param_name = api.get("param_name", "url")
        response_path = api.get("response_path", ["data", "url"])
        timeout = api.get("timeout", 15)
        headers = api.get("headers", {})

        logger.debug(f"[Douyin-L3] 调用 {name}: {api_url}")

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            if method == "GET":
                resp = client.get(api_url, params={param_name: url}, headers=headers)
            else:
                resp = client.post(api_url, json={param_name: url}, headers=headers)

            resp.raise_for_status()
            data = resp.json()

            value = data
            for key in response_path:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and isinstance(key, int):
                    value = value[key] if key < len(value) else None
                else:
                    value = None
                    break

            if value and isinstance(value, str):
                return value

        raise DownloadError(f"{name} 返回数据异常: {json.dumps(data, ensure_ascii=False)[:200]}")

    # ===== yt-dlp 通用下载 =====

    def _get_download_format(self, quality: str, platform: str) -> str:
        """获取下载格式，优先下载音频"""
        if platform == "youtube":
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif platform == "bilibili":
            return "bestaudio/best"
        else:
            return f"{quality}/best"

    def _get_js_runtime_path(self) -> Optional[str]:
        """获取 JavaScript 运行时路径"""
        deno_path = os.path.expanduser("~/.deno/bin/deno.exe")
        if os.path.exists(deno_path):
            return deno_path
        node_path = os.popen("where node").read().strip().split("\n")[0] if os.popen("where node").read().strip() else None
        if node_path and os.path.exists(node_path):
            return node_path
        return None

    def _yt_dlp_download(
        self,
        url: str,
        quality: str,
        cookie_file: Optional[str] = None,
        platform: str = "unknown",
    ) -> Tuple[Path, Dict[str, Any]]:
        """使用 yt-dlp 下载（内部通用方法）"""
        output_template = str(self.output_dir / f"{platform}_video.%(ext)s")

        ydl_opts: Dict[str, Any] = {
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

        if cookie_file and Path(cookie_file).exists():
            ydl_opts["cookiefile"] = cookie_file
            logger.info(f"[yt-dlp] 使用 Cookie: {cookie_file}")

        metadata: Dict[str, Any] = {}
        audio_path: Optional[Path] = None

        def hook(d: Dict[str, Any]) -> None:
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
                raise DownloadError(f"Cookie 无效或已过期: {err_msg[-300:]}")
            raise DownloadError(f"yt-dlp 下载失败: {err_msg[-300:]}")

        if audio_path is None or not audio_path.exists():
            raise AudioExtractError("下载完成但未找到音频文件")

        return audio_path, metadata

    def _download_yt_dlp_sync(self, url: str, quality: str) -> Tuple[Path, Dict[str, Any]]:
        """yt-dlp 通用下载（非抖音平台）"""
        platform = self._detect_platform(url)

        if platform in ("tiktok", "youtube", "twitter", "instagram", "bilibili"):
            logger.info(f"[Download] 平台 {platform} 使用浏览器 Cookie")
            return self._download_with_browser_cookie(url, quality, platform)

        cookie_file = self._try_export_cookies(platform)
        logger.info(f"[Download] Platform: {platform}, Cookie: {cookie_file}")

        if cookie_file:
            logger.info(f"[Download] Cookie file exists: {Path(cookie_file).exists()}")

        try:
            return self._yt_dlp_download(url, quality, cookie_file, platform)
        finally:
            if cookie_file and "temp_cookies" in cookie_file and Path(cookie_file).exists():
                try:
                    Path(cookie_file).unlink()
                except Exception:
                    pass

    def _download_with_browser_cookie(self, url: str, quality: str, platform: str) -> Tuple[Path, Dict[str, Any]]:
        """使用浏览器 Cookie 下载（通过命令行）"""
        logger.info(f"[Download] 尝试使用浏览器 Cookie 下载: {platform}")

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

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise DownloadError(f"yt-dlp 下载失败: {error_msg[-500:]}")

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
                raise DownloadError(f"未找到下载的音频文件")

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
        except Exception as e:
            raise DownloadError(f"下载失败: {e}")

    # ===== 工具方法 =====

    def _extract_audio(self, video_path: Path, base_name: str) -> Path:
        """用 FFmpeg 将视频文件转换为音频"""
        audio_path = self.output_dir / f"{base_name}.mp3"
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "libmp3lame", "-q:a", "0",
                str(audio_path),
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
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

    def _try_export_cookies(self, platform: str = "unknown") -> Optional[str]:
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

    def _find_cookie_file(self, platform: str) -> Optional[str]:
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

    def _download_xiaohongshu_images(self, url: str) -> Tuple[Path, Dict[str, Any]]:
        """
        小红书图片下载

        下载纯图片笔记中的所有图片，保存到本地目录
        """
        import httpx

        logger.info(f"[XiaoHongShu] 解析笔记获取图片...")

        image_dir = self.output_dir / "xiaohongshu_images"
        image_dir.mkdir(parents=True, exist_ok=True)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.xiaohongshu.com/",
        }

        image_paths = []
        title = ""
        note_id = ""

        try:
            with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
                resp = client.get(url)
                actual_url = str(resp.url)
                logger.info(f"[XiaoHongShu] 解析到实际 URL: {actual_url}")

                note_id = self._extract_xiaohongshu_id(actual_url)
                if note_id == "unknown":
                    raise DownloadError(f"无法从 URL 提取小红书笔记 ID: {actual_url}")

                api_url = f"https://www.xiaohongshu.com/explore/{note_id}"
                url = actual_url

                title = f"xiaohongshu_{note_id}"
                image_urls = []

                resp = client.get(api_url)
                resp.raise_for_status()
                html = resp.text

                import re
                image_patterns = [
                    r'"url":"(https?://sns-img[^"]+\.jpg[^"]*)"',
                    r'"url":"(https?://sns-img[^"]+\.jpeg[^"]*)"',
                    r'"url":"(https?://sns-img[^"]+\.png[^"]*)"',
                    r'"url":"(https?://sns-web[^"]+\.jpg[^"]*)"',
                    r'"url":"(https?://sns-web[^"]+\.jpeg[^"]*)"',
                    r'"url":"(https?://sns-web[^"]+\.png[^"]*)"',
                    r'"urlDefault":"(https?://sns-img[^"]+\.(?:jpg|jpeg|png)[^"]*)"',
                    r'"url":"(https?://sns\.xiaohongshu\.com[^"]+\.(?:jpg|jpeg|png)[^"]*)"',
                ]

                for pattern in image_patterns:
                    found = re.findall(pattern, html)
                    image_urls.extend(found)

                image_urls = list(dict.fromkeys(image_urls))

                if not image_urls:
                    logger.warning(f"[XiaoHongShu] 未找到图片，尝试其他方法...")
                    title_match = re.search(r'"title":"([^"]+)"', html)
                    if title_match:
                        title = title_match.group(1)
                        logger.info(f"[XiaoHongShu] 提取到标题: {title}")

                    web_img_patterns = [
                        r'src="(https?://sns-img[^"]+)"',
                        r'data-src="(https?://sns-img[^"]+)"',
                        r'background-image:\s*url\(["\']?(https?://[^"\')\s]+\.(?:jpg|jpeg|png)[^"\')\s]*)[ "\']?\)',
                    ]
                    for pattern in web_img_patterns:
                        found = re.findall(pattern, html)
                        image_urls.extend(found)

                    image_urls = list(dict.fromkeys(image_urls))

                if not image_urls:
                    raise DownloadError("未找到可下载的图片")

                logger.info(f"[XiaoHongShu] 找到 {len(image_urls)} 张图片")

                for idx, img_url in enumerate(image_urls, 1):
                    img_path = image_dir / f"{note_id}_{idx:02d}.jpg"
                    try:
                        img_resp = client.get(img_url)
                        img_resp.raise_for_status()
                        with open(img_path, "wb") as f:
                            f.write(img_resp.content)
                        image_paths.append(img_path)
                        logger.info(f"[XiaoHongShu] 下载图片 {idx}/{len(image_urls)}: {img_path.name}")
                    except Exception as e:
                        logger.warning(f"[XiaoHongShu] 下载图片失败: {e}")

                if not image_paths:
                    raise DownloadError("所有图片下载失败")

        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError(f"小红书图片下载失败: {e}")

        metadata = {
            "title": title,
            "uploader": "",
            "duration": 0,
            "thumbnail": image_paths[0] if image_paths else "",
            "url": url,
            "id": note_id,
            "platform": "xiaohongshu",
            "image_count": len(image_paths),
            "image_paths": [str(p) for p in image_paths],
            "is_images_only": True,
        }

        result_file = image_dir / f"{note_id}_info.txt"
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(f"标题: {title}\n")
            f.write(f"链接: {url}\n")
            f.write(f"图片数量: {len(image_paths)}\n")
            f.write(f"保存目录: {image_dir}\n")
            f.write("\n图片列表:\n")
            for i, p in enumerate(image_paths, 1):
                f.write(f"{i}. {p.name}\n")

        logger.info(f"[XiaoHongShu] 图片下载完成: {len(image_paths)} 张，保存到 {image_dir}")

        return result_file, metadata

    def _extract_xiaohongshu_id(self, url: str) -> str:
        """从 URL 提取小红书笔记 ID"""
        import re
        patterns = [
            r'/discovery/item/([a-zA-Z0-9]+)',
            r'/explore/([a-zA-Z0-9]+)',
            r'xhslink\.com/[a-zA-Z]+/([a-zA-Z0-9]+)',
            r'xiaohongshu\.com/discovery/item/([a-zA-Z0-9]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return "unknown"

    def _detect_platform(self, url: str) -> str:
        """检测视频平台"""
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "bilibili.com" in url_lower or "b23.tv" in url_lower:
            return "bilibili"
        elif "douyin.com" in url_lower or "iesdouyin.com" in url_lower:
            return "douyin"
        elif "xiaohongshu.com" in url_lower or "xhslink.com" in url_lower:
            return "xiaohongshu"
        elif "kuaishou.com" in url_lower:
            return "kuaishou"
        elif "weibo.com" in url_lower:
            return "weibo"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            return "twitter"
        elif "instagram.com" in url_lower:
            return "instagram"
        elif "tiktok.com" in url_lower:
            return "tiktok"
        elif "vimeo.com" in url_lower:
            return "vimeo"
        return "unknown"


# -----------------------------------------------------------------------------
# VidkNot - Video Knowledge, Knotted.
# -----------------------------------------------------------------------------
# Copyright (c) 2026 VidkNot Team
# 
# This software is licensed under the MIT License.
# See LICENSE file in the project root for details.
# 
# Repository: https://github.com/suonian/vidknot
# -----------------------------------------------------------------------------

