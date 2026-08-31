"""ContentProcessor 回归测试（float duration 格式化 bug）"""

import pytest

from vidknot.core.processor import ContentProcessor


def _make_processor():
    # 显式传参避免触发 ConfigManager / 网络
    return ContentProcessor(provider="openai", model="test-model", max_tokens=100)


class TestBuildPromptDuration:
    def test_float_duration_formats_without_error(self):
        """yt-dlp 返回 float 秒数时不应抛 ValueError（:02d 需要 int）"""
        proc = _make_processor()
        prompt = proc._build_prompt(
            "转录内容",
            {
                "title": "测试视频",
                "uploader": "作者",
                "url": "https://example.com/v",
                "duration": 294.0,  # float，此前触发 ValueError
                "platform": "bilibili",
            },
        )
        assert "00:04:54" in prompt

    def test_int_duration_still_works(self):
        proc = _make_processor()
        prompt = proc._build_prompt(
            "转录内容",
            {"title": "t", "uploader": "u", "duration": 3661, "platform": "youtube"},
        )
        assert "01:01:01" in prompt

    def test_missing_duration_shows_unknown(self):
        proc = _make_processor()
        prompt = proc._build_prompt("转录内容", {"title": "t", "platform": "unknown"})
        assert "未知" in prompt
