"""
测试 vidknot.core.platforms 平台插件架构

覆盖：
- PlatformRegistry 注册/检测/兜底
- 各平台 URL 识别
- YouTube 字幕优先三级策略
- 抖音三层 fallback
- 小红书笔记 ID 提取
- SubtitleExtractor 字幕解析
- VideoDownloader 委托 PlatformRegistry
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vidknot.core.platforms import PlatformRegistry
from vidknot.core.platforms.base import BasePlatform, YtDlpPlatform
from vidknot.core.platforms.bilibili import BilibiliPlatform
from vidknot.core.platforms.douyin import DouyinPlatform
from vidknot.core.platforms.generic import GenericPlatform
from vidknot.core.platforms.kuaishou import KuaishouPlatform
from vidknot.core.platforms.twitter import TwitterPlatform
from vidknot.core.platforms.wechat_video import WeChatVideoPlatform
from vidknot.core.platforms.weibo import WeiboPlatform
from vidknot.core.platforms.xiaohongshu import XiaoHongShuPlatform
from vidknot.core.platforms.youtube import YouTubePlatform
from vidknot.core.transcriber import (
    OpenAITranscribeASR,
    SiliconFlowASR,
    SubtitleExtractor,
    get_transcriber,
)
from vidknot.utils.exceptions import DownloadError, TranscriptionError


class TestPlatformRegistry:
    """测试 PlatformRegistry"""

    def test_default_platforms_registered(self):
        """默认平台应全部注册"""
        names = PlatformRegistry.list_platforms()
        for expected in (
            "youtube", "douyin", "bilibili", "xiaohongshu", "tiktok",
            "twitter", "instagram", "kuaishou", "weibo", "vimeo",
            "wechat_video", "generic",
        ):
            assert expected in names

    def test_detect_youtube(self):
        assert PlatformRegistry.detect("https://www.youtube.com/watch?v=dQw4w9WgXcQ").name == "youtube"
        assert PlatformRegistry.detect("https://youtu.be/dQw4w9WgXcQ").name == "youtube"

    def test_detect_douyin(self):
        assert PlatformRegistry.detect("https://v.douyin.com/iRNBho6u/").name == "douyin"
        assert PlatformRegistry.detect("https://www.iesdouyin.com/share/video/123").name == "douyin"

    def test_detect_bilibili(self):
        assert PlatformRegistry.detect("https://www.bilibili.com/video/BV1xx411c7mD").name == "bilibili"
        assert PlatformRegistry.detect("https://b23.tv/abc123").name == "bilibili"

    def test_detect_xiaohongshu(self):
        assert PlatformRegistry.detect("https://www.xiaohongshu.com/explore/abc123").name == "xiaohongshu"
        assert PlatformRegistry.detect("http://xhslink.com/a/abc123").name == "xiaohongshu"

    def test_detect_twitter(self):
        assert PlatformRegistry.detect("https://twitter.com/user/status/123").name == "twitter"
        assert PlatformRegistry.detect("https://x.com/user/status/123").name == "twitter"

    def test_detect_wechat_video(self):
        url = "https://channels.weixin.qq.com/web/pages/feed/abc"
        assert PlatformRegistry.detect(url).name == "wechat_video"

    def test_detect_generic_fallback(self):
        """未知 URL 应返回 generic 兜底"""
        platform = PlatformRegistry.detect("https://example.com/video/123")
        assert platform.name == "generic"

    def test_get_by_name(self):
        assert PlatformRegistry.get("youtube") is not None
        assert PlatformRegistry.get("nonexistent") is None

    def test_register_replaces_same_name(self):
        """重复注册同名平台应替换而非重复"""
        original = PlatformRegistry.get("generic")
        PlatformRegistry.register(GenericPlatform())
        names = PlatformRegistry.list_platforms()
        assert names.count("generic") == 1
        # 恢复
        PlatformRegistry.register(original)

    def test_generic_can_handle_anything(self):
        assert GenericPlatform().can_handle("https://anything.com/x")
        assert not GenericPlatform().can_handle("")


class TestBasePlatform:
    """测试 BasePlatform 基类行为"""

    def test_can_handle_domain_match(self):
        class FakePlatform(YtDlpPlatform):
            name = "fake"
            domains = ["fake.example.com"]

        p = FakePlatform()
        assert p.can_handle("https://fake.example.com/video")
        assert not p.can_handle("https://other.com/video")

    def test_can_handle_case_insensitive(self):
        class FakePlatform(YtDlpPlatform):
            name = "fake"
            domains = ["example.com"]

        assert FakePlatform().can_handle("https://EXAMPLE.COM/Video")

    def test_fetch_subtitle_default_none(self):
        """默认 fetch_subtitle 应返回 None"""

        class FakePlatform(BasePlatform):
            name = "fake"
            domains = ["fake.com"]

            def download(self, url, dl, quality="bestaudio/best", force_audio=False):
                return None, {}

        assert FakePlatform().fetch_subtitle("https://fake.com", MagicMock()) is None

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BasePlatform()


class TestYouTubePlatform:
    """测试 YouTube 平台"""

    def test_extract_video_id_watch_url(self):
        assert YouTubePlatform._extract_video_id(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"
        ) == "dQw4w9WgXcQ"

    def test_extract_video_id_short_url(self):
        assert YouTubePlatform._extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_extract_video_id_shorts(self):
        assert YouTubePlatform._extract_video_id(
            "https://www.youtube.com/shorts/abcdefghijk"
        ) == "abcdefghijk"

    def test_extract_video_id_embed_live(self):
        assert YouTubePlatform._extract_video_id(
            "https://www.youtube.com/embed/dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"
        assert YouTubePlatform._extract_video_id(
            "https://www.youtube.com/live/dQw4w9WgXcQ"
        ) == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid(self):
        assert YouTubePlatform._extract_video_id("https://www.youtube.com/channel/UC123") is None

    def _make_dl(self, prefer_subtitles=True):
        dl = MagicMock()
        dl.output_dir = Path("/tmp")

        def config_get(*keys, default=None):
            if keys[-1] == "prefer_subtitles":
                return prefer_subtitles
            if keys[-1] == "subtitle_languages":
                return ["zh", "en"]
            return default

        dl._config.get = MagicMock(side_effect=config_get)
        dl._find_cookie_file = MagicMock(return_value=None)
        return dl

    def test_download_subtitle_success_skips_audio(self):
        """Level1 字幕成功时返回 (None, metadata含subtitle_text/subtitle_segments)"""
        platform = YouTubePlatform()
        dl = self._make_dl()

        with patch.object(
            platform, "_fetch_via_transcript_api",
            return_value=[
                {"start": 0.0, "end": 1.2, "text": "这是官方"},
                {"start": 1.2, "end": 2.5, "text": "字幕文本"},
            ],
        ), patch.object(
            platform, "_fetch_metadata_only", return_value={"title": "测试", "platform": "youtube"}
        ):
            audio_path, metadata = platform.download("https://youtu.be/dQw4w9WgXcQ", dl)

        assert audio_path is None
        assert metadata["subtitle_text"] == "这是官方 字幕文本"
        assert metadata["transcription_source"] == "youtube_transcript_api"
        assert len(metadata["subtitle_segments"]) == 2
        dl._download_with_browser_cookie.assert_not_called()

    def test_download_force_audio_skips_subtitles(self):
        """force_audio=True 时直接下载音频"""
        platform = YouTubePlatform()
        dl = self._make_dl()
        dl._download_audio_no_cookie = MagicMock(side_effect=AssertionError("should not be called"))
        dl._download_with_browser_cookie = MagicMock(return_value=(Path("/tmp/a.mp3"), {"title": "t"}))

        audio_path, metadata = platform.download(
            "https://youtu.be/dQw4w9WgXcQ", dl, force_audio=True
        )

        assert audio_path == Path("/tmp/a.mp3")
        dl._download_audio_no_cookie.assert_not_called()
        dl._download_with_browser_cookie.assert_called_once()

    def test_download_prefer_subtitles_false(self):
        """prefer_subtitles=False 时直接下载音频"""
        platform = YouTubePlatform()
        dl = self._make_dl(prefer_subtitles=False)
        dl._download_audio_no_cookie = MagicMock(side_effect=AssertionError("should not be called"))
        dl._download_with_browser_cookie = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))

        platform.download("https://youtu.be/dQw4w9WgXcQ", dl)
        dl._download_audio_no_cookie.assert_not_called()
        dl._download_with_browser_cookie.assert_called_once()

    def test_download_level1_fail_level2_success(self):
        """Level1 失败后 Level2 (yt-dlp 字幕) 成功"""
        platform = YouTubePlatform()
        dl = self._make_dl()

        with patch.object(platform, "_fetch_via_transcript_api", return_value=None), patch(
            "vidknot.core.platforms.youtube.fetch_ytdlp_subtitles",
            return_value=("yt-dlp 提取的字幕", {"title": "t", "platform": "youtube"}),
        ):
            audio_path, metadata = platform.download("https://youtu.be/dQw4w9WgXcQ", dl)

        assert audio_path is None
        assert metadata["subtitle_text"] == "yt-dlp 提取的字幕"
        assert metadata["transcription_source"] == "yt_dlp_subtitle"

    def test_download_all_levels_fail_fallback_audio(self):
        """所有字幕层级失败后回退音频下载 (Hermes PR: 走完 3-tier fallback 链)"""
        platform = YouTubePlatform()
        dl = self._make_dl()
        # Hermes (PR #N): SABR-only bypass fails → falls back to browser cookie
        with patch.object(platform, "_fetch_via_transcript_api", return_value=None), patch(
            "vidknot.core.platforms.youtube.fetch_ytdlp_subtitles", return_value=(None, {})
        ), patch.object(
            platform, "_download_audio_no_cookie",
            side_effect=Exception("simulated SABR failure"),
        ) as mock_no_cookie:
            dl._download_with_browser_cookie = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
            audio_path, _ = platform.download("https://youtu.be/dQw4w9WgXcQ", dl)

        assert audio_path == Path("/tmp/a.mp3")
        assert mock_no_cookie.called
        dl._download_with_browser_cookie.assert_called_once()


class TestDouyinPlatform:
    """测试抖音平台三层 fallback"""

    def test_layer1_success(self):
        platform = DouyinPlatform()
        dl = MagicMock()
        platform._layer1_parse_and_download = MagicMock(
            return_value=(Path("/tmp/a.mp3"), {"platform": "douyin"})
        )

        audio_path, metadata = platform.download("https://v.douyin.com/x/", dl)
        assert audio_path == Path("/tmp/a.mp3")
        platform._layer1_parse_and_download.assert_called_once()

    def test_fallback_to_layer2(self):
        platform = DouyinPlatform()
        dl = MagicMock()
        platform._layer1_parse_and_download = MagicMock(side_effect=DownloadError("L1 fail"))
        platform._layer2_yt_dlp_with_cookie = MagicMock(
            return_value=(Path("/tmp/b.mp3"), {"platform": "douyin"})
        )

        audio_path, _ = platform.download("https://v.douyin.com/x/", dl)
        assert audio_path == Path("/tmp/b.mp3")

    def test_fallback_to_layer3_when_enabled(self):
        platform = DouyinPlatform()
        dl = MagicMock()
        dl._config.get = MagicMock(side_effect=lambda *k, default=None: (
            True if k[-1] == "enable_third_party" else default
        ))
        platform._layer1_parse_and_download = MagicMock(side_effect=DownloadError("L1 fail"))
        platform._layer2_yt_dlp_with_cookie = MagicMock(side_effect=DownloadError("L2 fail"))
        platform._layer3_third_party_api = MagicMock(
            return_value=(Path("/tmp/c.mp3"), {"platform": "douyin"})
        )

        audio_path, _ = platform.download("https://v.douyin.com/x/", dl)
        assert audio_path == Path("/tmp/c.mp3")

    def test_layer3_skipped_when_disabled(self):
        platform = DouyinPlatform()
        dl = MagicMock()
        dl._config.get = MagicMock(return_value=False)
        platform._layer1_parse_and_download = MagicMock(side_effect=DownloadError("L1 fail"))
        platform._layer2_yt_dlp_with_cookie = MagicMock(side_effect=DownloadError("L2 fail"))
        platform._layer3_third_party_api = MagicMock()

        with pytest.raises(DownloadError, match="所有策略均已尝试"):
            platform.download("https://v.douyin.com/x/", dl)

        platform._layer3_third_party_api.assert_not_called()

    def test_all_layers_fail_raises(self):
        platform = DouyinPlatform()
        dl = MagicMock()
        dl._config.get = MagicMock(return_value=True)
        platform._layer1_parse_and_download = MagicMock(side_effect=DownloadError("L1"))
        platform._layer2_yt_dlp_with_cookie = MagicMock(side_effect=DownloadError("L2"))
        platform._layer3_third_party_api = MagicMock(side_effect=DownloadError("L3"))

        with pytest.raises(DownloadError, match="所有策略均已尝试"):
            platform.download("https://v.douyin.com/x/", dl)


class TestXiaoHongShuPlatform:
    """测试小红书平台"""

    def test_extract_note_id_explore(self):
        assert XiaoHongShuPlatform._extract_note_id(
            "https://www.xiaohongshu.com/explore/64abc123def456"
        ) == "64abc123def456"

    def test_extract_note_id_discovery(self):
        assert XiaoHongShuPlatform._extract_note_id(
            "https://www.xiaohongshu.com/discovery/item/abc123"
        ) == "abc123"

    def test_extract_note_id_unknown(self):
        assert XiaoHongShuPlatform._extract_note_id("https://www.xiaohongshu.com/") == "unknown"

    def test_image_fail_fallback_ytdlp(self):
        """图片下载失败后回退 yt-dlp"""
        platform = XiaoHongShuPlatform()
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=None)
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/v.mp3"), {"platform": "xiaohongshu"}))
        platform._probe_note_type = MagicMock(return_value="image")
        platform._download_images = MagicMock(side_effect=DownloadError("no images"))

        audio_path, _ = platform.download("https://www.xiaohongshu.com/explore/x", dl)
        assert audio_path == Path("/tmp/v.mp3")

    def test_force_audio_skips_images(self):
        """force_audio 直接走 yt-dlp"""
        platform = XiaoHongShuPlatform()
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=None)
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/v.mp3"), {}))
        platform._probe_note_type = MagicMock(return_value="image")
        platform._download_images = MagicMock()

        platform.download("https://www.xiaohongshu.com/explore/x", dl, force_audio=True)
        platform._download_images.assert_not_called()
        platform._probe_note_type.assert_not_called()

    def test_ytdlp_fail_fallback_xhs_downloader(self):
        """yt-dlp 失败后尝试 XHS-Downloader（未安装时给出安装指引）"""
        platform = XiaoHongShuPlatform()
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=None)
        dl._yt_dlp_download = MagicMock(side_effect=DownloadError("yt-dlp fail"))
        platform._probe_note_type = MagicMock(return_value="image")
        platform._download_images = MagicMock(side_effect=DownloadError("no images"))

        try:
            import XHS_Downloader  # noqa: F401
            pytest.skip("XHS-Downloader 已安装，无法测试未安装分支")
        except ImportError:
            with pytest.raises(DownloadError, match="pip install xhs-downloader"):
                platform.download("https://www.xiaohongshu.com/explore/x", dl)

    def test_probe_video_type(self):
        """探测为视频笔记时走视频下载"""
        platform = XiaoHongShuPlatform()
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=None)
        platform._probe_note_type = MagicMock(return_value="video")
        platform._download_video = MagicMock(return_value=(Path("/tmp/v.mp3"), {"platform": "xiaohongshu", "is_video": True}))
        platform._download_images = MagicMock()

        audio_path, meta = platform.download("https://www.xiaohongshu.com/explore/x", dl)
        assert audio_path == Path("/tmp/v.mp3")
        assert meta["is_video"] is True
        platform._download_images.assert_not_called()

    def test_video_fail_fallback_ytdlp(self):
        """视频下载失败后回退 yt-dlp"""
        platform = XiaoHongShuPlatform()
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=None)
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/v.mp3"), {"platform": "xiaohongshu"}))
        platform._probe_note_type = MagicMock(return_value="video")
        platform._download_video = MagicMock(side_effect=DownloadError("video fail"))

        audio_path, _ = platform.download("https://www.xiaohongshu.com/explore/x", dl)
        assert audio_path == Path("/tmp/v.mp3")

    def test_extract_video_from_state(self):
        """从 __INITIAL_STATE__ 提取视频直链"""
        html = '''
        <script>window.__INITIAL_STATE__ = {
          "note": {
            "noteDetailMap": {
              "abc123": {
                "note": {
                  "title": "测试视频笔记",
                  "type": "video",
                  "video": {
                    "media": {
                      "stream": {
                        "h264": [
                          {"masterUrl": "https://sns-video-bd.xhscdn.com/stream/123/HD.mp4", "backupUrls": []}
                        ]
                      }
                    }
                  }
                }
              }
            }
          }
        };</script>
        '''
        title, images, video_url = XiaoHongShuPlatform._extract_from_state(html, "abc123")
        assert title == "测试视频笔记"
        assert images == []
        assert video_url == "https://sns-video-bd.xhscdn.com/stream/123/HD.mp4"

    def test_extract_video_fallback_h265(self):
        """h264 不可用时回退 h265"""
        html = '''
        <script>window.__INITIAL_STATE__ = {
          "note": {
            "noteDetailMap": {
              "abc123": {
                "note": {
                  "title": "h265 only",
                  "video": {
                    "media": {
                      "stream": {
                        "h265": [
                          {"masterUrl": "https://sns-video-bd.xhscdn.com/stream/456/h265.m3u8"}
                        ]
                      }
                    }
                  }
                }
              }
            }
          }
        };</script>
        '''
        _, _, video_url = XiaoHongShuPlatform._extract_from_state(html, "abc123")
        assert video_url == "https://sns-video-bd.xhscdn.com/stream/456/h265.m3u8"

    def test_extract_video_uses_backup_urls(self):
        """无 masterUrl 时用 backupUrls"""
        html = '''
        <script>window.__INITIAL_STATE__ = {
          "note": {
            "noteDetailMap": {
              "abc123": {
                "note": {
                  "video": {
                    "media": {
                      "stream": {
                        "h264": [
                          {"backupUrls": ["https://sns-video-al.xhscdn.com/stream/789/HD.mp4"]}
                        ]
                      }
                    }
                  }
                }
              }
            }
          }
        };</script>
        '''
        _, _, video_url = XiaoHongShuPlatform._extract_from_state(html, "abc123")
        assert video_url == "https://sns-video-al.xhscdn.com/stream/789/HD.mp4"


class TestTikTokPlatform:
    """测试 TikTok 平台（cobalt 可选）"""

    def test_no_cobalt_uses_ytdlp(self):
        from vidknot.core.platforms.tiktok import TikTokPlatform

        platform = TikTokPlatform()
        dl = MagicMock()
        dl._config.get = MagicMock(return_value=None)
        dl._download_with_browser_cookie = MagicMock(return_value=(Path("/tmp/t.mp3"), {}))

        audio_path, _ = platform.download("https://www.tiktok.com/@u/video/1", dl)
        assert audio_path == Path("/tmp/t.mp3")
        dl._download_with_browser_cookie.assert_called_once()

    def test_cobalt_success(self):
        from vidknot.core.platforms.tiktok import TikTokPlatform

        platform = TikTokPlatform()
        dl = MagicMock()
        dl._config.get = MagicMock(return_value="https://cobalt.example/api/json")
        platform._download_via_cobalt = MagicMock(return_value=(Path("/tmp/c.mp3"), {}))

        audio_path, _ = platform.download("https://www.tiktok.com/@u/video/1", dl)
        assert audio_path == Path("/tmp/c.mp3")
        platform._download_via_cobalt.assert_called_once()

    def test_cobalt_fail_fallback_ytdlp(self):
        from vidknot.core.platforms.tiktok import TikTokPlatform

        platform = TikTokPlatform()
        dl = MagicMock()
        dl._config.get = MagicMock(return_value="https://cobalt.example/api/json")
        platform._download_via_cobalt = MagicMock(side_effect=DownloadError("cobalt fail"))
        dl._download_with_browser_cookie = MagicMock(return_value=(Path("/tmp/t.mp3"), {}))

        audio_path, _ = platform.download("https://www.tiktok.com/@u/video/1", dl)
        assert audio_path == Path("/tmp/t.mp3")


class TestOtherPlatforms:
    """测试其他平台"""

    def test_twitter_can_handle(self):
        p = TwitterPlatform()
        assert p.can_handle("https://twitter.com/user/status/1")
        assert p.can_handle("https://x.com/user/status/1")
        assert not p.can_handle("https://example.com/x/com")

    def test_wechat_video_raises(self):
        """视频号应抛出明确错误"""
        with pytest.raises(DownloadError, match="暂不支持自动下载"):
            WeChatVideoPlatform().download("https://channels.weixin.qq.com/x", MagicMock())

    def test_ytdlp_platform_browser_cookie_path(self):
        """use_browser_cookie 平台应调 _download_with_browser_cookie"""

        class FakeCookiePlatform(YtDlpPlatform):
            name = "fake"
            domains = ["fake.com"]
            use_browser_cookie = True

        dl = MagicMock()
        dl._download_with_browser_cookie = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
        FakeCookiePlatform().download("https://fake.com/v", dl)
        dl._download_with_browser_cookie.assert_called_once()

    def test_ytdlp_platform_cookie_file_path(self):
        """普通平台应走 Cookie 文件路径并清理临时 Cookie"""
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value="/tmp/temp_cookies.txt")
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))

        class FakePlatform(YtDlpPlatform):
            name = "fake"
            domains = ["fake.com"]

        with patch.object(Path, "exists", return_value=False):
            FakePlatform().download("https://fake.com/v", dl)
        dl._yt_dlp_download.assert_called_once()


class TestUnverifiedPlatforms:
    """⚠️ 未经实战验证平台（快手 / 微博 / B站）的 mock 级行为测试（无网络）"""

    def test_kuaishou_domains(self):
        p = KuaishouPlatform()
        assert p.can_handle("https://www.kuaishou.com/short-video/3xabc")
        assert not p.can_handle("https://example.com/kuaishou")

    def test_kuaishou_cookie_file_path(self):
        """快手走 YtDlpPlatform 标准 Cookie 文件路径"""
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=None)
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
        KuaishouPlatform().download("https://www.kuaishou.com/v", dl)
        dl._yt_dlp_download.assert_called_once()

    def test_kuaishou_temp_cookie_cleanup(self, tmp_path):
        """临时 Cookie 文件在结束后应被清理"""
        cookie = tmp_path / "temp_cookies_ks.txt"
        cookie.write_text("cookie")
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=str(cookie))
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
        KuaishouPlatform().download("https://www.kuaishou.com/v", dl)
        assert not cookie.exists()

    def test_weibo_domains(self):
        p = WeiboPlatform()
        assert p.can_handle("https://weibo.com/123/abc")
        assert p.can_handle("https://m.weibo.cn/detail/123")
        assert not p.can_handle("https://example.com/weibo")

    def test_weibo_cookie_file_path(self):
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=None)
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
        WeiboPlatform().download("https://weibo.com/123/abc", dl)
        dl._yt_dlp_download.assert_called_once()

    def test_weibo_temp_cookie_cleanup(self, tmp_path):
        cookie = tmp_path / "temp_cookies_wb.txt"
        cookie.write_text("cookie")
        dl = MagicMock()
        dl._try_export_cookies = MagicMock(return_value=str(cookie))
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
        WeiboPlatform().download("https://weibo.com/123/abc", dl)
        assert not cookie.exists()

    def test_bilibili_subtitle_priority_success(self):
        """字幕优先：拿到 CC 字幕时直接返回文本，不下载音频"""
        dl = MagicMock()
        p = BilibiliPlatform()
        p._fetch_subtitles = MagicMock(return_value=("字幕正文", {"title": "t"}))
        audio, metadata = p.download("https://www.bilibili.com/video/BV1x", dl)
        assert audio is None
        assert metadata["subtitle_text"] == "字幕正文"
        assert metadata["transcription_source"] == "bilibili_cc_subtitle"

    def test_bilibili_subtitle_fail_fallback_cookie_file(self):
        """字幕失败 → 有 Cookie 文件时走 yt-dlp 下载"""
        dl = MagicMock()
        dl._find_cookie_file = MagicMock(return_value="/cookies/bilibili.txt")
        dl._yt_dlp_download = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
        p = BilibiliPlatform()
        p._fetch_subtitles = MagicMock(side_effect=DownloadError("无字幕"))
        p.download("https://www.bilibili.com/video/BV1x", dl)
        dl._yt_dlp_download.assert_called_once()
        dl._download_with_browser_cookie.assert_not_called()

    def test_bilibili_subtitle_fail_fallback_browser_cookie(self):
        """字幕失败且无 Cookie 文件 → 走浏览器 Cookie 下载"""
        dl = MagicMock()
        dl._find_cookie_file = MagicMock(return_value=None)
        dl._download_with_browser_cookie = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
        p = BilibiliPlatform()
        p._fetch_subtitles = MagicMock(side_effect=DownloadError("无字幕"))
        p.download("https://www.bilibili.com/video/BV1x", dl)
        dl._download_with_browser_cookie.assert_called_once()

    def test_bilibili_force_audio_skips_subtitles(self):
        """force_audio=True 时跳过字幕优先，直接下载音频"""
        dl = MagicMock()
        dl._find_cookie_file = MagicMock(return_value=None)
        dl._download_with_browser_cookie = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))
        p = BilibiliPlatform()
        p._fetch_subtitles = MagicMock()
        p.download("https://www.bilibili.com/video/BV1x", dl, force_audio=True)
        p._fetch_subtitles.assert_not_called()
        dl._download_with_browser_cookie.assert_called_once()


class TestSubtitleExtractor:
    """测试字幕解析器"""

    def test_parse_srt(self, temp_dir):
        srt = temp_dir / "test.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\n大家好\n\n"
            "2\n00:00:03,500 --> 00:00:05,000\n欢迎观看\n",
            encoding="utf-8",
        )
        result = SubtitleExtractor().extract(srt)
        assert result == "大家好 欢迎观看"

    def test_parse_vtt_with_tags(self, temp_dir):
        vtt = temp_dir / "test.vtt"
        vtt.write_text(
            "WEBVTT\nKind: captions\nLanguage: zh\n\n"
            "00:00:01.000 --> 00:00:03.000\n<c>你好</c>世界\n\n"
            "00:00:03.000 --> 00:00:05.000\n你好世界\n",
            encoding="utf-8",
        )
        result = SubtitleExtractor().extract(vtt)
        # 标签去除 + 重复行去重
        assert result == "你好世界"

    def test_parse_dedup(self, temp_dir):
        srt = temp_dir / "dup.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\n重复行\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\n重复行\n\n"
            "3\n00:00:03,000 --> 00:00:04,000\n新内容\n",
            encoding="utf-8",
        )
        assert SubtitleExtractor().extract(srt) == "重复行 新内容"

    def test_unsupported_format(self, temp_dir):
        f = temp_dir / "test.txt"
        f.write_text("hello", encoding="utf-8")
        with pytest.raises(TranscriptionError, match="不支持的字幕格式"):
            SubtitleExtractor().extract(f)

    def test_missing_file(self):
        with pytest.raises(TranscriptionError, match="字幕文件不存在"):
            SubtitleExtractor().extract("/nonexistent/sub.srt")


class TestTranscriberFactory:
    """测试 get_transcriber 工厂"""

    def test_openai_whisper_provider(self):
        assert isinstance(get_transcriber("openai_whisper"), OpenAITranscribeASR)

    def test_siliconflow_provider(self):
        assert isinstance(get_transcriber("siliconflow"), SiliconFlowASR)

    def test_unknown_provider_fallback(self):
        assert isinstance(get_transcriber("unknown_xyz"), SiliconFlowASR)

    def test_openai_whisper_no_key_raises(self, temp_dir):
        """无 API Key 时应抛 NoAPIKeyError"""
        from vidknot.utils.exceptions import NoAPIKeyError

        audio = temp_dir / "a.mp3"
        audio.write_bytes(b"x" * 2048)

        import os
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(NoAPIKeyError):
                OpenAITranscribeASR().transcribe(audio)
        finally:
            if saved is not None:
                os.environ["OPENAI_API_KEY"] = saved


class TestDownloaderDelegation:
    """测试 VideoDownloader 委托 PlatformRegistry"""

    def test_download_sync_delegates_to_platform(self):
        from vidknot.core.downloader import VideoDownloader

        downloader = VideoDownloader()
        mock_platform = MagicMock()
        mock_platform.name = "mock"
        mock_platform.download = MagicMock(return_value=(Path("/tmp/a.mp3"), {"title": "t"}))

        with patch(
            "vidknot.core.platforms.PlatformRegistry.detect", return_value=mock_platform
        ):
            audio_path, metadata = downloader.download_audio_with_metadata("https://x.com/v")

        assert audio_path == Path("/tmp/a.mp3")
        mock_platform.download.assert_called_once()
        _, kwargs = mock_platform.download.call_args
        assert kwargs.get("force_audio") is False

    def test_download_sync_force_audio_passthrough(self):
        from vidknot.core.downloader import VideoDownloader

        downloader = VideoDownloader()
        mock_platform = MagicMock()
        mock_platform.download = MagicMock(return_value=(Path("/tmp/a.mp3"), {}))

        with patch(
            "vidknot.core.platforms.PlatformRegistry.detect", return_value=mock_platform
        ):
            downloader.download_audio_with_metadata("https://x.com/v", force_audio=True)

        _, kwargs = mock_platform.download.call_args
        assert kwargs.get("force_audio") is True

    def test_detect_platform_compat(self):
        """_detect_platform 兼容接口应返回平台名"""
        from vidknot.core.downloader import VideoDownloader

        downloader = VideoDownloader()
        assert downloader._detect_platform("https://www.youtube.com/watch?v=x") == "youtube"
        assert downloader._detect_platform("https://unknown-site.com/v") == "unknown"
