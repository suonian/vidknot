"""
小红书平台插件

策略：
1. 根据笔记类型（视频/图片）走对应分支
2. 视频笔记：从 __INITIAL_STATE__ 拿视频直链 → 下载 → 抽音频
3. 图片笔记：解析 __INITIAL_STATE__ + CDN 正则回退
4. 全链路 fall back 到 yt-dlp → XHS-Downloader

关键要求：
- xsec_token 必须保留在 URL 查询参数中（否则 404）
- 需要登录 Cookie（web_session, a1, webId 等）
- 短链接 xhslink.cn/xhslink.com 需先 302 解析

纯解析逻辑（__INITIAL_STATE__ / URL / Cookie 文件）位于
core/xhs_parser.py；本文件只负责下载编排与多级兜底。
"""

import re
from pathlib import Path
from typing import Any

from ...utils.exceptions import DownloadError
from ...utils.logger import get_logger
from .. import xhs_parser
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
            # 先探测笔记类型（需拉一次 HTML，但拿不到则让视频路径接管）
            note_type = self._probe_note_type(url, dl)
            if note_type == "video":
                try:
                    return self._download_video(url, dl)
                except Exception as e:
                    logger.warning(f"[XiaoHongShu] 视频下载失败: {e}，尝试 yt-dlp 兜底...")
            elif note_type == "image":
                try:
                    return self._download_images(url, dl)
                except Exception as e:
                    logger.warning(f"[XiaoHongShu] 图片下载失败: {e}，尝试视频路径兑底...")
                    # 图片路径走了一次请求后探测可能为“”代表被风控。
                    # 此时不要放弃，仍试一次视频下载走它自己内部的重复请求机制。
                    try:
                        return self._download_video(url, dl)
                    except Exception as e2:
                        logger.warning(f"[XiaoHongShu] 视频路径也失败: {e2}，尝试 yt-dlp 兜底...")
            else:
                # unknown：探测请求可能被风控跳到首页。直接试视频路径。
                try:
                    return self._download_video(url, dl)
                except Exception as e:
                    logger.warning(f"[XiaoHongShu] 视频下载失败: {e}，尝试图片路径兑底...")
                    try:
                        return self._download_images(url, dl)
                    except Exception as e2:
                        logger.warning(f"[XiaoHongShu] 图片路径也失败: {e2}，尝试 yt-dlp 兜底...")

        # yt-dlp 兜底（图片/视频/混合笔记）
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
                from urllib.parse import urlparse
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
                state_title, image_urls, _ = self._extract_from_state(html, note_id)
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

    def _probe_note_type(self, url: str, dl: Any) -> str:
        """探测笔记类型：video | image | unknown

        返回 unknown 表示获取失败，调用方应默认按图片走
        """
        import httpx

        cookie_file = dl._try_export_cookies("xiaohongshu")
        cookies_dict = self._load_cookies(cookie_file)
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.xiaohongshu.com/",
            }
            with httpx.Client(
                headers=headers, cookies=cookies_dict,
                follow_redirects=True, timeout=20.0,
            ) as client:
                resp = client.get(url)
                actual_url = str(resp.url)
                note_id = self._extract_note_id(actual_url)
                if note_id == "unknown":
                    return "unknown"
                from urllib.parse import urlparse
                parsed = urlparse(actual_url)
                api_url = f"https://www.xiaohongshu.com/explore/{note_id}"
                if parsed.query:
                    api_url += f"?{parsed.query}"
                resp = client.get(api_url)
                resp.raise_for_status()
                html = resp.text
                # 优先看 __INITIAL_STATE__ 里的 video 字段
                _, _, video_url = self._extract_from_state(html, note_id)
                if video_url:
                    return "video"
                # 回退：正则看是否有 video stream URL 特征
                if re.search(r'"masterUrl"\s*:\s*"https?://', html):
                    return "video"
                if re.search(r'sns-video[^"\\\s]+', html):
                    return "video"
                return "image"
        except Exception as e:
            logger.debug(f"[XiaoHongShu] 探测笔记类型失败: {e}")
            return "unknown"
        finally:
            if cookie_file and "temp_cookies" in cookie_file and Path(cookie_file).exists():
                try:
                    Path(cookie_file).unlink()
                except Exception:
                    pass

    def _download_video(self, url: str, dl: Any) -> tuple[Path, dict[str, Any]]:
        """小红书视频笔记下载

        流程：
        1. 从 __INITIAL_STATE__ 解析 video.media.stream.h264[0].master_url
        2. 下载视频到 output_dir
        3. 调用 dl._extract_audio 抽音频
        """
        import httpx

        logger.info("[XiaoHongShu] 解析视频笔记...")

        cookie_file = dl._try_export_cookies("xiaohongshu")
        cookies_dict = self._load_cookies(cookie_file)
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://www.xiaohongshu.com/",
            }

            video_url: str | None = None
            title = ""
            note_id = ""

            with httpx.Client(
                headers=headers, cookies=cookies_dict,
                follow_redirects=True, timeout=30.0,
            ) as client:
                # 短链展开
                resp = client.get(url)
                actual_url = str(resp.url)
                logger.info(f"[XiaoHongShu] 解析到实际 URL: {actual_url}")

                note_id = self._extract_note_id(actual_url)
                if note_id == "unknown":
                    raise DownloadError(f"无法从 URL 提取小红书笔记 ID: {actual_url}")

                from urllib.parse import urlparse
                parsed = urlparse(actual_url)
                api_url = f"https://www.xiaohongshu.com/explore/{note_id}"
                if parsed.query:
                    api_url += f"?{parsed.query}"

                resp = client.get(api_url)
                resp.raise_for_status()
                html = resp.text

                # 从 __INITIAL_STATE__ 拿视频直链
                state_title, _, state_video = self._extract_from_state(html, note_id)
                if state_title:
                    title = state_title
                if state_video:
                    video_url = state_video

                # 备用：正则从 HTML 拿 masterUrl
                if not video_url:
                    m = re.search(r'"masterUrl"\s*:\s*"(https?://[^"]+)"', html)
                    if m:
                        video_url = m.group(1)

            if not video_url:
                raise DownloadError("未在 __INITIAL_STATE__ 中找到视频直链")

            # video.masterUrl 通常是模板（如 .../{quality}.mp4），需要替换为具体清晰度
            # 默认尝试 _HD、_SD 或裸链接；先用原 URL 尝试，必要时走备选
            candidates = [video_url]
            # 常见模板后缀：按高→低
            for suffix in ["_HD.mp4", ".mp4", "_SD.mp4"]:
                templated = video_url
                if "{" in templated or "_HD" not in templated:
                    templated2 = templated.replace("{quality}", suffix.lstrip("_").rstrip(".mp4")).replace(".mp4", suffix)
                    if templated2 != video_url and templated2 not in candidates:
                        candidates.append(templated2)

            # 下载视频（选第一个能成功的）
            video_path = dl.output_dir / f"{note_id or 'xiaohongshu_video'}.mp4"
            downloaded = False
            for candidate in candidates:
                try:
                    logger.info(f"[XiaoHongShu] 下载视频: {candidate[:120]}...")
                    with httpx.Client(
                        headers=headers, cookies=cookies_dict,
                        follow_redirects=True, timeout=120.0,
                    ) as client:
                        with client.stream("GET", candidate) as resp:
                            resp.raise_for_status()
                            with open(video_path, "wb") as f:
                                for chunk in resp.iter_bytes(chunk_size=65536):
                                    if chunk:
                                        f.write(chunk)
                    if video_path.exists() and video_path.stat().st_size > 1024:
                        downloaded = True
                        logger.info(
                            f"[XiaoHongShu] 视频下载成功 ({video_path.stat().st_size} bytes): {video_path.name}"
                        )
                        break
                    video_path.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"[XiaoHongShu] 候选 URL 下载失败: {str(e)[:120]}")
                    if video_path.exists():
                        video_path.unlink(missing_ok=True)

            if not downloaded:
                raise DownloadError("所有候选视频 URL 均下载失败")

            # 抽音频（用于转写为笔记）
            audio_path = dl._extract_audio(video_path, note_id or "xiaohongshu_video")

            metadata = {
                "title": title or f"xiaohongshu_{note_id}",
                "uploader": "",
                "duration": 0,
                "thumbnail": "",
                "url": url,
                "id": note_id,
                "platform": "xiaohongshu",
                "is_video": True,
                "video_path": str(video_path),
                "video_url": video_url,
            }

            logger.info(
                f"[XiaoHongShu] 视频转笔记完成: {video_path.name} → {audio_path.name}"
            )
            return audio_path, metadata

        finally:
            if cookie_file and "temp_cookies" in cookie_file and Path(cookie_file).exists():
                try:
                    Path(cookie_file).unlink()
                except Exception:
                    pass

    # ===== 解析方法（实现位于 core/xhs_parser.py，此处为薄委托） =====

    @staticmethod
    def _load_cookies(cookie_file: str | None) -> dict[str, str] | None:
        """从 Netscape Cookie 文件加载 Cookie 字典"""
        return xhs_parser.load_cookies(cookie_file)

    @staticmethod
    def _extract_from_state(html: str, note_id: str) -> tuple[str, list[str], str | None]:
        """从 __INITIAL_STATE__ JSON 提取标题、图片 URL、视频 URL"""
        return xhs_parser.extract_from_state(html, note_id)

    @staticmethod
    def _extract_images_by_regex(html: str) -> list[str]:
        """通过正则匹配图片 URL（回退方案，覆盖所有已知 CDN）"""
        return xhs_parser.extract_images_by_regex(html)

    @staticmethod
    def _extract_note_id(url: str) -> str:
        """从 URL 提取小红书笔记 ID"""
        return xhs_parser.extract_note_id(url)
