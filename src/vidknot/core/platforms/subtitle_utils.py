"""
平台插件共享的字幕提取工具

提供基于 yt-dlp 的字幕提取能力，供 youtube.py / bilibili.py 等复用。
"""

from pathlib import Path
from typing import Any

from ...utils.logger import get_logger

logger = get_logger(__name__)


def fetch_ytdlp_subtitles(
    url: str,
    output_dir: Path,
    platform: str,
    languages: list[str] | None = None,
    cookie_file: str | None = None,
    browser_cookie: bool = False,
) -> tuple[str | None, dict[str, Any]]:
    """
    使用 yt-dlp 提取字幕（不下载媒体）

    Args:
        url: 视频 URL
        output_dir: 输出目录
        platform: 平台名（用于文件前缀）
        languages: 字幕语言列表（如 ["zh", "en"]）
        cookie_file: Cookie 文件路径
        browser_cookie: 是否使用浏览器 Cookie

    Returns:
        (subtitle_text, metadata)。无字幕时 subtitle_text 为 None。
    """
    import yt_dlp

    from ..transcriber import SubtitleExtractor

    languages = languages or ["zh", "en"]
    output_template = str(output_dir / f"{platform}_sub.%(ext)s")

    ydl_opts: dict[str, Any] = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": languages,
        "subtitlesformat": "vtt/srt/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
        "ignoreerrors": True,
    }
    if cookie_file and Path(cookie_file).exists():
        ydl_opts["cookiefile"] = cookie_file
    if browser_cookie:
        ydl_opts["cookiesfrombrowser"] = ("chrome",)

    metadata: dict[str, Any] = {}
    subtitle_text: str | None = None

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
    except Exception as e:
        logger.warning(f"[{platform}] 字幕提取失败: {str(e)[:200]}")
        return None, metadata

    # 查找下载的字幕文件并解析
    extractor = SubtitleExtractor()
    for ext in ("vtt", "srt"):
        candidates = sorted(output_dir.glob(f"{platform}_sub*.{ext}"))
        for sub_file in candidates:
            try:
                text = extractor.extract(sub_file)
                if text and text.strip():
                    subtitle_text = text.strip()
                    logger.info(f"[{platform}] 提取到字幕: {sub_file.name} ({len(subtitle_text)} 字符)")
                    break
            except Exception as e:
                logger.warning(f"[{platform}] 解析字幕失败 {sub_file.name}: {e}")
        if subtitle_text:
            break

    # 清理字幕文件
    for ext in ("vtt", "srt"):
        for sub_file in output_dir.glob(f"{platform}_sub*.{ext}"):
            try:
                sub_file.unlink()
            except Exception:
                pass

    return subtitle_text, metadata
