"""
抖音平台插件

四层 Fallback 策略：
┌─────────────────────────────────────────────────────────────────┐
│ Layer 0: f2 XBogus 签名（scripts/f2_helper.py，免费开源，自动签名）│
│ Layer 1: iesdouyin 直采（douyin_parser + 移动端指纹 + Cookie）    │
│ Layer 2: yt-dlp + Cookie（可能因 X-Bogus 失败）                  │
│ Layer 3 (opt-in): 第三方 API 兜底（apibyte/canxiang/alapi/tikhub）│
└─────────────────────────────────────────────────────────────────┘

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

        # ---- Layer 0: f2 XBogus 签名（免费开源优先）----
        # 默认 disabled：f2 0.0.1.7 签名算法已被抖音更新，真实环境跑不通。
        # Hermes agent (上海服务器) 2026-08 实测：签名后 API 返回空 body。
        # 等 f2 项目复活或集成 Evil0ctal/Douyin_TikTok_Download_API 自部署后可重新开启。
        if self._cfg(dl, "enable_f2", default=False):
            try:
                logger.info("[Douyin] Layer 0: 尝试 f2 XBogus 签名...")
                return self._layer0_f2_helper(url, dl)
            except Exception as e:
                err = f"Layer0(f2签名): {str(e)[:200]}"
                errors.append(err)
                logger.warning(f"[Douyin] {err}")

        # ---- Layer 1: iesdouyin 直采 + Cookie ----
        try:
            logger.info("[Douyin] Layer 1: 尝试 iesdouyin 直采...")
            return self._layer1_parse_and_download(url, dl)
        except Exception as e:
            err = f"Layer1(iesdouyin): {str(e)[:200]}"
            errors.append(err)
            logger.warning(f"[Douyin] {err}")

        # ---- Layer 2: yt-dlp + Cookie ----
        try:
            logger.info("[Douyin] Layer 2: 尝试 yt-dlp + Cookie...")
            return self._layer2_yt_dlp_with_cookie(url, quality, dl)
        except Exception as e:
            err = f"Layer2(yt-dlp): {str(e)[:200]}"
            errors.append(err)
            logger.warning(f"[Douyin] {err}")

        # ---- Layer 3: 第三方 API / Evil0ctal 自部署 ----
        if self._cfg(dl, "enable_third_party", default=False):
            try:
                logger.info("[Douyin] Layer 3: 尝试第三方 API...")
                return self._layer3_third_party_api(url, dl)
            except Exception as e:
                err = f"Layer3(第三方API): {str(e)[:200]}"
                errors.append(err)
                logger.warning(f"[Douyin] {err}")

        # ---- 全部失败 ----
        error_report = "\n".join(f"  - {e}" for e in errors)
        raise DownloadError(
            f"抖音视频下载失败，所有策略均已尝试:\n{error_report}\n\n"
            f"建议:\n"
            f"1. 导出浏览器 Cookie 为 Netscape 格式保存到 cookies/douyin.txt\n"
            f"2. 确认 .venv-f2 已安装 f2 库（./.venv-f2/bin/pip install f2）\n"
            f"3. 或在 config.yaml 中配置 TikHub API Key (Layer 3)"
        )

    def _cfg(self, dl: Any, key: str, default=None):
        """读取配置：platforms.douyin.{key} 优先，其次 douyin.{key}"""
        value = dl._config.get("platforms", "douyin", key, default=None)
        if value is None:
            value = dl._config.get("douyin", key, default=default)
        return value

    @staticmethod
    def _cookie_file_to_str(cookie_file: str) -> str | None:
        """从 Netscape Cookie 文件读取为 'key=val; key2=val2' 字符串"""
        if not cookie_file or not Path(cookie_file).exists():
            return None
        cookies: list[str] = []
        try:
            with open(cookie_file, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        cookies.append(f"{parts[5]}={parts[6]}")
        except Exception:
            return None
        return "; ".join(cookies) if cookies else None

    def _layer0_f2_helper(self, url: str, dl: Any) -> tuple[Path, dict[str, Any]]:
        """Layer 0: 调用 f2_helper.py 子进程（免费 XBogus 签名）

        要求 .venv-f2/bin/python3 已安装 f2 0.0.1.7+。
        子进程隔离避免 f2 的庞依赖污染主 venv。
        """
        import subprocess

        f2_python = Path(__file__).parent.parent.parent.parent / ".venv-f2" / "bin" / "python3"
        helper_script = Path(__file__).parent.parent.parent.parent / "scripts" / "f2_helper.py"

        if not f2_python.exists():
            raise DownloadError(f".venv-f2 不存在: {f2_python}")
        if not helper_script.exists():
            raise DownloadError(f"f2_helper.py 不存在: {helper_script}")

        # 尝试获取 Cookie
        explicit_cookie = self._cfg(dl, "cookie_file")
        cookie_file = None
        if explicit_cookie and Path(explicit_cookie).exists():
            cookie_file = explicit_cookie
        else:
            # 从 dl._find_cookie_file 获取
            found = dl._find_cookie_file("douyin")
            if found and Path(found).exists():
                cookie_file = found

        # 构造命令
        cmd = [str(f2_python), str(helper_script), url]
        if cookie_file:
            cmd.extend(["--cookie-file", cookie_file])

        logger.info(f"[Douyin-L0] 调用 f2_helper: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            raise DownloadError("f2_helper.py 超时（30秒）")
        except Exception as e:
            raise DownloadError(f"f2_helper.py 调用失败: {e}")

        if result.returncode != 0 and not result.stdout.strip():
            raise DownloadError(f"f2_helper.py 退出码 {result.returncode}: {result.stderr[:300]}")

        # 解析 JSON 输出
        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            raise DownloadError(f"f2_helper.py 输出非 JSON: stdout={result.stdout[:200]}, stderr={result.stderr[:200]}")

        if not data.get("ok"):
            raise DownloadError(f"f2_helper 解析失败: {data.get('error', 'unknown')}")

        video_url = data.get("video_url", "")
        if not video_url:
            raise DownloadError("f2_helper 未返回视频地址")

        logger.info(f"[Douyin-L0] 获取到视频地址: {video_url[:80]}...")

        # 下载视频
        title = data.get("title", "douyin_video")
        author = data.get("author", "unknown")
        duration = data.get("duration", 0)
        aweme_id = data.get("aweme_id", "douyin")

        safe_title = dl._sanitize_filename(title) or "douyin_video"
        video_path = dl.output_dir / f"douyin_f2_{author}_{aweme_id}_{safe_title}.mp4"

        import httpx
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            with client.stream("GET", video_url) as resp:
                resp.raise_for_status()
                with open(video_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        f.write(chunk)

        # 提取音频
        audio_path = dl._extract_audio(video_path, video_path.stem)

        metadata = {
            "title": title,
            "uploader": author,
            "duration": duration,
            "thumbnail": data.get("cover", ""),
            "url": url,
            "id": aweme_id,
            "platform": "douyin",
            "download_layer": "f2_xbogus",
        }
        return audio_path, metadata

    def _layer1_parse_and_download(self, url: str, dl: Any) -> tuple[Path, dict[str, Any]]:
        """第一层: 使用 douyin_parser 解析直链并下载（支持 Cookie）"""
        from .. import douyin_parser
        from ..cookie_provider import cleanup_temp_cookie, get_douyin_cookie_file

        # 尝试获取 Cookie 以提高解析成功率
        explicit_cookie = self._cfg(dl, "cookie_file")
        cookie_file, strategy = get_douyin_cookie_file(
            explicit_path=explicit_cookie,
            enable_cdp=self._cfg(dl, "enable_cdp", default=True),
            enable_browser_cookie3=self._cfg(dl, "enable_browser_cookie3", default=True),
        )
        cookie_str = self._cookie_file_to_str(cookie_file) if cookie_file else None
        if cookie_str:
            logger.info(f"[Douyin-L1] 使用 Cookie 策略: {strategy}")

        try:
            info = douyin_parser.parse(url, cookie_str=cookie_str)
        finally:
            cleanup_temp_cookie(cookie_file)

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
                    "url": "https://api.tikhub.dev/api/v1/douyin/web/fetch_one_video_by_share_url",
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
                self._download_with_retry(video_url, video_path, api["name"])

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

    @staticmethod
    def _download_with_retry(
        video_url: str,
        video_path: Path,
        api_name: str,
        max_retries: int = 2,
        chunk_size: int = 65536,
        timeout: float = 90.0,
    ) -> None:
        """下载视频直链（自带指数退避重试）。

        TikHub / apibyte 返回的视频直链可能来自 CDN 缓存，偶尔临时不可达。
        加 2 次重试（1s / 2s 退避），避免因为 CDN 瞬断直接跳过该 API。
"""
        import time

        import httpx

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(
                    follow_redirects=True, timeout=timeout,
                ) as client:
                    with client.stream("GET", video_url) as resp:
                        resp.raise_for_status()
                        with open(video_path, "wb") as f:
                            for chunk in resp.iter_bytes(chunk_size=chunk_size):
                                if chunk:
                                    f.write(chunk)
                if video_path.exists() and video_path.stat().st_size > 1024:
                    logger.info(
                        f"[Douyin-L3] {api_name} 视频下载完成"
                        f" ({video_path.stat().st_size} bytes)"
                    )
                    return
                last_err = f"视频文件异常 ({video_path.stat().st_size} bytes)"
                video_path.unlink(missing_ok=True)
            except Exception as e:
                last_err = str(e)[:200]
                video_path.unlink(missing_ok=True)

            if attempt < max_retries:
                delay = 1.0 * (2 ** attempt)
                logger.warning(
                    f"[Douyin-L3] {api_name} 下载失败 (attempt {attempt + 1}),"
                    f" {delay}s 后重试: {last_err}"
                )
                time.sleep(delay)

        raise DownloadError(
            f"{api_name} 视频下载失败 (after {max_retries + 1} attempts): {last_err}"
        )

    @staticmethod
    def _call_third_party_api(
        url: str,
        api: dict[str, Any],
        max_retries: int = 2,
    ) -> str | None:
        """调用单个第三方 API 获取视频直链（自带指数退避重试）。

        重试策略（v0.4.2 新增）:
        - 临时错误（429 限流 / 5xx 过载 / 网络超时）→ 指数退避重试
        - 永久错误（401 鉴权过期 / 403 无权限 / 404 不存在）→ 直接跳过
        """
        import time

        import httpx

        name = api["name"]
        api_url = api["url"]
        method = api.get("method", "GET").upper()
        param_name = api.get("param_name", "url")
        response_path = api.get("response_path", ["data", "url"])
        timeout = api.get("timeout", 15)
        headers = api.get("headers", {})

        _permanent_status = {401, 403, 404}

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"[Douyin-L3] 调用 {name}: {api_url}")

                with httpx.Client(
                    timeout=timeout, follow_redirects=True,
                ) as client:
                    if method == "GET":
                        resp = client.get(
                            api_url, params={param_name: url}, headers=headers,
                        )
                    else:
                        resp = client.post(
                            api_url, json={param_name: url}, headers=headers,
                        )

                    # 永久错误 → 不重试
                    if resp.status_code in _permanent_status:
                        logger.warning(
                            f"[Douyin-L3] {name} 返回 {resp.status_code}"
                            f" (permanent, skip): {resp.text[:200]}"
                        )
                        return None

                    resp.raise_for_status()
                    data = resp.json()

            except httpx.TimeoutException:
                last_err = f"{name} 超时"
            except httpx.HTTPStatusError as e:
                sc = e.response.status_code
                last_err = f"{name} HTTP {sc}: {str(e)[:150]}"
                if sc in _permanent_status:
                    return None  # permanent, don't retry
            except Exception as e:
                last_err = f"{name} 请求异常: {str(e)[:150]}"
            else:
                # 成功 → 解析 response
                return DouyinPlatform._parse_api_response(
                    data, response_path, name,
                )

            if attempt < max_retries:
                delay = 1.0 * (2 ** attempt)
                logger.warning(
                    f"[Douyin-L3] {last_err} —"
                    f" {delay}s 后重试 (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delay)

        logger.warning(f"[Douyin-L3] {name} 重试 {max_retries} 次后仍失败")
        return None

    @staticmethod
    def _parse_api_response(
        data: dict,
        response_path: list,
        api_name: str,
    ) -> str | None:
        """从第三方 API JSON 响应中按路径提取视频直链 URL。"""
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

        logger.warning(
            f"[Douyin-L3] {api_name} 返回数据无法解析"
            f" (path={response_path}): {str(data)[:200]}"
        )
        return None
