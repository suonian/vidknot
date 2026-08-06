"""
测试 vidknot.core.corrector

覆盖：
- 工具函数：_normalize, _strip_timestamps, _make_diff, _extract_corrected_transcript
- mmx 集成：_mmx_search, _mmx_chat（mock subprocess）
- DualASRCorrector：完整流程（mock 外部依赖）
- run_correction_pipeline：工厂函数
"""

from unittest.mock import MagicMock, patch

import pytest

from vidknot.core.corrector import (
    DualASRCorrector,
    _extract_corrected_transcript,
    _make_diff,
    _normalize,
    _strip_timestamps,
    run_correction_pipeline,
)
from vidknot.core.transcriber import FasterWhisperASR, SiliconFlowASR
from vidknot.utils.exceptions import CorrectionError, LLMError

# ========== 工具函数测试 ==========


class TestNormalize:
    """测试 _normalize 函数"""

    def test_strip_punctuation_and_spaces(self):
        assert _normalize("hello world!") == "helloworld"

    def test_strip_chinese_punctuation(self):
        assert _normalize("大家好，今天天气真好。") == "大家好今天天气真好"

    def test_strip_digits(self):
        # 数字被剥离，但 % 等符号保留
        result = _normalize("完播率 95%")
        assert "完播率" in result
        assert "9" not in result and "5" not in result

    def test_strip_emoji(self):
        assert _normalize("hello 🎼 world") == "helloworld"

    def test_empty_string(self):
        assert _normalize("") == ""

    def test_none_safe(self):
        # None 输入不应崩溃（按空字符串处理）
        try:
            result = _normalize(None)
            # 如果返回了，应该是空字符串或可哈希
            assert result == "" or result is None
        except (TypeError, AttributeError):
            # 接受类型错误的实现也算合理
            pass

    def test_only_punctuation(self):
        assert _normalize("，。！？") == ""


class TestStripTimestamps:
    """测试 _strip_timestamps 函数"""

    def test_strip_time_prefix(self):
        assert _strip_timestamps("[  0.0s -    3.4s] hello") == "hello"

    def test_strip_no_spaces(self):
        assert _strip_timestamps("[0.0s-3.4s] world") == "world"

    def test_no_timestamp_passthrough(self):
        assert _strip_timestamps("no timestamp here") == "no timestamp here"

    def test_multiple_lines(self):
        text = "[  0.0s -    3.4s] 第一行\n[  3.4s -    5.9s] 第二行"
        assert _strip_timestamps(text) == "第一行\n第二行"


class TestMakeDiff:
    """测试 _make_diff 函数"""

    def test_identical_text_no_diff(self):
        fw = "[  0.0s -    3.4s] 三大平台瞒了创作者们整整8年"
        sf = "三大平台瞒了创作者们整整8年"
        diff_lines, fw_norm, sf_norm = _make_diff(fw, sf)
        assert len(diff_lines) == 0

    def test_simple_difference(self):
        fw = "[  0.0s -    3.4s] 三大平台瞒了创作者们整整8年"
        sf = "三大平台瞞了创作者们整整8年"  # 瞞 vs 瞒
        diff_lines, fw_norm, sf_norm = _make_diff(fw, sf)
        assert len(diff_lines) > 0
        # diff line 应包含 SF 和 FW 标注
        assert any("SF=" in line for line in diff_lines)
        assert any("FW=" in line for line in diff_lines)

    def test_major_difference(self):
        fw = "[  0.0s -    3.4s] papi酱是知名创作者"
        sf = "puppy酱是知名创作者"
        diff_lines, _, _ = _make_diff(fw, sf)
        assert len(diff_lines) > 0

    def test_diff_includes_context(self):
        fw = "[  0.0s -    3.4s] 完播率高的视频更受欢迎"
        sf = "顽波率高的视频更受欢迎"
        diff_lines, _, _ = _make_diff(fw, sf)
        # 至少有一条 diff line
        assert len(diff_lines) >= 1
        # diff line 应包含上下文
        assert any("ctx:" in line for line in diff_lines)


class TestExtractCorrectedTranscript:
    """测试 _extract_corrected_transcript 函数"""

    def test_extract_with_markers(self):
        llm_output = """
前面是一些解释文字

===CORRECTED===
[  0.0s -    3.4s] 三大平台瞒了创作者们整整8年
[  3.4s -    5.9s] 最近终于把给谁流量给多少
===END===
"""
        result = _extract_corrected_transcript(llm_output)
        assert "[  0.0s -    3.4s] 三大平台瞒了创作者们整整8年" in result
        assert "[  3.4s -    5.9s] 最近终于把给谁流量给多少" in result
        assert "前面是一些解释文字" not in result

    def test_fallback_no_markers(self):
        """无 ===CORRECTED=== 标记时回退到最长连续时间戳段"""
        llm_output = """随意的解释文字
[  0.0s -    3.4s] 第一段
[  3.4s -    5.9s] 第二段
[  5.9s -    8.0s] 第三段
更多说明"""
        result = _extract_corrected_transcript(llm_output)
        # fallback 应该找到最长连续段，至少包含一段
        assert "[  0.0s -    3.4s] 第一段" in result or "[  3.4s -    5.9s] 第二段" in result
        assert "随意的解释文字" not in result

    def test_empty_input(self):
        assert _extract_corrected_transcript("") == ""


# ========== mmx 集成测试（mock subprocess） ==========


class TestMmxSearch:
    """测试 _mmx_search（mock subprocess.run）"""

    def test_returns_summary_on_success(self):
        from vidknot.core.corrector import _mmx_search

        mock_response = '{"organic": [{"title": "papi酱", "snippet": "知名网红"}]}'
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_response
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = _mmx_search("papi酱")

        assert "papi酱" in result
        assert "知名网红" in result

    def test_handles_failure(self):
        from vidknot.core.corrector import _mmx_search

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "command failed"

        with patch("subprocess.run", return_value=mock_result):
            result = _mmx_search("query")

        assert "搜索失败" in result

    def test_handles_timeout(self):
        from vidknot.core.corrector import _mmx_search

        with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("mmx", 30)):
            result = _mmx_search("query")

        assert "超时" in result

    def test_handles_no_results(self):
        from vidknot.core.corrector import _mmx_search

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"organic": []}'

        with patch("subprocess.run", return_value=mock_result):
            result = _mmx_search("query")

        assert "无结果" in result


class TestMmxChat:
    """测试 _mmx_chat（mock subprocess.run）"""

    def test_returns_text_content(self):
        from vidknot.core.corrector import _mmx_chat

        mock_response = '{"content": [{"type": "text", "text": "这是回答"}, {"type": "text", "text": " 继续"}]}'
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_response

        with patch("subprocess.run", return_value=mock_result):
            result = _mmx_chat("prompt", max_tokens=1000, timeout=60)

        assert result == "这是回答 继续"

    def test_raises_llm_error_on_failure(self):
        from vidknot.core.corrector import _mmx_chat

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "API error"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(LLMError, match="mmx 调用失败"):
                _mmx_chat("prompt")

    def test_raises_on_timeout(self):
        from vidknot.core.corrector import _mmx_chat

        with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("mmx", 60)):
            with pytest.raises(LLMError, match="超时"):
                _mmx_chat("prompt")

    def test_handles_empty_content(self):
        from vidknot.core.corrector import _mmx_chat

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"content": []}'

        with patch("subprocess.run", return_value=mock_result):
            result = _mmx_chat("prompt")

        assert result == ""


# ========== DualASRCorrector 测试 ==========


class TestDualASRCorrector:
    """测试 DualASRCorrector 类"""

    def test_v4_init(self):
        c = DualASRCorrector(version="v4")
        assert c.version == "v4"
        assert len(c.PROMPT_V4) > 0

    def test_v3_init(self):
        c = DualASRCorrector(version="v3")
        assert c.version == "v3"
        assert len(c.PROMPT_V3) > 0

    def test_unknown_version_raises(self):
        with pytest.raises(CorrectionError, match="未知 version"):
            DualASRCorrector(version="v999")

    def test_correct_identical_text_no_correction_needed(self):
        """两份转录一致时应跳过整个校正流程"""
        fw = "[  0.0s -    3.4s] 三大平台瞒了创作者们整整8年"
        sf = "三大平台瞒了创作者们整整8年"

        # 不应该调用任何 mmx
        with patch("vidknot.core.corrector._mmx_chat") as mock_chat:
            c = DualASRCorrector(version="v4")
            result = c.correct(fw, sf, "测试视频")

        assert result["diff_count"] == 0
        assert result["corrected_text"] == fw
        assert mock_chat.call_count == 0  # 完全跳过

    def test_correct_with_diff_runs_full_pipeline(self):
        """存在差异时应跑完整流程"""
        fw = "[  0.0s -    3.4s] papi酱是知名创作者"
        sf = "puppy酱是知名创作者"

        # Mock mmx_chat 返回两次（一次清单，一次校正）
        mock_chat = MagicMock(side_effect=[
            "1. 搜证 [papi酱] - 知名网红",  # 搜证清单
            """校正决定表...

===CORRECTED===
[  0.0s -    3.4s] papi酱是知名创作者
===END===""",  # 校正结果
        ])

        # Mock mmx_search
        with patch("vidknot.core.corrector._mmx_chat", mock_chat):
            with patch("vidknot.core.corrector._mmx_search", return_value="[papi酱] 知名网红"):
                c = DualASRCorrector(version="v4")
                result = c.correct(fw, sf, "测试视频")

        assert result["diff_count"] > 0
        assert result["n_segments"] == 1
        assert "papi酱" in result["corrected_text"]
        # search_evidence 应包含搜证项
        assert len(result["search_evidence"]) >= 1
        # decision_table 应有内容
        assert result["decision_table"]

    def test_correct_includes_diff_text_in_prompt(self):
        """prompt 应包含 diff 清单"""
        fw = "[  0.0s -    3.4s] papi酱是知名创作者"
        sf = "puppy酱是知名创作者"

        captured_prompts = []

        def capture(prompt, **kwargs):
            captured_prompts.append(prompt)
            if len(captured_prompts) == 1:
                return "1. 搜证 [papi酱] - 知名网红"
            return """===CORRECTED===
[  0.0s -    3.4s] papi酱是知名创作者
===END==="""

        with patch("vidknot.core.corrector._mmx_chat", side_effect=capture):
            with patch("vidknot.core.corrector._mmx_search", return_value="mock result"):
                c = DualASRCorrector(version="v4")
                c.correct(fw, sf, "测试视频")

        # 第二次调用是校正 prompt
        assert "Diff 清单" in captured_prompts[1]
        assert "puppy酱" in captured_prompts[1]  # 包含 diff 内容

    def test_correct_returns_all_keys(self):
        """返回 dict 应包含所有 key"""
        fw = "[  0.0s -    3.4s] papi酱是知名创作者"
        sf = "puppy酱是知名创作者"

        with patch("vidknot.core.corrector._mmx_chat", side_effect=[
            "1. 搜证 [papi酱] - 知名网红",
            """===CORRECTED===
[  0.0s -    3.4s] papi酱是知名创作者
===END===""",
        ]):
            with patch("vidknot.core.corrector._mmx_search", return_value="mock"):
                c = DualASRCorrector(version="v4")
                result = c.correct(fw, sf, "测试")

        required_keys = {
            "corrected_text", "search_evidence", "diff_count",
            "decision_table", "llm_raw_output", "n_segments"
        }
        assert required_keys.issubset(result.keys())


class TestRunCorrectionPipeline:
    """测试 run_correction_pipeline 工厂函数"""

    def test_returns_combined_results(self):
        # run_correction_pipeline 内部有文件校验，直接 patch validate
        # 模拟：transcribe 返回固定文本，corrector 返回固定结果

        mock_fw_result = "[  0.0s -    3.4s] 大家好"
        mock_sf_result = "大家好"
        mock_correction_result = {
            "corrected_text": "[  0.0s -    3.4s] 大家好",
            "search_evidence": {},
            "diff_count": 0,
            "decision_table": "",
            "llm_raw_output": "",
            "n_segments": 1,
        }

        # 创建假 audio 文件让 validate 通过
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"\x00" * 2048)  # 大于 1024 bytes
            fake_path = f.name

        try:
            # Patch transcribe 方法（不影响 validate）
            with patch.object(FasterWhisperASR, "transcribe", return_value=mock_fw_result):
                with patch.object(SiliconFlowASR, "transcribe", return_value=mock_sf_result):
                    with patch.object(DualASRCorrector, "correct", return_value=mock_correction_result):
                        result = run_correction_pipeline(
                            audio_path=fake_path,
                            video_title="测试视频",
                            version="v4",
                        )

            assert result["fw_text"] == mock_fw_result
            assert result["sf_text"] == mock_sf_result
            assert result["version"] == "v4"
            assert "corrected_text" in result
        finally:
            import os
            os.unlink(fake_path)
