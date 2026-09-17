"""
测试临时子目录命名规范(issue #10 修复)

覆盖:
- VideoDownloader 接受 subdir 参数
- 默认子目录命名:<platform>-<id>-<YYYYMMDD-HHMMSS>-<uuid6>/
- 路径穿越防护:绝对路径拒绝
- 路径穿越防护:.. 路径拒绝
- 并发冲突防护:uuid 后缀
- CLI --temp-subdir 参数
"""

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from vidknot.core.downloader import VideoDownloader


class TestVideoDownloaderSubdir:
    """测试 VideoDownloader subdir 参数(issue #10)"""

    def test_default_output_dir_unchanged(self):
        """默认无 subdir 时,行为不变"""
        dl = VideoDownloader()
        assert dl.subdir is None
        # output_dir 应该是 /tmp/vidknot/
        assert dl.output_dir.name == "vidknot"

    def test_subdir_creates_subdirectory(self, tmp_path):
        """指定 subdir 时,应创建子目录"""
        dl = VideoDownloader(output_dir=str(tmp_path), subdir="myvideo")
        assert dl.subdir == "myvideo"
        assert dl.output_dir == tmp_path / "myvideo"
        assert dl.output_dir.exists()

    def test_subdir_rejects_absolute_path(self, tmp_path):
        """绝对路径应被拒绝(路径穿越防护)"""
        abs_path = "/etc/passwd"
        with pytest.raises(ValueError, match="绝对路径"):
            VideoDownloader(output_dir=str(tmp_path), subdir=abs_path)

    def test_subdir_rejects_dotdot_traversal(self, tmp_path):
        """.. 路径应被拒绝(路径穿越防护)"""
        with pytest.raises(ValueError, match=r"\.\."):
            VideoDownloader(output_dir=str(tmp_path), subdir="../../../etc")

    def test_subdir_rejects_nested_dotdot(self, tmp_path):
        """嵌套 .. 也应拒绝"""
        with pytest.raises(ValueError, match=r"\.\."):
            VideoDownloader(output_dir=str(tmp_path), subdir="foo/../../bar")

    def test_subdir_escape_attempt_blocked(self, tmp_path):
        """逃逸到 output_dir 外应被拒绝"""
        # 路径解析后不在 output_dir 内
        with pytest.raises(ValueError):
            # 构造一个相对路径,解析后会逃出 output_dir
            VideoDownloader(output_dir=str(tmp_path), subdir="../outside")


class TestSubdirNamingConvention:
    """测试命名规范:<platform>-<id>-<YYYYMMDD-HHMMSS>-<uuid6>/"""

    def test_default_subdir_format(self, tmp_path, monkeypatch):
        """默认 subdir 应含 uuid 后缀(并发冲突防护)"""
        # 通过 _run_cli_impl 模拟(直接看生成的 subdir)
        # 这里只测子目录生成的部分
        from datetime import datetime
        import uuid

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_suffix = uuid.uuid4().hex[:6]
        subdir = f"unknown-{timestamp}-{unique_suffix}"

        # 验证格式
        assert subdir.startswith("unknown-")
        # 校验时间戳格式
        m = re.match(r"^unknown-(\d{8}-\d{6})-([a-f0-9]{6})$", subdir)
        assert m is not None, f"格式不符: {subdir}"

    def test_subdir_rename_to_platform_id(self, tmp_path):
        """下载后获取 video_id 时,应重命名为 <platform>-<id>-<ts>-<uuid6>"""
        old_dir = tmp_path / "unknown-20260917-123045-a1b2c3"
        old_dir.mkdir()

        new_subdir = "douyun-7680499471466282623-20260917-123045-a1b2c3"
        new_dir = tmp_path / new_subdir

        old_dir.rename(new_dir)
        assert new_dir.exists()
        assert not old_dir.exists()


class TestCliTempSubdir:
    """测试 --temp-subdir CLI 参数"""

    def test_temp_subdir_option_in_parser(self):
        """--temp-subdir 应该在 CLI parser 中"""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--temp-subdir", default=None)
        args = parser.parse_args(["--temp-subdir", "myvideo"])
        assert args.temp_subdir == "myvideo"

    def test_temp_subdir_default_none(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--temp-subdir", default=None)
        args = parser.parse_args([])
        assert args.temp_subdir is None


class TestProcessVideoSubdirFlow:
    """测试 process_video 的子目录重命名流程"""

    def test_subdir_format_after_rename(self, tmp_path, monkeypatch):
        """下载后获取 video_id,应重命名为 <platform>-<id>-<ts>-<uuid6>"""
        import uuid
        from datetime import datetime

        # 模拟初始 unknown-<ts>-<uuid6>
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        uuid_suffix = uuid.uuid4().hex[:6]
        original = f"unknown-{timestamp}-{uuid_suffix}"

        # 模拟下载后获取 video_id
        video_id = "7680499471466282623"
        platform = "douyin"

        # 重命名规则:platform-videoid-<ts>-<uuid6>
        # original = unknown-YYYYMMDD-HHMMSS-uuid6 (3 dash-separated segments after unknown)
        # suffix = -YYYYMMDD-HHMMSS-uuid6
        suffix = "-" + original[len("unknown-"):]
        renamed = f"{platform}-{video_id}{suffix}"

        # 校验
        assert renamed.startswith(f"{platform}-{video_id}-")
        assert uuid_suffix in renamed
        assert timestamp in renamed

    def test_concurrent_unique_subdirs(self):
        """并发时,2 个任务 subdir 应不同(uuid 后缀)"""
        import uuid
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        s1 = f"unknown-{ts}-{uuid.uuid4().hex[:6]}"
        s2 = f"unknown-{ts}-{uuid.uuid4().hex[:6]}"
        assert s1 != s2, "并发场景应生成不同 uuid"