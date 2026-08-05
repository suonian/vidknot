"""
平台插件注册表

平台插件架构：
- BasePlatform: 抽象基类（name/domains/can_handle/download/fetch_subtitle）
- PlatformRegistry: 注册表，按注册顺序遍历匹配 URL
- 新增平台只需：创建平台文件 + 在 register_default_platforms() 注册

用法:
    from vidknot.core.platforms import PlatformRegistry

    platform = PlatformRegistry.detect(url)
    audio_path, metadata = platform.download(url, downloader)
"""

from ...utils.logger import get_logger
from .base import BasePlatform, YtDlpPlatform
from .bilibili import BilibiliPlatform
from .douyin import DouyinPlatform
from .generic import GenericPlatform
from .instagram import InstagramPlatform
from .kuaishou import KuaishouPlatform
from .tiktok import TikTokPlatform
from .twitter import TwitterPlatform
from .vimeo import VimeoPlatform
from .wechat_video import WeChatVideoPlatform
from .weibo import WeiboPlatform
from .xiaohongshu import XiaoHongShuPlatform
from .youtube import YouTubePlatform

logger = get_logger(__name__)

__all__ = [
    "BasePlatform",
    "YtDlpPlatform",
    "PlatformRegistry",
    "YouTubePlatform",
    "DouyinPlatform",
    "BilibiliPlatform",
    "XiaoHongShuPlatform",
    "TikTokPlatform",
    "TwitterPlatform",
    "InstagramPlatform",
    "KuaishouPlatform",
    "WeiboPlatform",
    "VimeoPlatform",
    "WeChatVideoPlatform",
    "GenericPlatform",
]


class PlatformRegistry:
    """平台注册表：注册、检测、列举"""

    _platforms: list[BasePlatform] = []

    @classmethod
    def register(cls, platform: BasePlatform) -> None:
        """注册平台插件（重复 name 会被替换）"""
        cls._platforms = [p for p in cls._platforms if p.name != platform.name]
        cls._platforms.append(platform)

    @classmethod
    def detect(cls, url: str) -> BasePlatform:
        """按注册顺序检测 URL 所属平台，无匹配时返回通用兜底平台"""
        for platform in cls._platforms:
            if platform.name == "generic":
                continue
            if platform.can_handle(url):
                return platform
        return cls._get_generic()

    @classmethod
    def get(cls, name: str) -> BasePlatform | None:
        """按名称获取平台"""
        for platform in cls._platforms:
            if platform.name == name:
                return platform
        return None

    @classmethod
    def list_platforms(cls) -> list[str]:
        """列举所有已注册平台名称"""
        return [p.name for p in cls._platforms]

    @classmethod
    def _get_generic(cls) -> BasePlatform:
        generic = cls.get("generic")
        if generic is None:
            generic = GenericPlatform()
            cls.register(generic)
        return generic

    @classmethod
    def clear(cls) -> None:
        """清空注册表（测试用）"""
        cls._platforms = []


def register_default_platforms() -> None:
    """注册所有默认平台（具体平台在前，generic 兜底在最后）"""
    if PlatformRegistry._platforms:
        return
    for platform in (
        YouTubePlatform(),
        DouyinPlatform(),
        BilibiliPlatform(),
        XiaoHongShuPlatform(),
        TikTokPlatform(),
        TwitterPlatform(),
        InstagramPlatform(),
        KuaishouPlatform(),
        WeiboPlatform(),
        VimeoPlatform(),
        WeChatVideoPlatform(),
        GenericPlatform(),
    ):
        PlatformRegistry.register(platform)


# 模块导入时自动注册默认平台
register_default_platforms()
