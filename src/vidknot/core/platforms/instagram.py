"""
Instagram 平台插件

策略：yt-dlp + 浏览器 Cookie。
"""

from ...utils.logger import get_logger
from .base import YtDlpPlatform

logger = get_logger(__name__)


class InstagramPlatform(YtDlpPlatform):
    """Instagram"""

    name = "instagram"
    domains = ["instagram.com"]
    use_browser_cookie = True
