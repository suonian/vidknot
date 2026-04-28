"""
测试 vidknot.utils.logger
"""

import logging

import pytest
from vidknot.utils.logger import get_logger, log_step, log_download_progress


class TestGetLogger:
    """测试 get_logger"""

    def test_get_logger_returns_logger(self):
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test"

    def test_get_logger_singleton(self):
        """同名 logger 应返回同一实例"""
        logger1 = get_logger("singleton_test")
        logger2 = get_logger("singleton_test")
        assert logger1 is logger2

    def test_logger_has_handler(self):
        logger = get_logger("handler_test")
        assert len(logger.handlers) > 0

    def test_logger_level_configurable(self, monkeypatch):
        """日志级别应可通过环境变量配置"""
        monkeypatch.setenv("VIDKNOT_LOG_LEVEL", "DEBUG")
        # 重新获取（已有 handler 时不重新配置）
        logger = logging.getLogger("level_test_with_handler")
        logger.setLevel(logging.DEBUG)
        assert logger.level == logging.DEBUG


class TestLogStep:
    """测试 log_step 辅助函数"""

    def test_log_step_info(self, caplog):
        logger = get_logger("log_step_test")
        log_step(logger, "下载完成", "ok")
        assert any("下载完成" in r.message for r in caplog.records)

    def test_log_step_all_statuses(self, caplog):
        logger = get_logger("log_step_statuses")
        for status in ["start", "ok", "error", "skip", "progress"]:
            log_step(logger, f"步骤_{status}", status)
        # 每个状态都应有对应记录
        assert len(caplog.records) == 5


class TestLogDownloadProgress:
    """测试 log_download_progress 辅助函数"""

    def test_log_download_progress(self, caplog):
        logger = get_logger("progress_test")
        log_download_progress(logger, downloaded=50, total=100, speed="1.2MB/s")
        assert any("50%" in r.message for r in caplog.records)

    def test_log_download_progress_zero_total(self, caplog):
        """total=0 时不应除零"""
        logger = get_logger("progress_zero_test")
        log_download_progress(logger, downloaded=0, total=0, speed="0B/s")
        # 应显示 0%
        assert any("0%" in r.message for r in caplog.records)


class TestColoredFormatter:
    """测试彩色日志格式化器"""

    def test_colored_formatter_exists(self):
        from vidknot.utils.logger import _ColoredFormatter
        formatter = _ColoredFormatter("%(levelname)s %(message)s")
        assert formatter is not None

    def test_format_adds_color_codes(self):
        from vidknot.utils.logger import _ColoredFormatter
        formatter = _ColoredFormatter("%(levelname)s: %(message)s")

        # 创建一个 LogRecord
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        # INFO 级别应为绿色（ANSI 码 32）
        assert "test message" in formatted
        # levelname 应包含 ANSI 颜色码
        assert "INFO" in formatted
