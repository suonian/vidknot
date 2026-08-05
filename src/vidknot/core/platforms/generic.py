"""
通用平台插件（兜底）

处理所有未被具体平台匹配的 URL，委托 yt-dlp 尝试下载。
"""

from ...utils.logger import get_logger
from .base import YtDlpPlatform

logger = get_logger(__name__)


class GenericPlatform(YtDlpPlatform):
    """通用 yt-dlp 兜底平台"""

    name = "generic"
    domains = []

    def can_handle(self, url: str) -> bool:
        """兜底平台：匹配所有 URL"""
        return bool(url)
