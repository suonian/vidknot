"""
小红书平台插件

策略：
1. 优先尝试图片笔记下载（解析 __INITIAL_STATE__ + CDN 正则回退）
2. 失败则回退到 yt-dlp 视频下载
3. 可选对接 xhs 库（pip install xhs）或 XHS-Downloader 作为增强

关键要求：
- xsec_token 必须保留在 URL 查询参数中（否则 404）
- 需要登录 Cookie（web_session, a1, webId 等）
- 短链接 xhslink.cn/xhslink.com 需先 302 解析
"""

import re
from pathlib import Path
from typing import Any

from ...utils.exceptions import DownloadError
from ...utils.logger import get_logger
from .base import BasePlatform

logger = get_logger(__name__)


class XiaoHongShuPlatform(BasePlatform):
    """小红书平台：图片优先 + yt-dlp 视频兜底"""

    name = "xiaohongshu"
    domains = ["xiaohongshu.com", "xhslink.com", "xhslink.cn"]

    def download(
        self,
        url: str,
        dl: Any,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path, dict[str, Any]]:
        if not force_audio:
            try:
                return self._download_images(url, dl)
            except Exception as e:
                logger.warning(f"[XiaoHongShu] 图片下载失败: {e}，尝试视频下载...")

        # 视频下载（yt-dlp + Cookie）
        cookie_file = dl._try_export_cookies("xiaohongshu")
        try:
            try:
                return dl._yt_dlp_download(url, quality, cookie_file, "xiaohongshu")
            except Exception as e:
                logger.warning(f"[XiaoHongShu] yt-dlp 下载失败: {str(e)[:150]}")
                # 最终兜底：XHS-Downloader（可选依赖）
                return self._download_with_xhs_downloader(url, dl)
        finally:
            if cookie_file and "temp_cookies" in cookie_file and Path(cookie_file).exists():
                try:
                    Path(cookie_file).unlink()
                except Exception:
                    pass

    def _download_with_xhs_downloader(self, url: str, dl: Any) -> tuple[Path, dict[str, Any]]:
        """使用 XHS-Downloader 兜底下载（可选依赖: pip install xhs-downloader）"""
        try:
            import asyncio

            from XHS_Downloader import XHS
        except ImportError:
            raise DownloadError(
                "小红书视频下载失败。\n\n"
                "建议: 安装可选依赖 XHS-Downloader 增强小红书支持:\n"
                "  pip install xhs-downloader"
            )

        logger.info("[XiaoHongShu] 尝试 XHS-Downloader 兜底...")

        try:
            async def _run():
                async with XHS() as xhs:
                    return await xhs.download(url)

            result = asyncio.run(_run())
        except Exception as e:
            raise DownloadError(f"XHS-Downloader 下载失败: {e}")

        # XHS-Downloader 下载结果可能在 ./download 目录
        candidates: list[Path] = []
        for base in (Path.cwd() / "download", dl.output_dir):
            candidates.extend(sorted(base.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True))

        video_path = candidates[0] if candidates else None
        if not video_path:
            raise DownloadError(f"XHS-Downloader 完成但未找到视频文件: {result}")

        audio_path = dl._extract_audio(video_path, "xiaohongshu_video")
        metadata = {
            "title": "xiaohongshu_video",
            "uploader": "",
            "duration": 0,
            "thumbnail": "",
            "url": url,
            "id": self._extract_note_id(url),
            "platform": "xiaohongshu",
        }
        return audio_path, metadata

    def _download_images(self, url: str, dl: Any) -> tuple[Path, dict[str, Any]]:
        """
        小红书图片下载

        下载纯图片笔记中的所有图片，保存到本地目录
        """
        import httpx

        logger.info("[XiaoHongShu] 解析笔记获取图片...")

        image_dir = dl.output_dir / "xiaohongshu_images"
        image_dir.mkdir(parents=True, exist_ok=True)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.xiaohongshu.com/",
        }

        image_paths = []
        title = ""
        note_id = ""

        try:
            # 获取 Cookie（小红书需要登录 Cookie 才能访问笔记）
            cookie_file = dl._try_export_cookies("xiaohongshu")
            cookies_dict = self._load_cookies(cookie_file)

            with httpx.Client(
                headers=headers, cookies=cookies_dict,
                follow_redirects=True, timeout=30.0,
            ) as client:
                resp = client.get(url)
                actual_url = str(resp.url)
                logger.info(f"[XiaoHongShu] 解析到实际 URL: {actual_url}")

                note_id = self._extract_note_id(actual_url)
                if note_id == "unknown":
                    raise DownloadError(f"无法从 URL 提取小红书笔记 ID: {actual_url}")

                # 保留完整查询参数（xsec_token 是必需的，否则 404）
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(actual_url)
                api_url = f"https://www.xiaohongshu.com/explore/{note_id}"
                if parsed.query:
                    api_url += f"?{parsed.query}"

                title = f"xiaohongshu_{note_id}"
                image_urls = []

                resp = client.get(api_url)
                resp.raise_for_status()
                html = resp.text

                # 优先从 __INITIAL_STATE__ 提取图片（最可靠）
                state_title, image_urls = self._extract_from_state(html, note_id)
                if state_title:
                    title = state_title

                if not image_urls:
                    # 回退到正则匹配
                    image_urls = self._extract_images_by_regex(html)
                    title_match = re.search(r'"title":"([^"]+)"', html)
                    if title_match:
                        title = title_match.group(1)

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
                        logger.info(
                            f"[XiaoHongShu] 下载图片 {idx}/{len(image_urls)}: {img_path.name}"
                        )
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

    @staticmethod
    def _load_cookies(cookie_file: str | None) -> dict[str, str] | None:
        """从 Netscape Cookie 文件加载 Cookie 字典"""
        if not cookie_file or not Path(cookie_file).exists():
            return None
        cookies = {}
        try:
            with open(cookie_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7 and "xiaohongshu" in parts[0].lower():
                        cookies[parts[5]] = parts[6]
        except Exception:
            pass
        return cookies or None

    @staticmethod
    def _extract_from_state(html: str, note_id: str) -> tuple[str, list[str]]:
        """从 __INITIAL_STATE__ JSON 提取标题和图片 URL（最可靠）

        Returns:
            (title, image_urls) 元组
        """
        import json as _json

        match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>', html, re.DOTALL)
        if not match:
            return "", []

        try:
            # 小红书 JSON 中 undefined 需替换为 null
            raw = match.group(1).replace("undefined", "null")
            state = _json.loads(raw)
        except Exception:
            return "", []

        title = ""
        image_urls: list[str] = []
        # 遍历笔记数据查找 imageList
        note_data = state.get("note", {}).get("noteDetailMap", {})
        for key, val in note_data.items():
            note_detail = val.get("note", {}) if isinstance(val, dict) else {}
            # 提取标题
            note_title = note_detail.get("title", "")
            if note_title:
                title = note_title
            # 提取图片
            image_list = note_detail.get("imageList", [])
            for img in image_list:
                url = img.get("urlDefault") or img.get("url", "")
                if url and isinstance(url, str) and url.startswith("http"):
                    image_urls.append(url)

        return title, list(dict.fromkeys(image_urls))

    @staticmethod
    def _extract_images_by_regex(html: str) -> list[str]:
        """通过正则匹配图片 URL（回退方案，覆盖所有已知 CDN）"""
        image_patterns = [
            # 所有已知小红书图片 CDN 域名
            r'"url[^"]*":"(https?://sns-webpic[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            r'"url[^"]*":"(https?://sns-img[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            r'"url[^"]*":"(https?://sns-web[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            r'"url[^"]*":"(https?://sns\.xiaohongshu\.com[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            r'"url[^"]*":"(https?://ci\.xiaohongshu\.com[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
        ]
        image_urls: list[str] = []
        for pattern in image_patterns:
            image_urls.extend(re.findall(pattern, html))
        return list(dict.fromkeys(image_urls))

    @staticmethod
    def _extract_note_id(url: str) -> str:
        """从 URL 提取小红书笔记 ID"""
        patterns = [
            r"/discovery/item/([a-zA-Z0-9]+)",
            r"/explore/([a-zA-Z0-9]+)",
            r"xhslink\.(?:com|cn)/[a-zA-Z]+/([a-zA-Z0-9]+)",
            r"xiaohongshu\.com/discovery/item/([a-zA-Z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return "unknown"
