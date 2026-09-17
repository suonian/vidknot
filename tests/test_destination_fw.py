"""
测试 destination=fw / fw_file(issue #8 修复)

覆盖:
- CLI choices 包含 fw 和 fw_file
- VideoKnowledgePipeline 接受 fw 和 fw_file(不构造 writer)
- _run_cli_impl 在 destination=fw 时输出 SF + FW 段
- _run_cli_impl 在 destination=fw_file 时把 FW 段写到 *.fw.txt
- _run_cli_impl 在 destination=fw_file 但无 -o 时报错退出
- 未启用校正时,默认 destination 不跑 FW(性能回归防护)
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from vidknot import __main__
from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline


class TestCliDestinationChoices:
    """测试 CLI destination choices 含 fw / fw_file"""

    def test_destination_choices_includes_fw(self):
        """CLI 应接受 fw 选项"""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--destination", "-d", default="obsidian",
            choices=["feishu", "yuque", "notion", "obsidian", "both",
                     "none", "fw", "fw_file"],
        )
        args = parser.parse_args(["-d", "fw"])
        assert args.destination == "fw"

    def test_destination_choices_includes_fw_file(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--destination", "-d", default="obsidian",
            choices=["feishu", "yuque", "notion", "obsidian", "both",
                     "none", "fw", "fw_file"],
        )
        args = parser.parse_args(["-d", "fw_file"])
        assert args.destination == "fw_file"

    def test_real_main_parser_accepts_fw(self):
        """真实 main() 的 parser 应接受 -d fw（argparse 拒绝时以 code 2 退出）"""
        with patch("sys.argv", ["vidknot", "https://example.com", "-d", "fw"]), \
             patch.object(__main__, "_run_cli_impl"):
            try:
                __main__.main()
            except SystemExit as e:
                assert e.code != 2, "argparse 拒绝了 -d fw"


class TestVideoKnowledgePipelineFwDestinations:
    """测试 pipeline 接受 fw/fw_file(issue #8)"""

    def test_fw_destination_accepted(self):
        """destination=fw 不应抛 ValueError(issue #8 修复)"""
        pipeline = VideoKnowledgePipeline(destination="fw")
        assert pipeline.destination == "fw"

    def test_fw_file_destination_accepted(self):
        """destination=fw_file 不应抛 ValueError"""
        pipeline = VideoKnowledgePipeline(destination="fw_file")
        assert pipeline.destination == "fw_file"

    def test_fw_destination_no_writer_created(self):
        """fw 模式不应构造 feishu/obsidian 等 writer(issue #8)"""
        pipeline = VideoKnowledgePipeline(destination="fw")
        assert pipeline._feishu is None
        assert pipeline._obsidian is None
        assert pipeline._yuque is None
        assert pipeline._notion is None

    def test_supported_destinations_includes_fw(self):
        """SUPPORTED_DESTINATIONS 应含 fw/fw_file"""
        assert "fw" in VideoKnowledgePipeline.SUPPORTED_DESTINATIONS
        assert "fw_file" in VideoKnowledgePipeline.SUPPORTED_DESTINATIONS


class TestRunCliImplFwDestination:
    """测试 _run_cli_impl 输出逻辑(issue #8)"""

    @pytest.fixture(autouse=True)
    def _skip_env_check(self):
        """绕过 CLI 环境依赖检查（CI runner 无 f2/ffmpeg，与本类所测输出逻辑无关）"""
        with patch("vidknot.utils.env_check.check_all_requirements", return_value=(True, [])), \
             patch("vidknot.utils.env_check.check_ffmpeg", return_value=(True, "/usr/bin/ffmpeg")):
            yield

    def _make_args(self, **overrides):
        args = MagicMock()
        args.url = "https://example.com"
        args.destination = "obsidian"
        args.output = None
        args.language = "zh"
        args.no_cache = True
        args.feishu_folder = None
        args.obsidian_tags = []
        args.temp_subdir = None
        args.no_correct = False
        args.correct = False
        args.correction_version = None
        args.raw = False
        args.summary = False
        for k, v in overrides.items():
            setattr(args, k, v)
        return args

    def test_fw_destination_appends_fw_segments(self, capsys):
        """destination=fw 时,FW 段应追加到输出"""
        mock_result = {
            "transcription": "SF 完整文本",
            "markdown": "笔记内容",
            "fw_transcription": "[  0.0s -   2.0s] FW 段1\n[  2.0s -   4.0s] FW 段2",
        }

        mock_args = self._make_args(destination="fw", raw=True)
        mock_args.summary = False  # 强制 raw

        with patch.object(__main__, "process_video", return_value=mock_result):
            try:
                __main__._run_cli_impl(mock_args)
            except SystemExit:
                pass

        captured = capsys.readouterr()
        # FW 段应出现在 stdout
        assert "FW 段1" in captured.out
        assert "FW 段2" in captured.out
        # 分隔符
        assert "FW FasterWhisper 段" in captured.out

    def test_fw_file_destination_writes_fw_file(self, tmp_path):
        """destination=fw_file 时,FW 段应写到 *.fw.txt"""
        mock_result = {
            "transcription": "SF 完整文本",
            "markdown": "笔记内容",
            "fw_transcription": "[  0.0s -   2.0s] FW 段1",
        }

        output_path = tmp_path / "out.md"
        mock_args = self._make_args(
            destination="fw_file", output=str(output_path), raw=True
        )

        with patch.object(__main__, "process_video", return_value=mock_result):
            try:
                __main__._run_cli_impl(mock_args)
            except SystemExit:
                pass

        assert output_path.exists()
        fw_path = output_path.with_suffix(".fw.txt")
        assert fw_path.exists()
        assert "FW 段1" in fw_path.read_text()

    def test_fw_file_destination_requires_o(self, caplog):
        """destination=fw_file 必须有 -o(issue #8 修复:防止静默丢数据)"""
        mock_result = {
            "transcription": "SF",
            "markdown": "笔记",
            "fw_transcription": "[FW]",
        }

        mock_args = self._make_args(
            destination="fw_file", output=None, raw=True
        )

        with patch.object(__main__, "process_video", return_value=mock_result), \
             pytest.raises(SystemExit) as exc:
            __main__._run_cli_impl(mock_args)

        assert exc.value.code == 2

    def test_obsidian_destination_no_extra_fw_run(self):
        """destination=obsidian 时,不应自动跑 FW(性能回归防护)"""
        mock_result = {
            "transcription": "SF",
            "markdown": "笔记",
            # 注意:没有 fw_transcription
        }

        mock_args = self._make_args(destination="obsidian", raw=True)

        # FasterWhisperASR 不应被实例化(会触发 .transcribe)
        with patch.object(__main__, "process_video", return_value=mock_result), \
             patch("vidknot.core.transcriber.FasterWhisperASR") as mock_fw, \
             patch("vidknot.pipeline.video_knowledge_pipeline.VideoKnowledgePipeline.save",
                   return_value="mock://saved"):
            try:
                __main__._run_cli_impl(mock_args)
            except SystemExit:
                pass

            # 校验:FasterWhisperASR 不应被调用
            mock_fw.assert_not_called()
