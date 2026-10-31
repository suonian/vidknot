"""YouTube 音频下载回退链回归测试

`prefer_subtitles=False` 或 `force_audio=True` 时走 `_download_audio_direct`，
它必须复用 `_download_audio` 的回退顺序：本地 Cookie 文件 → 无 Cookie
(SABR-only 兼容 extractor-args) → 浏览器 Cookie 嗅探。

直接跳到浏览器 Cookie 嗅探会在 Chrome 正在运行时硬失败——yt-dlp 无法复制
被占用的 Cookie 库（yt-dlp issue #7271），而此时无 Cookie 路径完全可用。
"""
from unittest.mock import MagicMock, patch

from vidknot.core.platforms.youtube import YouTubePlatform


def _dl_without_cookie_file():
    dl = MagicMock()
    dl._find_cookie_file.return_value = None
    return dl


class TestYoutubeDownloadAudioDirect:
    def test_prefers_no_cookie_path_over_browser_cookie(self):
        dl = _dl_without_cookie_file()
        with patch.object(
            YouTubePlatform, "_download_audio_no_cookie", return_value=("a.mp3", {"title": "t"})
        ) as no_cookie:
            path, meta = YouTubePlatform()._download_audio_direct(
                "https://youtu.be/x", dl, "bestaudio"
            )

        assert path == "a.mp3"
        no_cookie.assert_called_once()
        dl._download_with_browser_cookie.assert_not_called()

    def test_falls_back_to_browser_cookie_when_no_cookie_fails(self):
        dl = _dl_without_cookie_file()
        dl._download_with_browser_cookie.return_value = ("b.mp3", {"title": "t"})
        with patch.object(
            YouTubePlatform, "_download_audio_no_cookie", side_effect=Exception("sabr blocked")
        ):
            path, meta = YouTubePlatform()._download_audio_direct(
                "https://youtu.be/x", dl, "bestaudio"
            )

        assert path == "b.mp3"
        dl._download_with_browser_cookie.assert_called_once()

    def test_uses_cookie_file_first_when_present(self):
        dl = MagicMock()
        dl._find_cookie_file.return_value = "cookies/youtube.txt"
        dl._yt_dlp_download.return_value = ("c.mp3", {"title": "t"})

        path, meta = YouTubePlatform()._download_audio_direct(
            "https://youtu.be/x", dl, "bestaudio"
        )

        assert path == "c.mp3"
        dl._yt_dlp_download.assert_called_once()
