"""
小红书平台插件

策略：
1. 优先尝试图片笔记下载（纯图文笔记）
2. 失败则回退到 yt-dlp 视频下载
3. 可选对接 XHS-Downloader（pip install xhs-downloader）作为最终兜底
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
    domains = ["xiaohongshu.com", "xhslink.com"]

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
            with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
                resp = client.get(url)
                actual_url = str(resp.url)
                logger.info(f"[XiaoHongShu] 解析到实际 URL: {actual_url}")

                note_id = self._extract_note_id(actual_url)
                if note_id == "unknown":
                    raise DownloadError(f"无法从 URL 提取小红书笔记 ID: {actual_url}")

                api_url = f"https://www.xiaohongshu.com/explore/{note_id}"
                url = actual_url

                title = f"xiaohongshu_{note_id}"
                image_urls = []

                resp = client.get(api_url)
                resp.raise_for_status()
                html = resp.text

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
                    logger.warning("[XiaoHongShu] 未找到图片，尝试其他方法...")
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
    def _extract_note_id(url: str) -> str:
        """从 URL 提取小红书笔记 ID"""
        patterns = [
            r"/discovery/item/([a-zA-Z0-9]+)",
            r"/explore/([a-zA-Z0-9]+)",
            r"xhslink\.com/[a-zA-Z]+/([a-zA-Z0-9]+)",
            r"xiaohongshu\.com/discovery/item/([a-zA-Z0-9]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return "unknown"
