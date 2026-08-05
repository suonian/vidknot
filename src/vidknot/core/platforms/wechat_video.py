"""
微信视频号平台插件（预留接口）

视频号无法自动化抓取：微信生态封闭，需 putyy/res-downloader 等
桌面端抓包工具获取视频直链。此处仅注册域名识别并给出明确指引。
"""

from pathlib import Path
from typing import Any

from ...utils.exceptions import DownloadError
from ...utils.logger import get_logger
from .base import BasePlatform

logger = get_logger(__name__)


class WeChatVideoPlatform(BasePlatform):
    """微信视频号（预留，暂不可自动化）"""

    name = "wechat_video"
    domains = ["channels.weixin.qq.com", "finder.video.qq.com"]

    def download(
        self,
        url: str,
        dl: Any,
        quality: str = "bestaudio/best",
        force_audio: bool = False,
    ) -> tuple[Path | None, dict[str, Any]]:
        raise DownloadError(
            "微信视频号暂不支持自动下载。\n\n"
            "视频号链接处于微信封闭生态，无法通过 yt-dlp 直接解析。\n"
            "建议:\n"
            "1. 使用 res-downloader / putyy 等桌面端抓包工具导出视频文件\n"
            "2. 再用 vidknot 处理本地视频文件（阶段3 批量目录处理将支持）"
        )
