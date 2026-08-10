"""Tests for the Douyin cookie health check."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from vidknot.utils.cookie_health_check import (
    HealthReport,
    HealthStatus,
    check_cookie_health,
    write_health_flag,
)

COOKIE_CONTENT = """\
.douyin.com\tTRUE\t/\tFALSE\t1820022478\tfpk1\tabcdef123456789
.douyin.com\tTRUE\t/\tFALSE\t1820022478\tsessionid\tsess_xyz
"""


@pytest.fixture()
def cookie_file(tmp_path: Path) -> Path:
    p = tmp_path / "douyin.txt"
    p.write_text(COOKIE_CONTENT)
    return p


class TestCheckCookieHealth:
    def test_missing_cookie_is_expired(self, tmp_path: Path):
        report = check_cookie_health(tmp_path / "missing.txt")
        assert report.status is HealthStatus.EXPIRED
        assert "not found" in report.detail

    def test_200_response_is_healthy(self, cookie_file: Path):
        fake_proc = patch("subprocess.run")
        with fake_proc as mock_run:
            mock_run.return_value.stdout = "200"
            mock_run.return_value.returncode = 0
            report = check_cookie_health(cookie_file)
        assert report.status is HealthStatus.HEALTHY

    def test_403_response_is_expired(self, cookie_file: Path):
        fake_proc = patch("subprocess.run")
        with fake_proc as mock_run:
            mock_run.return_value.stdout = "403"
            mock_run.return_value.returncode = 0
            report = check_cookie_health(cookie_file)
        assert report.status is HealthStatus.EXPIRED

    def test_404_response_is_expired(self, cookie_file: Path):
        fake_proc = patch("subprocess.run")
        with fake_proc as mock_run:
            mock_run.return_value.stdout = "404"
            mock_run.return_value.returncode = 0
            report = check_cookie_health(cookie_file)
        assert report.status is HealthStatus.EXPIRED

    def test_5xx_response_is_warning(self, cookie_file: Path):
        fake_proc = patch("subprocess.run")
        with fake_proc as mock_run:
            mock_run.return_value.stdout = "502"
            mock_run.return_value.returncode = 0
            report = check_cookie_health(cookie_file)
        assert report.status is HealthStatus.WARNING

    def test_timeout_is_expired(self, cookie_file: Path):
        with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired(cmd="curl", timeout=30)):
            report = check_cookie_health(cookie_file)
        assert report.status is HealthStatus.EXPIRED

    def test_curl_missing_is_warning(self, cookie_file: Path):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            report = check_cookie_health(cookie_file)
        assert report.status is HealthStatus.WARNING


class TestWriteHealthFlag:
    def test_writes_json_to_flag_path(self, tmp_path: Path):
        report = HealthReport(
            status=HealthStatus.HEALTHY,
            aweme_id="123",
            detail="HTTP 200",
        )
        flag_path = write_health_flag(tmp_path, report, date="20260810")
        assert flag_path.exists()
        assert flag_path.name == "20260810.flag"
        data = json.loads(flag_path.read_text())
        assert data["status"] == "healthy"
        assert data["aweme_id"] == "123"

    def test_creates_flag_dir_if_missing(self, tmp_path: Path):
        report = HealthReport(
            status=HealthStatus.EXPIRED,
            aweme_id="123",
            detail="HTTP 403",
        )
        flag_dir = tmp_path / "deeply" / "nested" / "flags"
        write_health_flag(flag_dir, report, date="20260810")
        assert flag_dir.exists()
