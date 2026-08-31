"""
测试 vidknot.utils.retry 统一重试工具
"""

import pytest

from vidknot.utils import retry as retry_mod
from vidknot.utils.retry import (
    PERMANENT_HTTP_STATUS,
    RETRYABLE_HTTP_STATUS,
    get_network_config,
    retry_with_backoff,
)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """测试中不真实等待"""
    monkeypatch.setattr(retry_mod.time, "sleep", lambda _s: None)


class TestRetryWithBackoff:
    def test_success_first_try(self):
        calls = []

        def fn():
            calls.append(1)
            return "ok"

        assert retry_with_backoff(fn, tag="t") == "ok"
        assert len(calls) == 1

    def test_success_after_retries(self):
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("瞬断")
            return "ok"

        assert retry_with_backoff(fn, max_retries=2, tag="t") == "ok"
        assert len(calls) == 3

    def test_exhaust_retries_raises_last(self):
        calls = []

        def fn():
            calls.append(1)
            raise ValueError(f"第 {len(calls)} 次失败")

        with pytest.raises(ValueError, match="第 3 次失败"):
            retry_with_backoff(fn, max_retries=2, tag="t")
        assert len(calls) == 3

    def test_permanent_exception_not_retried(self):
        class Permanent(Exception):
            pass

        calls = []

        def fn():
            calls.append(1)
            raise Permanent("401")

        with pytest.raises(Permanent):
            retry_with_backoff(
                fn,
                max_retries=3,
                permanent_exceptions=(Permanent,),
                tag="t",
            )
        assert len(calls) == 1

    def test_non_retryable_exception_propagates(self):
        """不在 retryable_exceptions 中的异常直接抛出"""
        calls = []

        def fn():
            calls.append(1)
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            retry_with_backoff(fn, retryable_exceptions=(ValueError,), tag="t")
        assert len(calls) == 1

    def test_backoff_delays_exponential(self, monkeypatch):
        delays = []
        monkeypatch.setattr(retry_mod.time, "sleep", lambda s: delays.append(s))

        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            retry_with_backoff(
                fn, max_retries=3, backoff_base=1.0, backoff_factor=2.0, tag="t",
            )
        assert delays == [1.0, 2.0, 4.0]

    def test_max_delay_cap(self, monkeypatch):
        delays = []
        monkeypatch.setattr(retry_mod.time, "sleep", lambda s: delays.append(s))

        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            retry_with_backoff(
                fn, max_retries=6, backoff_base=1.0, backoff_factor=10.0,
                max_delay=30.0, tag="t",
            )
        assert all(d <= 30.0 for d in delays)


class TestHttpStatusSets:
    def test_permanent_set(self):
        assert PERMANENT_HTTP_STATUS == {401, 403, 404}

    def test_retryable_set(self):
        assert 429 in RETRYABLE_HTTP_STATUS
        assert 503 in RETRYABLE_HTTP_STATUS
        assert 200 not in RETRYABLE_HTTP_STATUS


class TestGetNetworkConfig:
    def test_defaults_without_manager(self):
        cfg = get_network_config(None)
        assert cfg["max_retries"] >= 0
        assert cfg["download_timeout"] >= 600
        assert cfg["http_timeout"] >= 30

    def test_defaults_not_below_legacy_hardcoded(self):
        """默认超时不得低于历史硬编码值，避免慢网络新增失败"""
        cfg = get_network_config(None)
        assert cfg["api_timeout"] >= 20
        assert cfg["http_timeout"] >= 30
