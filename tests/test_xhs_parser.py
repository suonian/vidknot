"""
测试 vidknot.core.xhs_parser（从小红书平台插件拆分的纯解析库）
"""

from vidknot.core import xhs_parser
from vidknot.core.platforms.xiaohongshu import XiaoHongShuPlatform


class TestExtractBalancedJson:
    def test_simple(self):
        assert xhs_parser.extract_balanced_json('{"a": 1}') == '{"a": 1}'

    def test_leading_whitespace(self):
        assert xhs_parser.extract_balanced_json('  \n {"a": 1} tail') == '{"a": 1}'

    def test_braces_in_string(self):
        text = '{"a": "}{"}x'
        assert xhs_parser.extract_balanced_json(text) == '{"a": "}{"}'

    def test_escaped_quote(self):
        text = '{"a": "\\""}x'
        assert xhs_parser.extract_balanced_json(text) == '{"a": "\\""}'

    def test_unbalanced_returns_none(self):
        assert xhs_parser.extract_balanced_json('{"a": 1') is None

    def test_not_json_returns_none(self):
        assert xhs_parser.extract_balanced_json('hello') is None


class TestExtractNoteId:
    def test_explore(self):
        assert xhs_parser.extract_note_id(
            "https://www.xiaohongshu.com/explore/64abc123def456"
        ) == "64abc123def456"

    def test_discovery(self):
        assert xhs_parser.extract_note_id(
            "https://www.xiaohongshu.com/discovery/item/abc123?xsec_token=x"
        ) == "abc123"

    def test_short_link(self):
        assert xhs_parser.extract_note_id("http://xhslink.com/a/abc123") == "abc123"

    def test_unknown(self):
        assert xhs_parser.extract_note_id("https://www.xiaohongshu.com/") == "unknown"


class TestExtractFromState:
    def test_images_and_title(self):
        html = (
            "<script>window.__INITIAL_STATE__ = "
            '{"note": {"noteDetailMap": {"abc": {"note": {'
            '"title": "测试标题",'
            '"imageList": [{"urlDefault": "https://sns-webpic.qc.xhscdn.com/a.jpg"}]'
            "}}}}}</script>"
        )
        title, images, video_url = xhs_parser.extract_from_state(html, "abc")
        assert title == "测试标题"
        assert images == ["https://sns-webpic.qc.xhscdn.com/a.jpg"]
        assert video_url is None

    def test_undefined_replaced(self):
        html = (
            "<script>window.__INITIAL_STATE__ = "
            '{"note": {"noteDetailMap": {"abc": {"note": {"title": undefined}}}}}'
            "</script>"
        )
        title, images, video_url = xhs_parser.extract_from_state(html, "abc")
        assert title == ""

    def test_no_state(self):
        assert xhs_parser.extract_from_state("<html></html>", "abc") == ("", [], None)


class TestExtractImagesByRegex:
    def test_matches_known_cdn(self):
        html = '"urlDefault":"https://sns-webpic.qc.xhscdn.com/202401/x.jpg"'
        assert xhs_parser.extract_images_by_regex(html) == [
            "https://sns-webpic.qc.xhscdn.com/202401/x.jpg"
        ]

    def test_dedup(self):
        html = '"urlDefault":"https://sns-img.b0.xhscdn.com/p.png" "url":"https://sns-img.b0.xhscdn.com/p.png"'
        assert len(xhs_parser.extract_images_by_regex(html)) == 1


class TestLoadCookies:
    def test_loads_xiaohongshu_cookies(self, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text(
            "# Netscape HTTP Cookie File\n"
            ".xiaohongshu.com\tTRUE\t/\tFALSE\t0\tweb_session\tabc123\n"
            "other.com\tTRUE\t/\tFALSE\t0\tfoo\tbar\n",
            encoding="utf-8",
        )
        cookies = xhs_parser.load_cookies(str(cookie_file))
        assert cookies == {"web_session": "abc123"}

    def test_missing_file(self):
        assert xhs_parser.load_cookies(None) is None
        assert xhs_parser.load_cookies("/nonexistent/path.txt") is None


class TestDelegateCompatibility:
    """类上的薄委托方法必须与 xhs_parser 行为一致（测试兼容层）"""

    def test_note_id_delegate(self):
        assert XiaoHongShuPlatform._extract_note_id(
            "https://www.xiaohongshu.com/explore/abc123"
        ) == xhs_parser.extract_note_id("https://www.xiaohongshu.com/explore/abc123")

    def test_from_state_delegate(self):
        html = "<script>window.__INITIAL_STATE__ = {\"note\": {}}</script>"
        assert XiaoHongShuPlatform._extract_from_state(html, "x") == (
            xhs_parser.extract_from_state(html, "x")
        )
