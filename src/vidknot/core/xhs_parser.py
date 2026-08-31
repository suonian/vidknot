"""
小红书页面纯解析库

从 platforms/xiaohongshu.py 拆分而来（v0.6.0）：本模块只做"解析"，
不做网络请求与下载编排，便于单独测试与复用。分工对齐
core/douyin_parser.py 的模式：

- xhs_parser: HTML/__INITIAL_STATE__/URL → 结构化数据（标题、图片、视频直链）
- platforms/xiaohongshu.py: 下载编排、类型探测、多级兜底

数据路径参考（__INITIAL_STATE__）：
  note.noteDetailMap[<note_id>].note.video.media.stream.h264[0].masterUrl
  或 backupUrls[0]
"""

import json
import re
from pathlib import Path

__all__ = [
    "extract_balanced_json",
    "extract_from_state",
    "extract_note_id",
    "extract_images_by_regex",
    "load_cookies",
]

# 已知小红书图片 CDN 域名（回退正则方案）
_IMAGE_CDN_PATTERNS = [
    r'"url[^"]*":"(https?://sns-webpic[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
    r'"url[^"]*":"(https?://sns-img[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
    r'"url[^"]*":"(https?://sns-web[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
    r'"url[^"]*":"(https?://sns\.xiaohongshu\.com[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
    r'"url[^"]*":"(https?://ci\.xiaohongshu\.com[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
]

_NOTE_ID_PATTERNS = [
    r"/discovery/item/([a-zA-Z0-9]+)",
    r"/explore/([a-zA-Z0-9]+)",
    r"xhslink\.(?:com|cn)/[a-zA-Z]+/([a-zA-Z0-9]+)",
    r"xiaohongshu\.com/discovery/item/([a-zA-Z0-9]+)",
]


def extract_balanced_json(text: str) -> str | None:
    """从 text 起点提取第一对花括号包裹的平衡 JSON 字符串。

    处理字符串字面量内的括号和转义，避免被字符串里的 {} 干扰。
    成功返回 JSON 文本，失败返回 None。
    """
    i = 0
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] != "{":
        return None

    depth = 0
    start = i
    in_str = False
    str_quote = ""
    escape = False
    while i < len(text):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == str_quote:
                in_str = False
        else:
            if ch in ('"', "'"):
                in_str = True
                str_quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    return None


def extract_from_state(html: str, note_id: str) -> tuple[str, list[str], str | None]:
    """从 __INITIAL_STATE__ JSON 提取标题、图片 URL、视频 URL

    Returns:
        (title, image_urls, video_url) 元组
    """
    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*', html)
    if not match:
        return "", [], None

    # 从赋值点开始，用括号平衡扫描提取完整 JSON
    json_text = extract_balanced_json(html[match.end():])
    if not json_text:
        return "", [], None

    # 处理小红书 JSON 中 undefined 需替换为 null
    json_text = json_text.replace("undefined", "null")
    try:
        state = json.loads(json_text)
    except Exception:
        return "", [], None

    title = ""
    image_urls: list[str] = []
    video_url: str | None = None
    note_data = state.get("note", {}).get("noteDetailMap", {})
    for key, val in note_data.items():
        note_detail = val.get("note", {}) if isinstance(val, dict) else {}
        note_title = note_detail.get("title", "")
        if note_title:
            title = note_title
        image_list = note_detail.get("imageList", [])
        for img in image_list:
            url = img.get("urlDefault") or img.get("url", "")
            if url and isinstance(url, str) and url.startswith("http"):
                image_urls.append(url)
        # 提取视频直链（注意：key 是驼峰 camelCase）
        video = note_detail.get("video", {})
        if isinstance(video, dict):
            media = video.get("media", {})
            if isinstance(media, dict):
                stream = media.get("stream", {})
                if isinstance(stream, dict):
                    video_url = _extract_stream_url(stream) or video_url

    return title, list(dict.fromkeys(image_urls)), video_url


def _extract_stream_url(stream: dict) -> str | None:
    """从 media.stream 提取视频直链：优先 h264，回退 h265。"""
    for codec_key in ("h264", "h265"):
        for item in stream.get(codec_key, []) or []:
            if not isinstance(item, dict):
                continue
            master = item.get("masterUrl") or item.get("master_url")
            if master and isinstance(master, str):
                return master
            backups = item.get("backupUrls") or item.get("backup_urls") or []
            if backups:
                return backups[0]
    return None


def extract_note_id(url: str) -> str:
    """从 URL 提取小红书笔记 ID，失败返回 "unknown"。"""
    for pattern in _NOTE_ID_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return "unknown"


def extract_images_by_regex(html: str) -> list[str]:
    """通过正则匹配图片 URL（回退方案，覆盖所有已知 CDN）"""
    image_urls: list[str] = []
    for pattern in _IMAGE_CDN_PATTERNS:
        image_urls.extend(re.findall(pattern, html))
    return list(dict.fromkeys(image_urls))


def load_cookies(cookie_file: str | None) -> dict[str, str] | None:
    """从 Netscape Cookie 文件加载小红书 Cookie 字典"""
    if not cookie_file or not Path(cookie_file).exists():
        return None
    cookies = {}
    try:
        with open(cookie_file, encoding="utf-8", errors="replace") as f:
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
