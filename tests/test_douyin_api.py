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

            def stream(self, method, url, **kwargs):
                return _BrokenStream()

        monkeypatch.setattr(douyin_api.httpx, "Client", _Client)

        with pytest.raises(DownloadError, match=r"视频文件异常 \(4 bytes\)"):
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

    def test_sends_douyin_cdn_headers(self, tmp_path):
        target = tmp_path / "video.mp4"
        captured = {}

        class _FakeStream:
            def __init__(self, method, url, headers=None):
                captured["method"] = method
                captured["url"] = url
                captured["headers"] = headers or {}

            def raise_for_status(self):
                pass

            def iter_bytes(self, chunk_size=65536):
                # 写入超过 1024 bytes 触发「下载成功」分支
                yield b"x" * 2048

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class _FakeClient:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def stream(self, method, url, headers=None):
                return _FakeStream(method, url, headers)

        original_client = douyin_api.httpx.Client
        douyin_api.httpx.Client = _FakeClient
        try:
            douyin_api.download_with_retry(
                "https://v3-web.douyinvod.com/x.mp4",
                target,
                "tikhub",
                max_retries=0,
            )
        finally:
            douyin_api.httpx.Client = original_client

        # 断言带上了抖音 CDN 必需的 headers
        headers = captured["headers"]
        assert "Referer" in headers, f"missing Referer in {headers}"
        assert headers["Referer"] == "https://www.douyin.com/"
        assert "User-Agent" in headers, f"missing User-Agent in {headers}"
        assert "iPhone" in headers["User-Agent"]
        assert target.exists()
        assert target.stat().st_size > 1024

    def test_headers_survive_retry_and_redirect(self, tmp_path, monkeypatch):
        import httpx

        target = tmp_path / "video.mp4"
        initial_url = "https://cdn.example.com/start"
        redirected_url = "https://media.example.com/video.mp4"
        requests = []

        def respond(request):
            requests.append(request)
            if len(requests) == 1:
                raise httpx.ReadTimeout("timeout", request=request)
            if str(request.url) == initial_url:
                return httpx.Response(302, headers={"Location": redirected_url})
            return httpx.Response(200, content=b"x" * 2048)

        real_client = httpx.Client
        monkeypatch.setattr(
            douyin_api.httpx,
            "Client",
            lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
        )
        douyin_api.download_with_retry(initial_url, target, "tikhub", max_retries=1)

        assert [str(request.url) for request in requests] == [
            initial_url, initial_url, redirected_url,
        ]
        for request in requests:
            assert request.headers["Referer"] == "https://www.douyin.com/"
            assert "iPhone" in request.headers["User-Agent"]
            assert "Authorization" not in request.headers
            assert "Cookie" not in request.headers
        assert target.read_bytes() == b"x" * 2048


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
