"""Tests for the f2 single-video download wrapper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.f2_helper_cli import (
    F2DownloadError,
    F2DownloadResult,
    download_one,
    find_downloaded_mp4,
    iesdouyin_share_url,
    read_cookie_file,
)

COOKIE_CONTENT = """\
# Netscape HTTP Cookie File
.douyin.com\tTRUE\t/\tFALSE\t1820022478\tfpk1\tabcdef123456789
.douyin.com\tTRUE\t/\tFALSE\t1820022478\tsessionid\tsess_xyz
# comment
"""


@pytest.fixture()
def cookie_file(tmp_path: Path) -> Path:
    p = tmp_path / "douyin.txt"
    p.write_text(COOKIE_CONTENT)
    return p


class TestReadCookieFile:
    def test_converts_netscape_to_string(self, cookie_file: Path):
        cookie_str = read_cookie_file(cookie_file)
        assert "fpk1=abcdef123456789" in cookie_str
        assert "sessionid=sess_xyz" in cookie_str

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_cookie_file(tmp_path / "missing.txt")

    def test_skips_comments_and_blanks(self, tmp_path: Path):
        p = tmp_path / "c.txt"
        p.write_text("\n# only comments\n\n")
        assert read_cookie_file(p) == ""


class TestIesdouyinShareUrl:
    def test_numeric_id_builds_url(self):
        assert (
            iesdouyin_share_url("7636872072064470298")
            == "https://www.iesdouyin.com/share/video/7636872072064470298/"
        )

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            iesdouyin_share_url("not-a-number")


class TestFindDownloadedMp4:
    def test_returns_none_when_root_missing(self, tmp_path: Path):
        assert find_downloaded_mp4(tmp_path / "no", "123") is None

    def test_finds_mp4_with_matching_aweme_id(self, tmp_path: Path):
        sub = tmp_path / "douyin" / "one" / "author"
        sub.mkdir(parents=True)
        target = sub / "2026-01-01_some_video.mp4"
        target.write_text("data")
        result = find_downloaded_mp4(tmp_path, "some")
        # Note: filename doesn't include aweme_id literally; falls back to mtime
        assert result == target

    def test_prefers_aweme_id_match(self, tmp_path: Path):
        sub = tmp_path / "douyin" / "one" / "author"
        sub.mkdir(parents=True)
        older = sub / "old_video.mp4"
        older.write_text("old")
        # Touch older to be older
        target = sub / "1234567890_video.mp4"
        target.write_text("new")
        os.utime(older, (1_000_000, 1_000_000))
        os.utime(target, (9_999_999, 9_999_999))
        result = find_downloaded_mp4(tmp_path, "1234567890")
        assert result == target


class TestDownloadOne:
    def test_raises_when_f2_binary_missing(self, tmp_path: Path, cookie_file: Path):
        with patch("scripts.f2_helper_cli.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_path.return_value.expanduser.return_value = mock_path.return_value
            with patch("scripts.f2_helper_cli.shutil.which", return_value=None):
                with pytest.raises(F2DownloadError, match="f2 executable not found"):
                    download_one("123", cookie_file=cookie_file)

    def test_returns_result_on_success(self, tmp_path: Path, cookie_file: Path):
        sub = tmp_path / "douyin" / "one" / "木子不写代码"
        sub.mkdir(parents=True)
        video = sub / "12345_some_clip_video.mp4"
        video.write_bytes(b"x" * 1024)

        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "完成\n"

        with patch("scripts.f2_helper_cli.subprocess.run", return_value=fake_proc):
            result = download_one(
                "12345",
                cookie_file=cookie_file,
                output_dir=tmp_path,
            )

        assert isinstance(result, F2DownloadResult)
        assert result.video_path == video
        assert result.aweme_id == "12345"

    def test_raises_on_subprocess_timeout(
        self, tmp_path: Path, cookie_file: Path
    ):
        with patch(
            "scripts.f2_helper_cli.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="f2", timeout=30),
        ):
            with pytest.raises(F2DownloadError, match="timed out"):
                download_one(
"12345",
                    cookie_file=cookie_file,
                    output_dir=tmp_path,
                    timeout_seconds=30,
                )

    def test_raises_when_no_video_written(
        self, tmp_path: Path, cookie_file: Path
    ):
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "完成\n"

        with patch("scripts.f2_helper_cli.subprocess.run", return_value=fake_proc):
            with pytest.raises(F2DownloadError, match="no \\*_video.mp4"):
                download_one(
"12345",
                    cookie_file=cookie_file,
                    output_dir=tmp_path,
                )



