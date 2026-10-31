"""子进程输出编码回归测试

背景：`subprocess.run(..., text=True)` 在 Windows 上按**本地代码页**（简体中文
为 cp936/GBK）解码子进程的 stdout，而 `mmx`（Node CLI）、yt-dlp 等工具写出的
是 UTF-8。字节流一旦无法按 GBK 解码：

1. 轻则中文变成乱码（UTF-8 被当成 GBK 解读）；
2. 重则抛 `UnicodeDecodeError`，且解码发生在 `subprocess` 的读取线程里 ——
   该线程崩溃后 `CompletedProcess.stdout` 变成 `None`，最终以
   `json.loads(None)` 这种完全误导性的 TypeError 暴露。

mmx 双 ASR 校正正是这样在 Windows 上静默失效的：主流程不中断，只是校正
被悄悄跳过、退回单源转录。macOS 的 locale 通常就是 UTF-8，所以该问题
只在 Windows 上显形。

因此：凡是以文本模式捕获子进程输出，一律显式指定 `encoding="utf-8"`
与 `errors="replace"`（`errors` 保证永远不会因解码失败而丢结果）。
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vidknot.core import corrector
from vidknot.utils.exceptions import LLMError

SRC_ROOT = Path(corrector.__file__).resolve().parent.parent

_SUBPROCESS_CALLS = {"run", "Popen", "check_output", "check_call"}


def _iter_subprocess_calls(tree: ast.AST):
    """遍历所有 subprocess.* 调用节点"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in _SUBPROCESS_CALLS:
            continue
        value = func.value
        if isinstance(value, ast.Name) and value.id == "subprocess":
            yield node


def _kwarg(node: ast.Call, name: str):
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_true(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


class TestNoLocaleDependentSubprocessDecoding:
    """全库守卫：文本模式捕获子进程输出必须显式指定编码"""

    def test_every_text_mode_subprocess_call_declares_encoding(self):
        offenders = []
        for path in sorted(SRC_ROOT.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for call in _iter_subprocess_calls(tree):
                text_mode = _is_true(_kwarg(call, "text")) or _is_true(
                    _kwarg(call, "universal_newlines")
                )
                if not text_mode:
                    continue
                if _kwarg(call, "encoding") is None:
                    offenders.append(
                        f"{path.relative_to(SRC_ROOT)}:{call.lineno}"
                    )
        assert not offenders, (
            "以下子进程调用以文本模式捕获输出但未指定 encoding，"
            "在非 UTF-8 locale（如中文 Windows）下会解码失败或产生乱码：\n"
            + "\n".join(offenders)
        )

    def test_encoding_is_utf8_with_replace_errors(self):
        """必须是 utf-8 + errors=replace：replace 保证永不抛解码异常"""
        offenders = []
        for path in sorted(SRC_ROOT.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for call in _iter_subprocess_calls(tree):
                if not _is_true(_kwarg(call, "text")):
                    continue
                enc = _kwarg(call, "encoding")
                err = _kwarg(call, "errors")
                enc_ok = isinstance(enc, ast.Constant) and enc.value == "utf-8"
                err_ok = isinstance(err, ast.Constant) and err.value == "replace"
                if not (enc_ok and err_ok):
                    offenders.append(
                        f"{path.relative_to(SRC_ROOT)}:{call.lineno}"
                    )
        assert not offenders, (
            "子进程文本解码必须使用 encoding='utf-8' + errors='replace'：\n"
            + "\n".join(offenders)
        )


class TestMmxChatEncoding:
    def _capturing_run(self, captured):
        def run(args, **kwargs):
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                returncode=0,
                stdout='{"content": [{"type": "text", "text": "收到"}]}',
                stderr="",
            )

        return run

    def test_chat_forces_utf8_decoding(self):
        captured = {}
        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch(
                "vidknot.core.corrector.subprocess.run",
                side_effect=self._capturing_run(captured),
            ):
                corrector._mmx_chat("测试")

        assert captured["kwargs"]["encoding"] == "utf-8"
        assert captured["kwargs"]["errors"] == "replace"

    def test_fallback_call_also_forces_utf8_decoding(self):
        """回退到 --message 的那条分支同样要显式编码"""
        captured = []

        def run(args, **kwargs):
            captured.append(kwargs)
            if "--messages-file" in args:
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="unknown flag: --messages-file",
                )
            return SimpleNamespace(
                returncode=0,
                stdout='{"content": [{"type": "text", "text": "回退成功"}]}',
                stderr="",
            )

        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch("vidknot.core.corrector.subprocess.run", side_effect=run):
                corrector._mmx_chat("多行\nprompt")

        assert len(captured) == 2
        for kwargs in captured:
            assert kwargs["encoding"] == "utf-8"
            assert kwargs["errors"] == "replace"

    def test_search_forces_utf8_decoding(self):
        captured = {}

        def run(args, **kwargs):
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                returncode=0,
                stdout='{"organic": [{"title": "标题", "snippet": "摘要"}]}',
                stderr="",
            )

        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch("vidknot.core.corrector.subprocess.run", side_effect=run):
                result = corrector._mmx_search("关键词")

        assert captured["kwargs"]["encoding"] == "utf-8"
        assert captured["kwargs"]["errors"] == "replace"
        assert "标题" in result

    def test_chinese_search_output_is_not_mojibake(self):
        """UTF-8 字节被按 GBK 解码会产生乱码；显式 UTF-8 后中文必须原样返回"""
        captured = {}

        def run(args, **kwargs):
            captured["kwargs"] = kwargs
            return SimpleNamespace(
                returncode=0,
                stdout='{"organic": [{"title": "标题", "snippet": "摘要"}]}',
                stderr="",
            )

        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch("vidknot.core.corrector.subprocess.run", side_effect=run):
                result = corrector._mmx_search("关键词")

        assert result == "[标题] 摘要"


class TestMmxChatEmptyOutput:
    """解码线程崩溃时 stdout 为 None，必须给出可诊断的错误而不是误导性 TypeError"""

    def test_none_stdout_raises_diagnosable_llm_error(self):
        def run(args, **kwargs):
            return SimpleNamespace(returncode=0, stdout=None, stderr="")

        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch("vidknot.core.corrector.subprocess.run", side_effect=run):
                with pytest.raises(LLMError) as exc:
                    corrector._mmx_chat("测试")

        assert "无输出" in str(exc.value)
        assert "JSON object" not in str(exc.value)

    def test_empty_stdout_raises_diagnosable_llm_error(self):
        def run(args, **kwargs):
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch("vidknot.core.corrector.subprocess.run", side_effect=run):
                with pytest.raises(LLMError) as exc:
                    corrector._mmx_chat("测试")

        assert "无输出" in str(exc.value)

    def test_search_with_empty_stdout_degrades_gracefully(self):
        def run(args, **kwargs):
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch(
            "vidknot.core.corrector.shutil.which",
            return_value=r"C:\Users\me\AppData\Roaming\npm\mmx.CMD",
        ):
            with patch("vidknot.core.corrector.subprocess.run", side_effect=run):
                assert corrector._mmx_search("关键词") == "（搜索无输出）"
