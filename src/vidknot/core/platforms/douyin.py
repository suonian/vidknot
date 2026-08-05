"""
抖音平台插件

三层 Fallback 策略（从 downloader.py 迁移）：
┌─────────────────────────────────────────────────────────────┐
│ 第一层: 无 Cookie 快速解析（douyin_parser + 移动端指纹）      │
│ 第二层: Cookie 解析通道（yt-dlp + cookie_provider）           │
│ 第三层: 第三方 API 兜底（apibyte/canxiang/alapi/tikhub）      │
└─────────────────────────────────────────────────────────────┘

可选对接 Evil0ctal/Douyin_TikTok_Download_API 自部署实例
（配置 platforms.douyin.api_base_url 或 douyin.api_base_url）。
"""

import json
from pathlib import Path
from typing import Any

from ...utils.exceptions import DownloadError
from ...utils.logger import get_logger
from .base import BasePlatform

logger = get_logger(__name__)

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


class DouyinPlatform(BasePlatform):
    """抖音平台：三层 fallback 下载"""

    name = "douyin"
    domains = ["douyin.com", "iesdouyin.com"]

    def download(
        self,
        url: str,
        dl: Any,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path, dict[str, Any]]:
        errors: list[str] = []

        # ---- 第一层: 无 Cookie 快速解析 ----
        try:
            logger.info("[Douyin] 第一层: 尝试无 Cookie 解析...")
            return self._layer1_parse_and_download(url, dl)
        except Exception as e:
            err = f"第一层(无Cookie解析): {str(e)[:200]}"
            errors.append(err)
            logger.warning(f"[Douyin] {err}")

        # ---- 第二层: yt-dlp + Cookie ----
        try:
            logger.info("[Douyin] 第二层: 尝试 yt-dlp + Cookie...")
            return self._layer2_yt_dlp_with_cookie(url, quality, dl)
        except Exception as e:
            err = f"第二层(yt-dlp+Cookie): {str(e)[:200]}"
            errors.append(err)
            logger.warning(f"[Douyin] {err}")

        # ---- 第三层: 第三方 API / Evil0ctal 自部署 ----
        if self._cfg(dl, "enable_third_party", default=False):
            try:
                logger.info("[Douyin] 第三层: 尝试第三方 API...")
                return self._layer3_third_party_api(url, dl)
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

    def _cfg(self, dl: Any, key: str, default=None):
        """读取配置：platforms.douyin.{key} 优先，其次 douyin.{key}"""
        value = dl._config.get("platforms", "douyin", key, default=None)
        if value is None:
            value = dl._config.get("douyin", key, default=default)
        return value

    def _layer1_parse_and_download(self, url: str, dl: Any) -> tuple[Path, dict[str, Any]]:
        """第一层: 使用 douyin_parser 解析直链并下载"""
        from .. import douyin_parser

        info = douyin_parser.parse(url)
        video_url = info.get("video_url", "")
        if not video_url:
            raise DownloadError("解析成功但未获取到视频地址")

        logger.info(f"[Douyin-L1] 获取到视频地址: {video_url[:80]}...")

        import httpx

        video_path = dl.output_dir / (
            f"douyin_{info.get('author', 'unknown')}_"
            f"{dl._sanitize_filename(info.get('title', 'video'))}.mp4"
        )
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            with client.stream(
                "GET", video_url, headers={"User-Agent": douyin_parser.ANDROID_CHROME_UA}
            ) as resp:
                resp.raise_for_status()
                with open(video_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        f.write(chunk)

        audio_path = dl._extract_audio(video_path, video_path.stem)

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

    def _layer2_yt_dlp_with_cookie(self, url: str, quality: str, dl: Any) -> tuple[Path, dict[str, Any]]:
        """第二层: 使用 yt-dlp + 自动获取的 Cookie"""
        from ..cookie_provider import cleanup_temp_cookie, get_douyin_cookie_file

        explicit_cookie = self._cfg(dl, "cookie_file")
        cookie_file, strategy = get_douyin_cookie_file(
            explicit_path=explicit_cookie,
            enable_cdp=self._cfg(dl, "enable_cdp", default=True),
            enable_browser_cookie3=self._cfg(dl, "enable_browser_cookie3", default=True),
        )

        if not cookie_file:
            raise DownloadError("无法获取抖音 Cookie（所有策略均失败）")

        logger.info(f"[Douyin-L2] 使用 Cookie 策略: {strategy}")

        try:
            return dl._yt_dlp_download(url, quality, cookie_file, "douyin")
        finally:
            cleanup_temp_cookie(cookie_file)

    def _layer3_third_party_api(self, url: str, dl: Any) -> tuple[Path, dict[str, Any]]:
        """第三层: 使用第三方 API / Evil0ctal 自部署获取直链并下载"""
        import httpx

        apis = self._cfg(dl, "third_party_apis") or list(DEFAULT_THIRD_PARTY_APIS)

        # Evil0ctal/Douyin_TikTok_Download_API 自部署实例（可选）
        api_base_url = self._cfg(dl, "api_base_url")
        if api_base_url:
            apis = [
                {
                    "name": "evil0ctal",
                    "url": f"{api_base_url.rstrip('/')}/api/douyin/web/fetch_one_video_by_share_url",
                    "method": "GET",
                    "param_name": "share_url",
                    "response_path": ["data", "aweme_detail", "video", "play_addr", "url_list", 0],
                    "timeout": 20,
                }
            ] + list(apis)

        tikhub_key = dl._config.get("douyin", "tikhub", "api_key")
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

                video_path = dl.output_dir / f"douyin_thirdparty_{api['name']}.mp4"
                with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                    with client.stream("GET", video_url) as resp:
                        resp.raise_for_status()
                        with open(video_path, "wb") as f:
                            for chunk in resp.iter_bytes(chunk_size=8192):
                                f.write(chunk)

                audio_path = dl._extract_audio(video_path, f"douyin_{api['name']}")

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

    def _call_third_party_api(self, url: str, api: dict[str, Any]) -> str | None:
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
