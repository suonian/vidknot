"""
Vimeo 平台插件

策略：yt-dlp 标准下载。
"""

from ...utils.logger import get_logger
from .base import YtDlpPlatform

logger = get_logger(__name__)


class VimeoPlatform(YtDlpPlatform):
    """Vimeo"""

    name = "vimeo"
    domains = ["vimeo.com"]
