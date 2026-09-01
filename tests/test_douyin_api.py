"""core/douyin_api.py 单元测试（无网络，httpx 全 mock）"""


import pytest

from vidknot.core import douyin_api
from vidknot.utils.exceptions import DownloadError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("vidknot.utils.retry.time.sleep", lambda s: None)


class TestParseApiResponse:
    def test_simple_path(self):
        data = {"data": {"video_url": "https://cdn.example.com/v.mp4"}}
        assert (
            douyin_api.parse_api_response(data, ["data", "video_url"], "test")
            == "https://cdn.example.com/v.mp4"
        )

    def test_list_index_path(self):
        data = {"data": {"url_list": ["https://a.mp4", "https://b.mp4"]}}
        assert (
            douyin_api.parse_api_response(data, ["data", "url_list", 0], "test")
            == "https://a.mp4"
        )

    def test_list_index_out_of_range(self):
        data = {"data": {"url_list": []}}
        assert douyin_api.parse_api_response(data, ["data", "url_list", 0], "test") is None

    def test_missing_key(self):
        assert douyin_api.parse_api_response({"data": {}}, ["data", "url"], "test") is None

    def test_non_str_value(self):
        data = {"data": {"url": 12345}}
        assert douyin_api.parse_api_response(data, ["data", "url"], "test") is None


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self):
        import httpx

        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=None, response=self
            )

    def json(self):
        return self._payload


class _FakeClient:
    """httpx.Client 替身：按预设响应序列返回"""

    responses: list = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    post = get

    def stream(self, method, url, **kwargs):
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


@pytest.fixture
def fake_httpx(monkeypatch):
    _FakeClient.responses = []
    monkeypatch.setattr(douyin_api.httpx, "Client", _FakeClient)
    return _FakeClient


API = {
    "name": "mockapi",
    "url": "https://mock.example/api",
    "method": "GET",
    "param_name": "url",
    "response_path": ["data", "video_url"],
    "timeout": 5,
}


class TestCallThirdPartyApi:
    def test_success(self, fake_httpx):
        fake_httpx.responses = [
            _FakeResponse(200, {"data": {"video_url": "https://cdn/v.mp4"}})
        ]
        assert (
            douyin_api.call_third_party_api("https://v.douyin.com/x", API)
            == "https://cdn/v.mp4"
        )

    def test_permanent_403_returns_none_without_retry(self, fake_httpx):
        fake_httpx.responses = [_FakeResponse(403, text="forbidden")]
        assert douyin_api.call_third_party_api("https://v.douyin.com/x", API) is None
        # 永久错误不应消耗更多响应
        assert fake_httpx.responses == []

    def test_server_error_retries_then_none(self, fake_httpx):
        fake_httpx.responses = [
            _FakeResponse(500, text="boom"),
            _FakeResponse(500, text="boom"),
            _FakeResponse(500, text="boom"),
        ]
        assert (
            douyin_api.call_third_party_api("https://v.douyin.com/x", API, max_retries=2)
            is None
        )
        # max_retries=2 → 总尝试 3 次
        assert fake_httpx.responses == []

    def test_timeout_retries_then_success(self, fake_httpx):
        import httpx

        fake_httpx.responses = [
            httpx.TimeoutException("timeout"),
            _FakeResponse(200, {"data": {"video_url": "https://cdn/v.mp4"}}),
        ]
        assert (
            douyin_api.call_third_party_api("https://v.douyin.com/x", API)
            == "https://cdn/v.mp4"
        )

    def test_unparseable_payload_returns_none(self, fake_httpx):
        fake_httpx.responses = [_FakeResponse(200, {"unexpected": True})]
        assert douyin_api.call_third_party_api("https://v.douyin.com/x", API) is None


class TestDownloadWithRetry:
    def test_file_too_small_raises_and_cleans(self, fake_httpx, tmp_path, monkeypatch):
        target = tmp_path / "video.mp4"

        class _BrokenStream:
            def raise_for_status(self):
                pass

            def iter_bytes(self, chunk_size=65536):
                yield b"tiny"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class _Client:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def stream(self, method, url):
                return _BrokenStream()

        monkeypatch.setattr(douyin_api.httpx, "Client", _Client)

        with pytest.raises(DownloadError, match="视频下载失败"):
            douyin_api.download_with_retry(
                "https://cdn/v.mp4", target, "mockapi", max_retries=0
            )
        assert not target.exists()

    def test_http_error_message_format(self, fake_httpx, tmp_path):
        import httpx

        target = tmp_path / "video.mp4"
        fake_httpx.responses = [httpx.ConnectError("refused")]

        with pytest.raises(DownloadError) as exc_info:
            douyin_api.download_with_retry(
                "https://cdn/v.mp4", target, "mockapi", max_retries=0
            )
        assert "mockapi 视频下载失败" in str(exc_info.value)
        assert "after 1 attempts" in str(exc_info.value)


class TestDelegateCompatibility:
    """DouyinPlatform 上的薄委托与模块函数行为一致"""

    def test_parse_delegate(self):
        from vidknot.core.platforms.douyin import DouyinPlatform

        data = {"data": {"url": "https://cdn/v.mp4"}}
        assert DouyinPlatform._parse_api_response(
            data, ["data", "url"], "x"
        ) == douyin_api.parse_api_response(data, ["data", "url"], "x")

    def test_call_delegate_routes_to_module(self, fake_httpx):
        from vidknot.core.platforms.douyin import DouyinPlatform

        fake_httpx.responses = [
            _FakeResponse(200, {"data": {"video_url": "https://cdn/v.mp4"}})
        ]
        assert (
            DouyinPlatform._call_third_party_api("https://v.douyin.com/x", API)
            == "https://cdn/v.mp4"
        )
