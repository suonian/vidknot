"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

# -*- coding: utf-8 -*-
"""
VidkNot 抖音视频解析器

三层解析策略（按优先级）：
1. curl_cffi 浏览器指纹模拟（模拟 Android Chrome TLS/HTTP2 指纹）
2. httpx 移动端请求（标准 HTTP 客户端）
3. 若均失败，抛出 ValueError 由上层 fallback 处理

curl_cffi 为可选依赖，未安装时自动回退到 httpx。
"""

import json
import re
from typing import Dict, Any, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ===== 移动端请求头（模拟 Android Chrome） =====

ANDROID_CHROME_UA = (
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

MOBILE_HEADERS = {
    "User-Agent": ANDROID_CHROME_UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.douyin.com/?is_from_mobile_home=1&recommend=1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}

# ===== HTTP 客户端抽象 =====

class HttpClient:
    """HTTP 客户端抽象基类"""

    def get(self, url: str, headers: Dict[str, str], follow_redirects: bool = True, timeout: float = 30.0) -> Any:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError


class HttpxClient(HttpClient):
    """httpx 客户端实现"""

    def __init__(self):
        import httpx
        self._client = httpx.Client(follow_redirects=True, timeout=30.0)
        self._httpx = httpx

    def get(self, url: str, headers: Dict[str, str], follow_redirects: bool = True, timeout: float = 30.0) -> Any:
        return self._client.get(url, headers=headers, follow_redirects=follow_redirects, timeout=timeout)

    @property
    def name(self) -> str:
        return "httpx"


class CurlCffiClient(HttpClient):
    """curl_cffi 客户端实现（模拟浏览器 TLS/HTTP2 指纹）"""

    def __init__(self, impersonate: str = "chrome99_android"):
        from curl_cffi import requests as curl_requests
        self._requests = curl_requests
        self._impersonate = impersonate

    def get(self, url: str, headers: Dict[str, str], follow_redirects: bool = True, timeout: float = 30.0) -> Any:
        return self._requests.get(
            url,
            headers=headers,
            impersonate=self._impersonate,
            timeout=timeout,
            allow_redirects=follow_redirects,
        )

    @property
    def name(self) -> str:
        return f"curl_cffi({self._impersonate})"


def _get_http_clients() -> list:
    """获取可用的 HTTP 客户端列表（按优先级）"""
    clients = []

    # 优先尝试 curl_cffi（浏览器指纹模拟）
    try:
        clients.append(CurlCffiClient(impersonate="chrome99_android"))
        logger.debug("[DouyinParser] curl_cffi 已加载")
    except ImportError:
        logger.debug("[DouyinParser] curl_cffi 未安装，跳过浏览器指纹模拟")

    # fallback 到 httpx
    try:
        clients.append(HttpxClient())
    except ImportError:
        raise ImportError("httpx 或 curl_cffi 至少需要一个 HTTP 客户端")

    return clients


# ===== 解析逻辑 =====

def parse(url: str) -> Dict[str, Any]:
    """
    解析抖音分享链接，返回视频元数据

    Args:
        url: 抖音分享链接（短链或长链）

    Returns:
        视频元数据字典

    Raises:
        ValueError: 解析失败（所有客户端均失败）
    """
    clients = _get_http_clients()
    last_error = None

    for client in clients:
        try:
            logger.info(f"[DouyinParser] 尝试使用 {client.name} 解析: {url[:60]}...")
            result = _parse_with_client(url, client)
            logger.info(f"[DouyinParser] {client.name} 解析成功: {result.get('title', '')[ :30]}...")
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"[DouyinParser] {client.name} 解析失败: {e}")
            continue

    raise ValueError(f"所有客户端均解析失败。最后错误: {last_error}")


def _parse_with_client(url: str, client: HttpClient) -> Dict[str, Any]:
    """使用指定客户端解析"""
    # 1. 获取重定向后的长链接并提取 video_id
    r1 = client.get(url, headers={"User-Agent": ANDROID_CHROME_UA})
    r1.raise_for_status()
    vid = _vid(str(r1.url))
    logger.debug(f"[DouyinParser] 提取 video_id: {vid}")

    # 2. 请求移动端分享页
    share_url = f"https://www.iesdouyin.com/share/video/{vid}/"
    r2 = client.get(share_url, headers=MOBILE_HEADERS)
    r2.raise_for_status()

    # 3. 解析 _ROUTER_DATA
    data = _json(r2.text)
    return _info(data)


def _vid(raw: str) -> str:
    """从 URL 中提取 video_id"""
    return raw.split("?")[0].rstrip("/").split("/")[-1]


def _json(html: str) -> Dict[str, Any]:
    """从 HTML 中提取 window._ROUTER_DATA JSON"""
    m = re.search(r"window\._ROUTER_DATA\s*=\s*(.*?)\s*</script>", html, re.DOTALL)
    if not m:
        raise ValueError("HTML 中未找到 window._ROUTER_DATA")
    return json.loads(m.group(1).strip())


def _info(data: Dict[str, Any]) -> Dict[str, Any]:
    """从 _ROUTER_DATA 中提取视频信息"""
    items: Optional[list] = None
    for v in data.get("loaderData", {}).values():
        if isinstance(v, dict) and "videoInfoRes" in v:
            items = v["videoInfoRes"].get("item_list", [])
            break

    if not items:
        raise ValueError("item_list 为空（抖音 SSR 反爬：需要 Cookie）")

    item = items[0]
    vd = item.get("video", {})
    raw = _lst(vd, "play_addr", "url_list")
    url = raw[0] if raw else ""
    url = url.replace("playwm", "play")
    cover = _lst(vd, "cover", "url_list")
    cover = cover[0] if cover else ""
    author = item.get("author", {})
    name = author.get("nickname", "unknown")
    sec = author.get("sec_uid", "")
    avatar = _lst(author, "avatar_thumb", "url_list")
    avatar = avatar[0] if avatar else ""
    dur = vd.get("duration", 0)

    return {
        "video_url": url,
        "title": item.get("desc", ""),
        "author": name,
        "cover_url": cover,
        "duration": dur,
        "platform": "douyin",
        "sec_uid": sec,
        "avatar_url": avatar,
    }


def _lst(d: Dict[str, Any], k1: str, k2: str) -> list:
    """安全获取嵌套列表"""
    v = d.get(k1, {})
    v = v.get(k2, [])
    return v if isinstance(v, list) else []


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

