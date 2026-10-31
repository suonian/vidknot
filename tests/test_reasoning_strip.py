"""推理块剥离与 NoAPIKeyError 提示语境的回归测试

背景：MiniMax-M3 等推理模型默认开启 thinking，会把推理过程直接内联在
message.content 里（而非 reasoning_content 字段），落库前必须剥离。
"""
from unittest.mock import MagicMock, patch

import pytest

from vidknot.core.processor import ContentProcessor, resolve_markdown, strip_reasoning
from vidknot.utils.exceptions import NoAPIKeyError


class TestResolveMarkdown:
    def test_keeps_non_empty_markdown(self):
        assert resolve_markdown("# 笔记", "转录文本") == "# 笔记"

    def test_falls_back_when_markdown_empty(self):
        assert resolve_markdown("", "转录文本") == "转录文本"

    def test_falls_back_when_markdown_none(self):
        assert resolve_markdown(None, "转录文本") == "转录文本"

    def test_falls_back_when_markdown_only_whitespace(self):
        assert resolve_markdown("   \n  ", "转录文本") == "转录文本"


class TestStripReasoning:
    def test_strips_leading_think_block(self):
        raw = "<think>We need answer Chinese. Let me count</think>\n\n# 标题\n\n正文"
        out = strip_reasoning(raw)
        assert "<think>" not in out
        assert "Let me count" not in out
        assert out.startswith("# 标题")
        assert "正文" in out

    def test_strips_multiple_think_blocks(self):
        raw = "<think>第一段</think>内容A<think>第二段</think>内容B"
        out = strip_reasoning(raw)
        assert "<think>" not in out
        assert "内容A" in out and "内容B" in out

    def test_multiline_think_block(self):
        """推理块可能跨多行，必须整体剥离"""
        raw = "<think>\nline1\nline2\n</think>\n最终答案"
        out = strip_reasoning(raw)
        assert "line1" not in out
        assert out == "最终答案"

    def test_plain_content_unchanged(self):
        """不返回推理块的模型（OpenAI / GLM）不受影响"""
        raw = "# 标题\n\n正文内容"
        assert strip_reasoning(raw) == raw

    def test_only_think_block_yields_empty(self):
        """模型只输出了推理时返回空串，由调用方回退到原始转录

        （响应被 max_tokens 截断时推理块没有闭合标签，此时不能把
        整段推理当成笔记落库。）
        """
        raw = "<think>只有推理没有答案</think>"
        assert strip_reasoning(raw) == ""

    def test_unclosed_think_block_is_stripped_to_end(self):
        """推理块未闭合（响应被 max_tokens 截断）时剥离到结尾"""
        raw = "<think>推理写到一半就被截断了，这里没有闭合标签"
        assert strip_reasoning(raw) == ""

    def test_unclosed_think_block_keeps_preceding_content(self):
        raw = "# 标题\n\n正文\n<think>推理被截断"
        out = strip_reasoning(raw)
        assert out == "# 标题\n\n正文"
        assert "<think>" not in out

    def test_empty_and_none(self):
        assert strip_reasoning("") == ""
        assert strip_reasoning(None) == ""


class TestCallLlmStripsReasoning:
    def _proc_with_content(self, content: str) -> ContentProcessor:
        proc = ContentProcessor(provider="openai-compatible", model="test-model", max_tokens=100)
        client = MagicMock()
        client.chat.completions.create.return_value.choices[0].message.content = content
        proc._client = client
        return proc

    def test_call_llm_removes_think_block(self):
        proc = self._proc_with_content("<think>推理中</think>\n\n# 笔记\n\n内容")
        out = proc._call_llm("prompt")
        assert "<think>" not in out
        assert out.startswith("# 笔记")

    def test_call_llm_passes_expected_request_args(self):
        proc = self._proc_with_content("答案")
        proc._call_llm("prompt")
        kwargs = proc._client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "test-model"
        assert kwargs["max_tokens"] == 100
        assert kwargs["messages"] == [{"role": "user", "content": "prompt"}]


class TestNoAPIKeyErrorHint:
    def test_default_hint_is_generic(self):
        """默认提示不应把用户引向某个特定服务的 Key"""
        hint = NoAPIKeyError("缺 Key").hint
        assert hint
        assert "SILICONFLOW_API_KEY" not in hint
        assert "docs/CONFIG.md" in hint

    def test_llm_missing_key_points_to_llm_variables(self):
        """LLM 缺 Key 时提示应指向 LLM_API_KEY，而不是 SiliconFlow"""
        import os

        from vidknot.utils.config_manager import ConfigManager

        proc = ContentProcessor(provider="openai-compatible", model="test-model", max_tokens=100)
        # 只摘掉 LLM_API_KEY，保留 USERPROFILE 等系统变量
        # （clear=True 会让 Windows 的 Path.home() 抛 RuntimeError）
        env = dict(os.environ)
        env.pop("LLM_API_KEY", None)
        with patch.object(ConfigManager, "get_provider", return_value={}):
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(NoAPIKeyError) as exc:
                    proc._get_client()
        assert "LLM_API_KEY" in str(exc.value)
        assert "SILICONFLOW_API_KEY" not in str(exc.value)
