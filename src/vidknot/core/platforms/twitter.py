"""
Twitter/X 平台插件

策略：yt-dlp + 浏览器 Cookie。twikit 预留（无需 API key，未来可扩展）。
"""

from ...utils.logger import get_logger
from .base import YtDlpPlatform

logger = get_logger(__name__)


class TwitterPlatform(YtDlpPlatform):
    """Twitter/X"""

    name = "twitter"
    domains = ["twitter.com", "x.com"]
    use_browser_cookie = True

    def can_handle(self, url: str) -> bool:
        url_lower = url.lower()
        # x.com 太短容易误匹配，要求是独立域名
        if "x.com" in url_lower:
            return "x.com/" in url_lower or url_lower.rstrip("/").endswith("x.com")
        return "twitter.com" in url_lower
