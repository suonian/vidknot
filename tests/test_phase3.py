"""
阶段 3 测试: Agent 化 MCP + 批量处理 + 结构化 JSON

覆盖:
- MCP 多工具 schema (list_tools_schema) 与平台状态 (get_platform_status)
- Fallback MCPServer 的工具分发
- agent_bridge 多工具路由与 asyncio bug 修复（同步调用）
- ContentProcessor.extract_structured / _parse_json
- pipeline.run_batch 并发批量处理
- _build_structured 结构化 JSON 兜底与校正置信度
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# MCP 工具 Schema 与平台状态
# ============================================================

class TestListToolsSchema:
    def test_contains_four_tools(self):
        from vidknot.adapters.mcp_server import list_tools_schema

        tools = list_tools_schema()
        names = {t["name"] for t in tools}
        assert names == {"video_to_notes", "batch_process", "platform_status", "search_video"}

    def test_each_tool_has_input_schema(self):
        from vidknot.adapters.mcp_server import list_tools_schema

        for tool in list_tools_schema():
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_video_to_notes_requires_url(self):
        from vidknot.adapters.mcp_server import list_tools_schema

        tool = next(t for t in list_tools_schema() if t["name"] == "video_to_notes")
        assert "url" in tool["inputSchema"]["required"]

    def test_batch_process_requires_urls(self):
        from vidknot.adapters.mcp_server import list_tools_schema

        tool = next(t for t in list_tools_schema() if t["name"] == "batch_process")
        assert "urls" in tool["inputSchema"]["required"]


class TestGetPlatformStatus:
    def test_basic_structure(self):
        from vidknot.adapters.mcp_server import get_platform_status

        payload = get_platform_status()
        assert "transcription_strategy" in payload
        assert payload["platform_count"] == len(payload["platforms"])
        assert payload["platform_count"] >= 10

    def test_platform_entry_fields(self):
        from vidknot.adapters.mcp_server import get_platform_status

        payload = get_platform_status()
        for p in payload["platforms"]:
            assert {"name", "domains", "subtitle_support",
                    "cookie_configured", "browser_cookie"} <= set(p)

    def test_youtube_and_bilibili_subtitle_support(self):
        from vidknot.adapters.mcp_server import get_platform_status

        payload = get_platform_status()
        by_name = {p["name"]: p for p in payload["platforms"]}
        assert by_name["youtube"]["subtitle_support"] is True
        assert by_name["bilibili"]["subtitle_support"] is True
        assert by_name["generic"]["subtitle_support"] is False


# ============================================================
# Fallback MCPServer 工具分发
# ============================================================

class TestMCPServerFallback:
    def _call(self, method, params=None):
        from vidknot.adapters.mcp_server import MCPServer

        server = MCPServer()
        return server._handle_request({"method": method, "params": params or {}, "id": 1})

    def test_tools_list_returns_all_tools(self):
        resp = self._call("tools/list")
        names = {t["name"] for t in resp["result"]["tools"]}
        assert {"video_to_notes", "batch_process", "platform_status", "search_video"} <= names

    def test_platform_status_tool(self):
        resp = self._call("tools/call", {"name": "platform_status"})
        text = resp["result"]["content"][0]["text"]
        payload = json.loads(text)
        assert payload["platform_count"] >= 10

    def test_search_video_reserved(self):
        resp = self._call("tools/call", {"name": "search_video", "arguments": {"query": "test"}})
        text = resp["result"]["content"][0]["text"]
        assert "尚未实现" in text

    def test_batch_process_missing_urls(self):
        resp = self._call("tools/call", {"name": "batch_process", "arguments": {}})
        assert resp["error"]["code"] == -32602

    def test_unknown_tool(self):
        resp = self._call("tools/call", {"name": "no_such_tool"})
        assert resp["error"]["code"] == -32602

    def test_video_to_notes_alias_dispatch(self):
        fake_pipeline = MagicMock()
        fake_pipeline.run.return_value = {"title": "t", "markdown": "# md"}

        with patch(
            "vidknot.pipeline.video_knowledge_pipeline.VideoKnowledgePipeline",
            return_value=fake_pipeline,
        ):
            resp = self._call(
                "tools/call",
                {"name": "video_to_notes", "arguments": {"url": "https://example.com/v", "destination": "none"}},
            )
        assert "result" in resp
        fake_pipeline.run.assert_called_once()

    def test_batch_process_dispatch(self):
        fake_pipeline = MagicMock()
        fake_pipeline.run_batch.return_value = [
            {"url": "https://a.com", "success": True, "title": "A"},
            {"url": "https://b.com", "success": False, "error": "fail"},
        ]

        with patch(
            "vidknot.pipeline.video_knowledge_pipeline.VideoKnowledgePipeline",
            return_value=fake_pipeline,
        ):
            resp = self._call(
                "tools/call",
                {"name": "batch_process",
                 "arguments": {"urls": ["https://a.com", "https://b.com"]}},
            )
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["total"] == 2
        assert payload["success"] == 1


# ============================================================
# agent_bridge 多工具路由
# ============================================================

class TestAgentBridge:
    def test_get_all_tools_metadata(self):
        from vidknot.adapters.agent_bridge import get_all_tools_metadata

        tools = get_all_tools_metadata()
        names = {t["function"]["name"] for t in tools}
        assert names == {"video_knowledge", "batch_process", "platform_status", "search_video"}
        for t in tools:
            assert t["type"] == "function"

    def test_execute_tool_routes_platform_status(self):
        from vidknot.adapters.agent_bridge import execute_tool

        result = execute_tool({}, tool="platform_status")
        assert result["success"] is True
        assert result["platform_count"] >= 10

    def test_execute_tool_routes_search_video_reserved(self):
        from vidknot.adapters.agent_bridge import execute_tool

        result = execute_tool({"query": "python"}, tool="search_video")
        assert result["implemented"] is False

    def test_execute_tool_search_video_requires_query(self):
        from vidknot.adapters.agent_bridge import execute_tool

        result = execute_tool({}, tool="search_video")
        assert result["success"] is False

    def test_execute_tool_batch_requires_urls(self):
        from vidknot.adapters.agent_bridge import execute_tool

        result = execute_tool({}, tool="batch_process")
        assert result["success"] is False

    def test_execute_tool_batch_dispatch(self):
        from vidknot.adapters import agent_bridge

        fake_pipeline = MagicMock()
        fake_pipeline.run_batch.return_value = [
            {"url": "https://a.com", "success": True, "title": "A"},
        ]
        with patch(
            "vidknot.pipeline.video_knowledge_pipeline.VideoKnowledgePipeline",
            return_value=fake_pipeline,
        ):
            result = agent_bridge.execute_tool(
                {"urls": ["https://a.com"]}, tool="batch_process"
            )
        assert result["success"] is True
        assert result["total"] == 1
        assert result["success_count"] == 1

    def test_execute_video_knowledge_sync_no_asyncio(self):
        """video_knowledge 路由应同步调用 pipeline.run（不使用 asyncio.run）"""
        from vidknot.adapters import agent_bridge

        fake_pipeline = MagicMock()
        fake_pipeline.run.return_value = {"title": "t", "markdown": "# md"}
        fake_pipeline.save.return_value = "Obsidian: /tmp/note.md"

        with patch(
            "vidknot.pipeline.video_knowledge_pipeline.VideoKnowledgePipeline",
            return_value=fake_pipeline,
        ):
            result = agent_bridge.execute_tool(
                {"url": "https://example.com/v", "destination": "obsidian"},
                tool="video_to_notes",
            )
        assert result["saved_to"] == "Obsidian: /tmp/note.md"
        assert "notify_message" in result

    def test_execute_tool_missing_url(self):
        from vidknot.adapters.agent_bridge import execute_tool

        result = execute_tool({}, tool="video_knowledge")
        assert result["success"] is False
        assert result["error"] == "URL is required"


# ============================================================
# 结构化 JSON
# ============================================================

class TestStructuredJson:
    def test_structured_prompt_format_no_keyerror(self):
        """STRUCTURED_PROMPT 的 JSON 示例花括号已转义，format 不应抛 KeyError"""
        from vidknot.core.processor import ContentProcessor

        prompt = ContentProcessor.STRUCTURED_PROMPT.format(
            title="标题", uploader="作者", transcription="内容"
        )
        assert '"topics"' in prompt
        assert "标题" in prompt

    def test_parse_json_plain(self):
        from vidknot.core.processor import ContentProcessor

        data = ContentProcessor._parse_json('{"topics": ["a"]}')
        assert data == {"topics": ["a"]}

    def test_parse_json_fenced(self):
        from vidknot.core.processor import ContentProcessor

        raw = '```json\n{"topics": ["a"]}\n```'
        assert ContentProcessor._parse_json(raw) == {"topics": ["a"]}

    def test_parse_json_embedded(self):
        from vidknot.core.processor import ContentProcessor

        raw = '说明文字 {"topics": ["a"]} 结尾'
        assert ContentProcessor._parse_json(raw) == {"topics": ["a"]}

    def test_parse_json_invalid(self):
        from vidknot.core.processor import ContentProcessor

        assert ContentProcessor._parse_json("完全不是 JSON") == {}

    def test_extract_structured_normalized_keys(self):
        from vidknot.core.processor import ContentProcessor

        processor = ContentProcessor.__new__(ContentProcessor)
        with patch.object(
            processor, "_call_llm",
            return_value='{"topics": ["t1"], "summary_one_line": "总结"}',
        ):
            result = processor.extract_structured("转录内容", {"title": "T", "uploader": "U"})
        assert result["topics"] == ["t1"]
        assert result["summary_one_line"] == "总结"
        # 缺失字段应有默认值
        assert result["entities"] == []
        assert result["key_points"] == []
        assert result["tags"] == []


class TestBuildStructured:
    def test_fallback_minimal_structure_on_llm_error(self):
        from vidknot.__main__ import _build_structured

        with patch(
            "vidknot.core.processor.ContentProcessor.extract_structured",
            side_effect=RuntimeError("LLM down"),
        ):
            structured = _build_structured("转录", {"title": "T"})
        assert structured == {
            "topics": [], "entities": [], "key_points": [],
            "summary_one_line": "", "tags": [], "segments": [],
        }

    def test_segments_propagated_from_metadata(self):
        """平台提供的带时间戳字幕分段应进入 structured.segments"""
        from vidknot.__main__ import _build_structured

        segs = [{"start": 0.0, "end": 5.2, "text": "hello"}]
        with patch(
            "vidknot.core.processor.ContentProcessor.extract_structured",
            return_value={"topics": ["a"], "entities": [], "key_points": [],
                          "summary_one_line": "", "tags": []},
        ):
            structured = _build_structured(
                "转录", {"title": "T", "subtitle_segments": segs}
            )
        assert structured["segments"] == segs

    def test_correction_confidence(self):
        from vidknot.__main__ import _build_structured

        with patch(
            "vidknot.core.processor.ContentProcessor.extract_structured",
            return_value={"topics": ["a"], "entities": [], "key_points": [],
                          "summary_one_line": "", "tags": []},
        ):
            structured = _build_structured(
                "转录", {"title": "T"},
                correction_meta={"diff_count": 5, "n_segments": 10},
            )
        # 1.0 - 5/10/5 = 0.9
        assert structured["correction_confidence"] == 0.9


# ============================================================
# 批量处理 pipeline.run_batch
# ============================================================

class TestRunBatch:
    def _make_pipeline(self):
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline.__new__(VideoKnowledgePipeline)
        pipeline.destination = "none"
        pipeline.format = "structured"
        pipeline.language = "auto"
        pipeline.use_cache = False
        pipeline.cache = None
        return pipeline

    def test_run_batch_success_and_failure(self):
        pipeline = self._make_pipeline()

        def fake_run(url):
            if "bad" in url:
                raise ValueError("boom")
            return {"title": f"title-{url}", "markdown": "# ok"}

        with patch.object(pipeline, "run", side_effect=fake_run):
            results = pipeline.run_batch(
                ["https://ok.com/1", "https://bad.com/2"], max_workers=2
            )
        assert len(results) == 2
        by_url = {r["url"]: r for r in results}
        assert by_url["https://ok.com/1"]["success"] is True
        assert by_url["https://bad.com/2"]["success"] is False
        assert by_url["https://bad.com/2"]["error"] == "boom"

    def test_run_batch_with_save(self):
        pipeline = self._make_pipeline()
        pipeline.destination = "obsidian"
        pipeline.save = MagicMock(return_value="Obsidian: /tmp/x.md")

        with patch.object(pipeline, "run", return_value={"title": "t"}):
            results = pipeline.run_batch(
                ["https://a.com"], max_workers=1, save_options={"tags": []}
            )
        assert results[0]["saved_to"] == "Obsidian: /tmp/x.md"
        pipeline.save.assert_called_once()

    def test_run_batch_empty(self):
        pipeline = self._make_pipeline()
        assert pipeline.run_batch([]) == []

    def test_pipeline_run_includes_structured(self):
        """pipeline.run() 在 structured 格式下应输出 result['structured']"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline.__new__(VideoKnowledgePipeline)
        pipeline.destination = "none"
        pipeline.format = "structured"
        pipeline.language = "auto"
        pipeline.use_cache = False
        pipeline.cache = None
        pipeline.downloader = MagicMock()
        pipeline.downloader.download_audio_with_metadata.return_value = (
            None,
            {"title": "t", "uploader": "u", "platform": "youtube",
             "subtitle_text": "字幕文本",
             "subtitle_segments": [{"start": 0.0, "end": 1.0, "text": "字幕文本"}]},
        )
        pipeline.processor = MagicMock()
        pipeline.processor.summarize.return_value = {"markdown": "# md"}
        pipeline.processor.extract_structured.return_value = {
            "topics": ["a"], "entities": [], "key_points": [],
            "summary_one_line": "s", "tags": [],
        }

        result = pipeline.run("https://youtube.com/watch?v=x")
        assert result["transcription"] == "字幕文本"
        assert result["structured"]["topics"] == ["a"]
        assert result["structured"]["segments"][0]["text"] == "字幕文本"

    def test_pipeline_run_structured_fallback_on_llm_error(self):
        """extract_structured 失败时 pipeline.run 回退最小结构"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline.__new__(VideoKnowledgePipeline)
        pipeline.destination = "none"
        pipeline.format = "structured"
        pipeline.language = "auto"
        pipeline.use_cache = False
        pipeline.cache = None
        pipeline.downloader = MagicMock()
        pipeline.downloader.download_audio_with_metadata.return_value = (
            None,
            {"title": "t", "subtitle_text": "字幕"},
        )
        pipeline.processor = MagicMock()
        pipeline.processor.summarize.return_value = {"markdown": "# md"}
        pipeline.processor.extract_structured.side_effect = RuntimeError("LLM down")

        result = pipeline.run("https://youtube.com/watch?v=x")
        assert result["structured"]["topics"] == []
        assert result["structured"]["segments"] == []


# ============================================================
# CLI 批量辅助
# ============================================================

class TestBatchCLIHelpers:
    def test_version_flag(self):
        """--version 标志应输出版本号并退出"""
        import subprocess
        import sys

        proc = subprocess.run(
            [sys.executable, "-m", "vidknot", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "vidknot" in proc.stdout

    def test_local_media_extensions(self):
        from vidknot.__main__ import LOCAL_MEDIA_EXTENSIONS

        assert ".mp4" in LOCAL_MEDIA_EXTENSIONS
        assert ".mp3" in LOCAL_MEDIA_EXTENSIONS
        assert ".m4a" in LOCAL_MEDIA_EXTENSIONS
        assert ".txt" not in LOCAL_MEDIA_EXTENSIONS

    def test_process_local_video_raw_mode(self):
        """raw 模式下 process_local_video 直接转录，不调用 LLM"""
        from vidknot.__main__ import process_local_video

        fake_file = Path("/tmp/fake_video.mp4")
        with patch(
            "vidknot.core.transcriber.SiliconFlowASR.transcribe",
            return_value="转录文本",
        ):
            result = process_local_video(fake_file, "raw", "auto")
        assert result["transcription"] == "转录文本"
        assert result["title"] == "fake_video"
        assert result["metadata"]["platform"] == "local"

    def test_process_local_video_fallback_provider(self):
        """SiliconFlow 失败时回退到 fallback provider"""
        from vidknot.__main__ import process_local_video

        fake_transcriber = MagicMock()
        fake_transcriber.transcribe.return_value="兜底转录"

        with patch(
            "vidknot.core.transcriber.SiliconFlowASR.transcribe",
            side_effect=RuntimeError("no key"),
        ), patch(
            "vidknot.core.transcriber.get_transcriber",
            return_value=fake_transcriber,
        ) as mock_get:
            result = process_local_video(Path("/tmp/x.mp3"), "raw", "auto")
        assert result["transcription"] == "兜底转录"
        mock_get.assert_called_once()
