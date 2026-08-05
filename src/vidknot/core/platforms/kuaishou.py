"""
快手平台插件

策略：yt-dlp 兜底（Cookie 文件可选）。
已知限制：快手视频多需登录态，且部分短链需要解析跳转。
"""

from ...utils.logger import get_logger
from .base import YtDlpPlatform

logger = get_logger(__name__)


class KuaishouPlatform(YtDlpPlatform):
    """快手"""

    name = "kuaishou"
    domains = ["kuaishou.com"]
