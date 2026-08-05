"""
微博平台插件

策略：yt-dlp 兜底（Cookie 文件可选）。
"""

from ...utils.logger import get_logger
from .base import YtDlpPlatform

logger = get_logger(__name__)


class WeiboPlatform(YtDlpPlatform):
    """微博"""

    name = "weibo"
    domains = ["weibo.com", "weibo.cn"]
