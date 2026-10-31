"""mmx CLI 解析回归测试

背景：Windows 下 npm 全局安装生成的是 `.cmd` 包装器，而 CreateProcess 只按
`.exe` 解析扩展名，直接 `subprocess.run(["mmx", ...])` 会抛 FileNotFoundError，
导致双 ASR 校正永远失败并静默降级到单源转写。
"""
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vidknot.core import corrector
from vidknot.utils.exceptions import LLMError


class TestMmxCommand:
    def test_returns_none_when_not_installed(self):
        with patch("vidknot.core.corrector.shutil.which", return_value=None):
            assert corrector._mmx_command() is None

    def test_returns_resolved_path(self):
        with patch("vidknot.core.corrector.shutil.which", return_value="/usr/bin/mmx"):
            cmd = corrector._mmx_command()
            assert cmd is not None
            assert cmd[-1] == "/usr/bin/mmx"

    def test_bat_cmd_wrapper_is_routed_through_shell(self):
        """Windows 的 .cmd 包装器必须经 cmd.exe /c 调用，否则 CreateProcess 不认"""
        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            cmd = corrector._mmx_command()
            assert cmd is not None
            assert cmd[0].lower() == "cmd.exe"
            assert cmd[1].lower() == "/c"
            assert cmd[2].lower().endswith("mmx.cmd")

    def test_no_bare_command_name_is_passed_to_subprocess(self):
        """不能把裸 "mmx" 交给 subprocess —— Windows 下必定 FileNotFoundError"""
        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            cmd = corrector._mmx_command()
            assert "mmx" not in cmd


class TestMmxGracefulDegradation:
    def test_search_returns_placeholder_when_missing(self):
        with patch("vidknot.core.corrector.shutil.which", return_value=None):
            assert corrector._mmx_search("测试") == "（mmx CLI 未安装）"

    def test_chat_raises_llm_error_when_missing(self):
        with patch("vidknot.core.corrector.shutil.which", return_value=None):
            with pytest.raises(LLMError, match="mmx CLI 未安装"):
                corrector._mmx_chat("测试")

    def test_search_does_not_raise_on_subprocess_failure(self):
        """搜索失败必须降级返回占位符，不能中断校正流程"""
        import subprocess

        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch(
                "vidknot.core.corrector.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="mmx", timeout=30),
            ):
                assert corrector._mmx_search("测试") == "（搜索超时）"


class TestMmxChatMessageDelivery:
    """多行 prompt 必须完整送达模型

    Windows 的 cmd.exe 把命令行参数里的换行当作命令分隔符，
    `--message` 只有第一行能送达，模型因此回「请提供原文」而不是执行校正。
    """

    def _fake_run(self, captured):
        def run(args, **kwargs):
            captured["args"] = list(args)
            if "--messages-file" in args:
                path = args[args.index("--messages-file") + 1]
                captured["path"] = path
                with open(path, encoding="utf-8") as fh:
                    captured["messages"] = json.load(fh)
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"content": [{"type": "text", "text": "校正完成"}]}),
                stderr="",
            )

        return run

    def test_multiline_prompt_is_passed_whole(self):
        captured = {}
        prompt = "第一行\n第二行\n第三行"
        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch(
                "vidknot.core.corrector.subprocess.run",
                side_effect=self._fake_run(captured),
            ):
                out = corrector._mmx_chat(prompt)

        assert out == "校正完成"
        assert "--messages-file" in captured["args"]
        assert captured["messages"][0]["content"] == prompt
        assert captured["messages"][0]["role"] == "user"

    def test_messages_file_is_cleaned_up(self):
        captured = {}
        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch(
                "vidknot.core.corrector.subprocess.run",
                side_effect=self._fake_run(captured),
            ):
                corrector._mmx_chat("多行\nprompt")

        assert not os.path.exists(captured["path"])

    def test_falls_back_to_message_when_messages_file_unsupported(self):
        """旧版 mmx 不认 --messages-file 时应回退到 --message"""
        calls = []

        def run(args, **kwargs):
            calls.append(list(args))
            if "--messages-file" in args:
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="unknown flag: --messages-file",
                )
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"content": [{"type": "text", "text": "回退成功"}]}),
                stderr="",
            )

        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch("vidknot.core.corrector.subprocess.run", side_effect=run):
                out = corrector._mmx_chat("多行\nprompt")

        assert out == "回退成功"
        assert len(calls) == 2
        assert "--message" in calls[1]
