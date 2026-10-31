"""跨平台兼容性回归测试

覆盖 macOS（开发平台）与 Windows（运行平台）之间会真实出问题的差异：
- Windows 保留设备名（CON / NUL / AUX / COM1 / LPT1 ...）
- 标准流编码（MCP stdio 要求 UTF-8，Windows 默认是本地代码页）
- POSIX 专属路径（curl -o /dev/null）
- JS 运行时的跨平台文件名（deno.exe vs deno）
"""
import io
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vidknot.utils import filename as filename_util
from vidknot.utils.stdio import ensure_utf8_stdio, stdio_encodings


class TestWindowsReservedNames:
    """Windows 保留设备名带扩展名仍然保留：

    写 "CON.md" 时内容会进控制台、文件根本不生成，删除还报拒绝访问。
    """

    @pytest.mark.parametrize(
        "name",
        ["CON", "con", "NUL", "nul", "AUX", "PRN", "COM1", "com9", "LPT1", "lpt9"],
    )
    def test_reserved_names_are_detected(self, name):
        assert filename_util.is_windows_reserved_name(name) is True

    @pytest.mark.parametrize(
        "name",
        ["CON.md", "NUL.md", "AUX.txt", "COM1.log", "CON.txt.md"],
    )
    def test_reserved_with_extension_is_detected(self, name):
        assert filename_util.is_windows_reserved_name(name) is True

    @pytest.mark.parametrize(
        "name",
        ["20261031_CON", "CONCERT", "笔记", "normal.md", "COM10", "LPT10", "", "我的NUL视频"],
    )
    def test_normal_names_are_not_reserved(self, name):
        assert filename_util.is_windows_reserved_name(name) is False

    def test_sanitize_escapes_reserved_name(self):
        assert filename_util.sanitize_filename("CON", fallback="笔记") == "_CON"

    def test_sanitize_keeps_normal_name(self):
        assert filename_util.sanitize_filename("第1章 开场", fallback="笔记") == "第1章_开场"

    def test_sanitize_fallback_when_empty(self):
        assert filename_util.sanitize_filename("", fallback="笔记") == "笔记"

    def test_obsidian_writer_generates_safe_filename(self, tmp_path):
        from vidknot.adapters.obsidian_writer import ObsidianWriter

        writer = ObsidianWriter(vault_path=str(tmp_path))
        assert writer._sanitize_filename("CON") == "_CON"
        assert writer._sanitize_filename("NUL") == "_NUL"

    def test_downloader_sanitize_escapes_reserved_name(self, tmp_path):
        from vidknot.core.downloader import VideoDownloader

        dl = VideoDownloader(output_dir=str(tmp_path))
        assert dl._sanitize_filename("CON") == "_CON"
        assert dl._sanitize_filename("NUL") == "_NUL"


class _FakeStream:
    """模拟一个编码为 GBK 的标准流。"""

    def __init__(self, encoding="gbk"):
        self.encoding = encoding
        self.reconfigured = None

    def reconfigure(self, encoding=None, errors=None):
        self.reconfigured = (encoding, errors)
        self.encoding = encoding


class TestStdioUtf8:
    def test_reconfigures_non_utf8_stream(self):
        stream = _FakeStream("gbk")
        with patch.object(sys, "stdout", stream):
            with patch.object(sys, "stderr", _FakeStream("gbk")):
                with patch.object(sys, "stdin", _FakeStream("gbk")):
                    ensure_utf8_stdio()
        assert stream.reconfigured == ("utf-8", "replace")

    def test_leaves_utf8_stream_untouched(self):
        stream = _FakeStream("utf-8")
        with patch.object(sys, "stdout", stream):
            with patch.object(sys, "stderr", _FakeStream("utf-8")):
                with patch.object(sys, "stdin", _FakeStream("utf-8")):
                    ensure_utf8_stdio()
        assert stream.reconfigured is None

    def test_handles_stream_without_reconfigure(self):
        class NoReconfigure:
            encoding = "gbk"

        with patch.object(sys, "stdout", NoReconfigure()):
            with patch.object(sys, "stderr", NoReconfigure()):
                with patch.object(sys, "stdin", NoReconfigure()):
                    ensure_utf8_stdio()  # 不应抛异常

    def test_stdio_encodings_reports_three_streams(self):
        enc = stdio_encodings()
        assert set(enc) == {"stdin", "stdout", "stderr"}

    def test_real_streams_become_utf8_even_when_env_encoding_is_not(self):
        """即使环境编码不是 UTF-8，调用后标准流也应为 UTF-8。

        必须在子进程里做：pytest 会替换 sys.stdout/sys.stdin（capture），
        宿主机又是「管道到 UTF-8 控制台」或「cp1252」各不相同，直接断言
        当前进程的真实流编码只会得到一个依赖运行环境的假结果。
        这里用 PYTHONIOENCODING=cp1252 造一个确定的非 UTF-8 环境，
        再断言子进程调用后自报 utf-8。
        """
        code = (
            "import sys;"
            "from vidknot.utils.stdio import ensure_utf8_stdio;"
            "ensure_utf8_stdio();"
            "print(sys.stdout.encoding);"
            "print(sys.stderr.encoding)"
        )
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "cp1252"
        env.pop("PYTHONUTF8", None)
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=120,
        )
        encodings = [
            line.strip().lower() for line in proc.stdout.splitlines() if line.strip()
        ]
        assert encodings, (
            f"子进程无输出 (rc={proc.returncode}): {proc.stderr[:300]}"
        )
        assert all(enc in ("utf-8", "utf8") for enc in encodings), encodings

    def test_stdio_encodings_never_raise_on_real_streams(self):
        """在真实进程里调用不得抛异常，且三个流都要能被报告"""
        ensure_utf8_stdio()
        enc = stdio_encodings()
        assert set(enc) == {"stdin", "stdout", "stderr"}
        for name, value in enc.items():
            assert isinstance(value, str) and value, name


class TestCurlUsesOsDevnull:
    """curl -o /dev/null 在 Windows 上会报 "client returned ERROR on write"（退出码 23）。"""

    def test_uses_os_devnull(self, tmp_path):
        from vidknot.utils import cookie_health_check as chc

        cookie = tmp_path / "douyin.txt"
        cookie.write_text("sessionid=abc\n", encoding="utf-8")

        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return SimpleNamespace(returncode=0, stdout="200", stderr="")

        with patch.object(chc.subprocess, "run", side_effect=fake_run):
            chc.check_cookie_health(cookie, probe_aweme_id="123", timeout_seconds=5)

        assert os.devnull in captured["cmd"]
        assert "/dev/null" not in captured["cmd"] or os.devnull == "/dev/null"

    def test_curl_failure_is_reported_as_warning(self, tmp_path):
        from vidknot.utils import cookie_health_check as chc

        cookie = tmp_path / "douyin.txt"
        cookie.write_text("sessionid=abc\n", encoding="utf-8")

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=23, stdout="", stderr="curl: write error")

        with patch.object(chc.subprocess, "run", side_effect=fake_run):
            report = chc.check_cookie_health(cookie, probe_aweme_id="123", timeout_seconds=5)

        assert report.status.name == "WARNING"
        assert "curl probe failed" in report.detail


class TestJsRuntimePath:
    """deno 在 Windows 是 deno.exe，在 macOS / Linux 是 deno。"""

    def test_finds_deno_without_extension(self, tmp_path):
        """macOS / Linux 上 deno 没有 .exe 扩展名"""
        from vidknot.core.downloader import VideoDownloader

        dl = VideoDownloader(output_dir=str(tmp_path))
        deno = tmp_path / "deno"
        deno.write_text("#!/bin/sh\n", encoding="utf-8")

        def fake_expanduser(p):
            # deno.exe 不存在，无扩展名的 deno 存在
            if p.endswith("deno.exe"):
                return str(tmp_path / "no-such-deno.exe")
            if p.endswith("deno"):
                return str(deno)
            return p

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            with patch("shutil.which", return_value=None):
                assert dl._get_js_runtime_path() == str(deno)

    def test_finds_deno_exe_on_windows(self, tmp_path):
        """Windows 上 deno 官方安装脚本产出 deno.exe"""
        from vidknot.core.downloader import VideoDownloader

        dl = VideoDownloader(output_dir=str(tmp_path))
        deno = tmp_path / "deno.exe"
        deno.write_text("binary", encoding="utf-8")

        def fake_expanduser(p):
            if p.endswith("deno.exe"):
                return str(deno)
            return str(tmp_path / "no-such-deno")

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            with patch("shutil.which", return_value=None):
                assert dl._get_js_runtime_path() == str(deno)

    def test_falls_back_to_node(self, tmp_path):
        from vidknot.core.downloader import VideoDownloader

        dl = VideoDownloader(output_dir=str(tmp_path))
        with patch("os.path.exists", return_value=False):
            with patch("shutil.which", side_effect=lambda n: "/usr/bin/node" if n == "node" else None):
                assert dl._get_js_runtime_path() == "/usr/bin/node"

    def test_prefers_deno_over_node(self, tmp_path):
        from vidknot.core.downloader import VideoDownloader

        dl = VideoDownloader(output_dir=str(tmp_path))
        with patch("os.path.exists", return_value=False):
            with patch(
                "shutil.which",
                side_effect=lambda n: {"deno": "/opt/deno", "node": "/usr/bin/node"}.get(n),
            ):
                assert dl._get_js_runtime_path() == "/opt/deno"


def test_io_module_available():
    """io 是标准库，sanity check 防止 import 被误删"""
    assert io.TextIOWrapper is not None
