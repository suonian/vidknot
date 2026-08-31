"""
抖音第三方 API 客户端（Layer 3 支持模块）

从 core/platforms/douyin.py 抽取，职责：
- DEFAULT_THIRD_PARTY_APIS：默认可用的第三方解析 API 配置
- call_third_party_api()：调用单个 API 获取视频直链
  （指数退避重试走 utils.retry；401/403/404 永久错误立即短路）
- parse_api_response()：按 response_path 从 JSON 响应中提取直链
- download_with_retry()：流式下载直链（指数退避重试 + 文件大小校验）

四层降级的编排骨架仍保留在 DouyinPlatform（core/platforms/douyin.py）。
"""

from pathlib import Path
from typing import Any

import httpx

from ..utils.exceptions import DownloadError
from ..utils.logger import get_logger
from ..utils.retry import PERMANENT_HTTP_STATUS, retry_with_backoff

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


class _PermanentAPIError(Exception):
    """永久状态码（401/403/404）内部标记：重试器命中后立即中止"""


def call_third_party_api(
    url: str,
    api: dict[str, Any],
    max_retries: int = 2,
) -> str | None:
    """调用单个第三方 API 获取视频直链（指数退避重试）。

    重试策略:
    - 临时错误（429 限流 / 5xx 过载 / 网络超时）→ 指数退避重试
    - 永久错误（401 鉴权过期 / 403 无权限 / 404 不存在）→ 直接跳过

    Returns:
        视频直链；API 永久失败或重试耗尽时返回 None。
    """
    name = api["name"]
    api_url = api["url"]
    method = api.get("method", "GET").upper()
    param_name = api.get("param_name", "url")
    response_path = api.get("response_path", ["data", "url"])
    timeout = api.get("timeout", 15)
    headers = api.get("headers", {})

    def _request() -> dict:
        logger.debug(f"[Douyin-L3] 调用 {name}: {api_url}")
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            if method == "GET":
                resp = client.get(api_url, params={param_name: url}, headers=headers)
            else:
                resp = client.post(api_url, json={param_name: url}, headers=headers)

            # 永久错误 → 不重试
            if resp.status_code in PERMANENT_HTTP_STATUS:
                logger.warning(
                    f"[Douyin-L3] {name} 返回 {resp.status_code}"
                    f" (permanent, skip): {resp.text[:200]}"
                )
                raise _PermanentAPIError(f"{name} HTTP {resp.status_code}")

            resp.raise_for_status()
            return resp.json()

    try:
        data = retry_with_backoff(
            _request,
            max_retries=max_retries,
            backoff_base=1.0,
            permanent_exceptions=(_PermanentAPIError,),
            tag=f"Douyin-L3:{name}",
        )
    except _PermanentAPIError:
        return None
    except Exception as e:
        logger.warning(f"[Douyin-L3] {name} 重试 {max_retries} 次后仍失败: {str(e)[:150]}")
        return None

    return parse_api_response(data, response_path, name)


def parse_api_response(
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


def download_with_retry(
    video_url: str,
    video_path: Path,
    api_name: str,
    max_retries: int = 2,
    chunk_size: int = 65536,
    timeout: float = 90.0,
) -> None:
    """下载视频直链（指数退避重试）。

    TikHub / apibyte 返回的视频直链可能来自 CDN 缓存，偶尔临时不可达。
    加 2 次重试（1s / 2s 退避），避免因为 CDN 瞬断直接跳过该 API。

    Raises:
        DownloadError: 重试耗尽或下载文件异常（过小）。
    """

    def _once() -> None:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
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
        size = video_path.stat().st_size if video_path.exists() else 0
        video_path.unlink(missing_ok=True)
        raise DownloadError(f"视频文件异常 ({size} bytes)")

    try:
        retry_with_backoff(
            _once,
            max_retries=max_retries,
            backoff_base=1.0,
            tag=f"Douyin-L3:{api_name}",
        )
    except Exception as e:
        video_path.unlink(missing_ok=True)
        raise DownloadError(
            f"{api_name} 视频下载失败 (after {max_retries + 1} attempts): {str(e)[:200]}"
        )
