"""
统一重试与退避工具

为网络请求等易瞬断的操作提供指数退避重试。设计提炼自抖音平台适配器
（core/platforms/douyin.py）中经实战验证的手写重试模板：

- 指数退避（默认 1s / 2s / 4s ...）
- 永久错误（如 401/403/404 鉴权权限类）通过 permanent_exceptions 立即中止
- 零第三方依赖，不引入 tenacity

用法::

    from vidknot.utils.retry import retry_with_backoff

    data = retry_with_backoff(
        lambda: httpx.get(url).json(),
        max_retries=2,
        tag="douyin-api",
    )
"""

import time
from typing import Any, Callable, TypeVar

from .logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# HTTP 状态码语义分组（供调用方判断重试策略）
RETRYABLE_HTTP_STATUS: set[int] = {408, 429, 500, 502, 503, 504}
PERMANENT_HTTP_STATUS: set[int] = {401, 403, 404}


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_retries: int = 2,
    backoff_base: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple = (Exception,),
    permanent_exceptions: tuple = (),
    tag: str = "retry",
) -> T:
    """带指数退避的重试执行器。

    Args:
        fn: 无参可调用对象，成功时返回值即为返回结果。
        max_retries: 失败后的最大重试次数（总尝试次数 = max_retries + 1）。
        backoff_base: 首次重试前等待秒数。
        backoff_factor: 退避倍数，第 n 次重试前等待 backoff_base * backoff_factor ** (n-1)。
        max_delay: 单次等待上限，防止退避无限增长。
        retryable_exceptions: 触发重试的异常类型。
        permanent_exceptions: 永久错误类型，命中后原样抛出、不再重试
            （优先级高于 retryable_exceptions）。
        tag: 日志标签，便于定位重试来源。

    Returns:
        fn 成功时的返回值。

    Raises:
        permanent_exceptions 中的异常（原样抛出），或重试耗尽后
        最后一次遇到的可重试异常。
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except permanent_exceptions:
            raise
        except retryable_exceptions as e:
            last_exc = e
            if attempt < max_retries:
                delay = min(backoff_base * (backoff_factor ** attempt), max_delay)
                logger.warning(
                    f"[{tag}] 第 {attempt + 1} 次尝试失败，"
                    f"{delay:.1f}s 后重试: {str(e)[:200]}"
                )
                time.sleep(delay)

    raise last_exc


def get_network_config(config_manager: Any = None) -> dict[str, Any]:
    """读取 network 配置段（带安全默认值）。

    返回键：http_timeout / download_timeout / api_timeout /
    max_retries / backoff_base。
    """
    defaults = {
        "http_timeout": 30,
        "download_timeout": 600,
        "api_timeout": 20,
        "max_retries": 2,
        "backoff_base": 1.0,
    }
    if config_manager is None:
        try:
            from .config_manager import ConfigManager

            config_manager = ConfigManager()
        except Exception:
            return defaults
    try:
        section = config_manager.get("network") or {}
    except Exception:
        return defaults
    merged = dict(defaults)
    merged.update({k: v for k, v in section.items() if v is not None})
    return merged
