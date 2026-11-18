"""
v0.6.13 / v0.6.14 回归测试：两段式 Agent 契约 + 保存链路修复 + 模型解析修正

覆盖：
- agent_material：待搜证词提取（纯算法）+ 素材包组装
- pipeline.collect_material / save_markdown
- 保存链路修复：写入器惰性构造、凭证缺失明确报错、飞书 create_document 同步化
- MCP 新工具 video_material / save_note（自研 JSON-RPC 入口）
- CLI 新参数 --material / --save-note
- 校正 / 搜证后端可插拔（不绑定厂商）
- ASR 语音模型解析（v0.6.14：语音/文本模型分离）
- 对照转写状态 diff_status（v0.6.14：区分未执行/失败/完成）
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# agent_material：待搜证词提取（纯算法，不调 LLM）
# ============================================================


class TestExtractSearchCandidates:
    def test_latin_proper_noun_priority(self):
        """含大写字母的专有名词应成为候选"""
        from vidknot.core.agent_material import extract_search_candidates

        candidates = extract_search_candidates(
            "他在 ByteDance 工作了三年",
            "他在 Byte Danc 工作了三年",
            limit=12,
        )
        assert "ByteDance" in candidates

    def test_chinese_window_around_difference(self):
        """中文差异应取差异位置附近的 2-4 字词块"""
        from vidknot.core.agent_material import extract_search_candidates

        candidates = extract_search_candidates(
            "人工智能很重要",
            "人工作智能很重要",
            limit=12,
        )
        assert any("人工智能" in c or "人工作智" in c for c in candidates)

    def test_lowercase_noise_filtered(self):
        """普通英文虚词/碎串不应成为候选"""
        from vidknot.core.agent_material import extract_search_candidates

        candidates = extract_search_candidates(
            "all right so here we are in front of the elephants",
            "all right so here we are infront of the elephants",
            limit=12,
        )
        assert candidates == []

    def test_digits_and_models_kept(self):
        """型号/年份这类含数字的词应保留"""
        from vidknot.core.agent_material import extract_search_candidates

        candidates = extract_search_candidates(
            "我们用 GPT-4 和 Claude 3 做了对比，发布于 2024 年",
            "我们用 GPT 4 和 Claude 3 做了对比，发布于 2024 年",
            limit=12,
        )
        assert "GPT-4" in candidates

    def test_dedup_and_limit(self):
        """重复候选去重，且不超过 limit"""
        from vidknot.core.agent_material import extract_search_candidates

        candidates = extract_search_candidates(
            "ChatGPT 很强，ChatGPT 真的强",
            "ChatGpt 很强，ChatGpt 真的强",
            limit=5,
        )
        assert len(candidates) <= 5
        assert len({c.lower() for c in candidates}) == len(candidates)

    def test_no_fw_text_falls_back_to_proper_nouns(self):
        """没有对照转写时，退化为「全文里的专有名词」"""
        from vidknot.core.agent_material import extract_search_candidates

        candidates = extract_search_candidates(
            "我们在 ByteDance 讨论了 Kubernetes",
            "",
            limit=12,
        )
        assert "ByteDance" in candidates
        assert "Kubernetes" in candidates
        assert "讨论了" not in candidates

    def test_empty_input(self):
        from vidknot.core.agent_material import extract_search_candidates

        assert extract_search_candidates("", "", limit=12) == []


class TestBuildMaterialBundle:
    def test_schema_and_fields(self):
        from vidknot.core.agent_material import SCHEMA, build_material_bundle

        bundle = build_material_bundle(
            url="https://example.com/v/1",
            metadata={
                "title": "示例标题",
                "uploader": "示例作者",
                "duration": "60",
                "platform": "bilibili",
            },
            transcription="他在 ByteDance 工作了三年",
            fw_segments="[  0.2s -    7.2s] 他在 Byte Danc 工作了三年",
            diff_lines=["[0] replace: SF='ByteDance' ↔ FW='Byte Danc' | ctx: ..."],
        )
        assert bundle["schema"] == SCHEMA
        assert bundle["title"] == "示例标题"
        assert bundle["author"] == "示例作者"
        assert bundle["duration"] == 60
        assert bundle["source_platform"] == "bilibili"
        assert bundle["transcription"] == "他在 ByteDance 工作了三年"
        assert bundle["diff_count"] == 1
        assert "ByteDance" in bundle["search_candidates"]
        # 时间戳不应泄漏进候选词
        assert not any(c.startswith("00.") for c in bundle["search_candidates"])
        # 素材包不得包含任何 LLM 产物
        assert "markdown" not in bundle
        assert "structured" not in bundle

    def test_duration_invalid_becomes_zero(self):
        from vidknot.core.agent_material import build_material_bundle

        bundle = build_material_bundle(
            url="u",
            metadata={"duration": "abc"},
            transcription="t",
        )
        assert bundle["duration"] == 0


# ============================================================
# pipeline：collect_material / save_markdown
# ============================================================


class TestCollectMaterial:
    def test_no_llm_no_search(self, tmp_path):
        """第一段不得调用 LLM 或联网搜索"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(destination="none", format="raw", use_cache=False)
        pipeline.downloader = MagicMock()
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            return_value=(None, {"title": "T", "uploader": "U", "duration": 10,
                                 "platform": "bilibili", "subtitle_text": "字幕全文"})
        )
        pipeline.transcriber = MagicMock()
        pipeline.transcriber.transcribe = MagicMock(return_value="不应被调用")

        with patch("vidknot.core.processor.ContentProcessor.summarize") as summarize, \
             patch("vidknot.core.processor.ContentProcessor.chat") as chat, \
             patch("vidknot.core.corrector._search_web") as search, \
             patch("vidknot.core.corrector._correction_chat") as correction:
            bundle = pipeline.collect_material("https://example.com/v/1", with_diff=False)

        assert bundle["schema"] == "vidknot.material/1"
        assert bundle["transcription"] == "字幕全文"
        summarize.assert_not_called()
        chat.assert_not_called()
        search.assert_not_called()
        correction.assert_not_called()

    def test_max_candidates_forwarded(self):
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(destination="none", format="raw", use_cache=False)
        pipeline.downloader = MagicMock()
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            return_value=(None, {"title": "T", "subtitle_text": "字幕"})
        )
        with patch("vidknot.core.agent_material.build_material_bundle") as build:
            pipeline.collect_material("u", with_diff=False, max_candidates=3)
        assert build.call_args.kwargs["max_candidates"] == 3

    def test_subtitle_path_downloads_audio_for_diff(self):
        """字幕路径拿不到音频时，应补一次音频下载以产出 FW 对照与待搜证词"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(destination="none", format="raw", use_cache=False)
        pipeline.downloader = MagicMock()
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            side_effect=[
                # 第一次：字幕优先，拿到字幕但没有音频
                (None, {"title": "T", "subtitle_text": "字幕全文", "duration": 30}),
                # 第二次：补下载音频
                ("/tmp/a.mp3", {"title": "T", "duration": 30}),
            ]
        )

        with patch(
            "vidknot.core.transcriber.FasterWhisperASR.transcribe",
            return_value="[  0.0s -    3.4s] pupi酱是知名创作者",
        ), patch(
            "vidknot.core.corrector._make_diff",
            return_value=(["[0] replace: SF='papi酱' ↔ FW='pupi酱' | ctx: ..."], "", ""),
        ) as make_diff:
            bundle = pipeline.collect_material("https://example.com/v/1", with_diff=True)

        # 确实补下载了音频
        assert pipeline.downloader.download_audio_with_metadata.call_count == 2
        assert pipeline.downloader.download_audio_with_metadata.call_args_list[1].kwargs[
            "force_audio"
        ] is True
        # 转写仍用字幕（质量更高），diff 来自 FW 对照
        assert bundle["transcription"] == "字幕全文"
        assert bundle["diff_count"] == 1
        make_diff.assert_called_once()

    def test_subtitle_path_no_extra_download_when_diff_disabled(self):
        """--no-diff 时不应为了 FW 对照多下载一次音频"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(destination="none", format="raw", use_cache=False)
        pipeline.downloader = MagicMock()
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            return_value=(None, {"title": "T", "subtitle_text": "字幕全文"})
        )
        pipeline.collect_material("https://example.com/v/1", with_diff=False)
        assert pipeline.downloader.download_audio_with_metadata.call_count == 1


class TestSaveMarkdown:
    def test_saves_to_obsidian(self, tmp_path):
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(
            destination="obsidian",
            use_cache=False,
            obsidian_config={"vault_path": str(tmp_path)},
        )
        saved = pipeline.save_markdown(
            "https://example.com/v/1",
            "# 智能体成稿\n\n内容",
            metadata={"title": "成稿标题", "author": "A", "duration": 5},
        )
        assert "Obsidian:" in saved
        files = [p for p in tmp_path.rglob("*.md")]
        assert any("成稿标题" in p.name for p in files)

    def test_tags_applied(self, tmp_path):
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(
            destination="obsidian",
            use_cache=False,
            obsidian_config={"vault_path": str(tmp_path)},
        )
        pipeline.save_markdown(
            "https://example.com/v/1",
            "# 正文",
            metadata={"title": "带标签"},
            options={"tags": ["自定义标签"]},
        )
        contents = [
            p.read_text(encoding="utf-8")
            for p in tmp_path.rglob("*.md")
            if "带标签" in p.name
        ]
        assert contents and "自定义标签" in contents[0]


# ============================================================
# 保存链路修复（v0.6.13）
# ============================================================


class TestSaveChainFix:
    def test_obsidian_saves_without_explicit_config(self, tmp_path, monkeypatch):
        """不传 config 时也必须真的落盘（此前静默返回 ''）"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        pipeline = VideoKnowledgePipeline(destination="obsidian", use_cache=False)
        saved = pipeline.save({"title": "无config也要落盘", "markdown": "# 正文"})
        assert saved
        assert "Obsidian:" in saved
        assert list(tmp_path.rglob("*.md"))

    def test_notion_missing_credential_raises(self, monkeypatch):
        """缺凭证必须明确报错，而不是静默返回 ''"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline
        from vidknot.utils.exceptions import StorageError

        monkeypatch.delenv("NOTION_TOKEN", raising=False)
        pipeline = VideoKnowledgePipeline(destination="notion", use_cache=False)
        with pytest.raises(StorageError) as exc:
            pipeline.save({"title": "t", "markdown": "# m"})
        assert "Notion" in str(exc.value)

    def test_yuque_missing_credential_raises(self, monkeypatch):
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline
        from vidknot.utils.exceptions import StorageError

        monkeypatch.delenv("YUQUE_TOKEN", raising=False)
        pipeline = VideoKnowledgePipeline(destination="yuque", use_cache=False)
        with pytest.raises(StorageError):
            pipeline.save({"title": "t", "markdown": "# m"})

    def test_none_destination_still_returns_empty(self):
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(destination="none", use_cache=False)
        assert pipeline.save({"title": "t", "markdown": "# m"}) == ""

    def test_both_aggregates_errors_and_keeps_success(self, tmp_path, monkeypatch):
        """both 模式：部分失败时汇总报错，但保留已成功的保存结果"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline
        from vidknot.utils.exceptions import StorageError

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        monkeypatch.delenv("NOTION_TOKEN", raising=False)
        pipeline = VideoKnowledgePipeline(destination="both", use_cache=False)
        with pytest.raises(StorageError) as exc:
            pipeline.save({"title": "t", "markdown": "# m"})
        # 已成功的保存结果写进 details，不丢失
        assert "已成功保存" in (exc.value.details or "")
        assert list(tmp_path.rglob("*.md"))

    def test_feishu_create_document_is_sync(self):
        """create_document 曾被误声明为 async，协程从未被 await → 文档从未创建"""
        import inspect

        from vidknot.adapters.feishu_writer import FeishuWriter

        assert not inspect.iscoroutinefunction(FeishuWriter.create_document)
        # 保留异步包装兼容旧的 await 调用方
        assert inspect.iscoroutinefunction(FeishuWriter.create_document_async)

    def test_placeholder_not_treated_as_credential(self):
        """config.yaml 里的 YOUR_XXX 占位符不能被当成真实凭证"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(destination="notion", use_cache=False)
        kwargs = pipeline._writer_config("notion")
        assert "token" not in kwargs

    def test_obsidian_tags_option_key_alias(self, tmp_path):
        """obsidian_tags 与 tags 两个键名都要生效"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(
            destination="obsidian",
            use_cache=False,
            obsidian_config={"vault_path": str(tmp_path)},
        )
        pipeline.save(
            {"title": "别名标签", "markdown": "# m"},
            {"obsidian_tags": ["别名标签值"]},
        )
        contents = [
            p.read_text(encoding="utf-8")
            for p in tmp_path.rglob("*.md")
            if "别名标签" in p.name
        ]
        assert contents and "别名标签值" in contents[0]


# ============================================================
# MCP 新工具
# ============================================================


class TestMCPAgentContractTools:
    def test_tools_schema_includes_new_tools(self):
        from vidknot.adapters.mcp_server import list_tools_schema

        names = {t["name"] for t in list_tools_schema()}
        assert "video_material" in names
        assert "save_note" in names

    def test_video_material_required_url(self):
        from vidknot.adapters.mcp_server import list_tools_schema

        tool = next(t for t in list_tools_schema() if t["name"] == "video_material")
        assert "url" in tool["inputSchema"]["required"]

    def test_save_note_required_markdown(self):
        from vidknot.adapters.mcp_server import list_tools_schema

        tool = next(t for t in list_tools_schema() if t["name"] == "save_note")
        assert "markdown" in tool["inputSchema"]["required"]

    def test_video_material_call(self):
        from vidknot.adapters.mcp_server import MCPServer

        fake = {"schema": "vidknot.material/1", "title": "T", "search_candidates": ["X"]}
        with patch(
            "vidknot.pipeline.video_knowledge_pipeline.VideoKnowledgePipeline.collect_material",
            return_value=fake,
        ):
            resp = MCPServer()._handle_tools_call(
                {"name": "video_material", "arguments": {"url": "https://example.com/v/1"}},
                1,
            )
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["schema"] == "vidknot.material/1"

    def test_video_material_requires_url(self):
        from vidknot.adapters.mcp_server import MCPServer

        resp = MCPServer()._handle_tools_call(
            {"name": "video_material", "arguments": {}}, 1
        )
        assert resp["error"]["code"] == -32602

    def test_save_note_call(self, tmp_path, monkeypatch):
        from vidknot.adapters.mcp_server import MCPServer

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        resp = MCPServer()._handle_tools_call(
            {
                "name": "save_note",
                "arguments": {
                    "markdown": "# 成稿",
                    "url": "https://example.com/v/1",
                    "title": "成稿",
                    "destination": "obsidian",
                },
            },
            1,
        )
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert "Obsidian:" in payload["saved_to"]
        assert list(tmp_path.rglob("*.md"))

    def test_save_note_requires_markdown(self):
        from vidknot.adapters.mcp_server import MCPServer

        resp = MCPServer()._handle_tools_call({"name": "save_note", "arguments": {}}, 1)
        assert resp["error"]["code"] == -32602

    def test_save_note_storage_error_is_reported(self, monkeypatch):
        from vidknot.adapters.mcp_server import MCPServer

        monkeypatch.delenv("NOTION_TOKEN", raising=False)
        resp = MCPServer()._handle_tools_call(
            {"name": "save_note", "arguments": {"markdown": "x", "destination": "notion"}},
            1,
        )
        assert resp["error"]["code"] == -32005


# ============================================================
# CLI 新模式
# ============================================================


class TestCLIAgentContractModes:
    def test_new_arguments_exist(self):
        """--material / --save-note 等新参数应被 argparse 接受并路由"""
        from vidknot import __main__ as cli

        captured = {}

        def fake_material(args):
            captured["mode"] = "material"
            captured["url"] = args.url
            captured["max_candidates"] = args.max_candidates
            captured["no_diff"] = args.no_diff

        def fake_save_note(args):
            captured["mode"] = "save_note"
            captured["save_note"] = args.save_note
            captured["note_title"] = args.note_title

        # cli.main() 会 load_dotenv(cwd/.env) 往进程环境里塞变量，
        # 必须在调用前后完整还原，避免污染后续用例
        saved_env = dict(os.environ)
        try:
            with patch.object(cli, "run_material_cli", fake_material), \
                 patch.object(cli, "run_save_note_cli", fake_save_note), \
                 patch.object(sys, "argv", ["vidknot", "https://example.com/v/1",
                                           "--material", "--max-candidates", "7", "--no-diff"]):
                cli.main()

            assert captured["mode"] == "material"
            assert captured["url"] == "https://example.com/v/1"
            assert captured["max_candidates"] == 7
            assert captured["no_diff"] is True

            with patch.object(cli, "run_material_cli", fake_material), \
                 patch.object(cli, "run_save_note_cli", fake_save_note), \
                 patch.object(sys, "argv", ["vidknot", "https://example.com/v/1",
                                           "--save-note", "note.md", "--note-title", "T"]):
                cli.main()

            assert captured["mode"] == "save_note"
            assert captured["save_note"] == "note.md"
            assert captured["note_title"] == "T"
        finally:
            os.environ.clear()
            os.environ.update(saved_env)

    def test_save_note_cli_writes_file(self, tmp_path, monkeypatch, capsys):
        from vidknot.__main__ import run_save_note_cli

        note = tmp_path / "note.md"
        note.write_text("# 成稿\n\n内容", encoding="utf-8")
        vault = tmp_path / "vault"
        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

        args = MagicMock()
        args.save_note = str(note)
        args.url = "https://example.com/v/1"
        args.destination = "obsidian"
        args.language = "auto"
        args.note_title = "CLI 成稿"
        args.note_author = ""
        args.note_platform = ""
        args.obsidian_tags = []
        args.feishu_folder = None

        run_save_note_cli(args)
        out = capsys.readouterr().out
        assert "已保存" in out
        assert list(vault.rglob("*.md"))

    def test_save_note_cli_missing_file(self, tmp_path):
        from vidknot.__main__ import run_save_note_cli

        args = MagicMock()
        args.save_note = str(tmp_path / "nope.md")
        with pytest.raises(SystemExit) as exc:
            run_save_note_cli(args)
        assert exc.value.code == 2

    def test_material_cli_emits_json(self, tmp_path, monkeypatch, capsys):
        from vidknot.__main__ import run_material_cli

        fake = {"schema": "vidknot.material/1", "title": "T"}
        args = MagicMock()
        args.url = "https://example.com/v/1"
        args.language = "auto"
        args.no_diff = True
        args.max_candidates = 5
        args.output = str(tmp_path / "material.json")

        with patch(
            "vidknot.pipeline.video_knowledge_pipeline.VideoKnowledgePipeline.collect_material",
            return_value=fake,
        ), patch(
            "vidknot.utils.env_check.check_all_requirements",
            return_value=(True, []),
        ):
            run_material_cli(args)

        payload = json.loads((tmp_path / "material.json").read_text(encoding="utf-8"))
        assert payload["schema"] == "vidknot.material/1"

    def test_material_cli_requires_url(self):
        from vidknot.__main__ import run_material_cli

        args = MagicMock()
        args.url = None
        with pytest.raises(SystemExit) as exc:
            run_material_cli(args)
        assert exc.value.code == 2


# ============================================================
# 校正 / 搜证后端可插拔（不绑定厂商）
# ============================================================


class TestPluggableCorrectionBackend:
    def test_backend_choices(self):
        from vidknot.core.corrector import _CORRECTION_BACKENDS, _SEARCH_BACKENDS

        assert set(_CORRECTION_BACKENDS) == {"auto", "provider", "mmx", "none"}
        assert set(_SEARCH_BACKENDS) == {"auto", "mmx", "none"}

    def test_resolve_backend_unknown_falls_back(self, monkeypatch):
        """未知后端名应回退，而不是抛错"""
        from vidknot.core import corrector

        monkeypatch.setattr(
            "vidknot.utils.config_manager.ConfigManager.get",
            lambda self, *a, **k: "不存在的后端",
        )
        assert corrector._resolve_correction_backend() in {"auto", "provider", "mmx", "none"}
        assert corrector._resolve_search_backend() in {"auto", "mmx", "none"}

    def test_resolve_backend_none_is_explicit(self, monkeypatch):
        """显式配置 none 时应直接返回 none（完全不做校正/搜证）"""
        from vidknot.core import corrector

        monkeypatch.setattr(
            "vidknot.utils.config_manager.ConfigManager.get",
            lambda self, *a, **k: "none",
        )
        assert corrector._resolve_correction_backend() == "none"
        assert corrector._resolve_search_backend() == "none"

    def test_correction_model_reads_config(self):
        from vidknot.core.corrector import _correction_model

        assert isinstance(_correction_model(), str)

    def test_no_hardcoded_minimax_in_corrector(self):
        """校正链路不应再硬编码 MiniMax 模型"""
        source = Path(
            sys.modules["vidknot.core.corrector"].__file__
        ).read_text(encoding="utf-8")
        assert '"MiniMax-M3"' not in source
        assert "'MiniMax-M3'" not in source


# ============================================================
# ASR 语音模型解析（v0.6.14）
# ============================================================


@pytest.fixture
def isolated_config(tmp_path):
    """隔离 ConfigManager 单例：注入临时配置，结束后恢复原实例。

    ConfigManager 是单例，测试里换配置必须整体还原，否则会污染后续用例。
    """
    from vidknot.utils.config_manager import ConfigManager

    original = ConfigManager._instance
    cfg_path = tmp_path / "config.yaml"

    def _make(yaml_text: str):
        cfg_path.write_text(yaml_text, encoding="utf-8")
        ConfigManager._instance = None
        return ConfigManager(config_path=str(cfg_path))

    try:
        yield _make
    finally:
        ConfigManager._instance = original


class TestAsrModelResolution:
    """语音模型与文本模型必须分离（v0.6.14）"""

    def test_empty_config_uses_asr_default(self, isolated_config):
        """空配置必须回落到语音模型默认值，而不是文本模型"""
        from vidknot.core.transcriber import SiliconFlowASR

        isolated_config("{}")
        resolved = SiliconFlowASR()._resolve_model()
        assert resolved == SiliconFlowASR.DEFAULT_MODEL
        assert "DeepSeek" not in resolved

    def test_toplevel_siliconflow_model_used(self, isolated_config):
        """顶层 siliconflow.model 应被采用"""
        from vidknot.core.transcriber import SiliconFlowASR

        isolated_config("siliconflow:\n  model: MyASRModel\n")
        assert SiliconFlowASR()._resolve_model() == "MyASRModel"

    def test_dedicated_asr_key_wins(self, isolated_config):
        """ASR 专属键 siliconflow_asr.model 优先级最高"""
        from vidknot.core.transcriber import SiliconFlowASR

        isolated_config(
            "siliconflow:\n  model: TopLevelModel\n"
            "siliconflow_asr:\n  model: DedicatedAsrModel\n"
        )
        assert SiliconFlowASR()._resolve_model() == "DedicatedAsrModel"

    def test_providers_model_used_when_explicit(self, isolated_config):
        """用户显式设置 providers.siliconflow.model 时仍可采用"""
        from vidknot.core.transcriber import SiliconFlowASR

        isolated_config("providers:\n  siliconflow:\n    model: ExplicitModel\n")
        assert SiliconFlowASR()._resolve_model() == "ExplicitModel"

    def test_constructor_arg_wins(self, isolated_config):
        """构造参数优先级最高"""
        from vidknot.core.transcriber import SiliconFlowASR

        isolated_config("siliconflow:\n  model: TopLevelModel\n")
        assert SiliconFlowASR(model="ExplicitArg")._resolve_model() == "ExplicitArg"

    def test_placeholder_skipped(self, isolated_config):
        """YOUR_ 占位符不应被当成模型名"""
        from vidknot.core.transcriber import SiliconFlowASR

        isolated_config("siliconflow:\n  model: YOUR_MODEL\n")
        assert SiliconFlowASR()._resolve_model() == SiliconFlowASR.DEFAULT_MODEL

    def test_builtin_default_has_no_text_model(self, isolated_config):
        """内置默认配置里不应再出现文本模型名"""
        config = isolated_config("{}")
        assert not config.get("providers", "siliconflow", "model")


# ============================================================
# 对照转写状态 diff_status（v0.6.14）
# ============================================================


class TestDiffStatus:
    """对照转写失败必须可被智能体识别，不能与「无差异」混淆"""

    def _pipeline(self):
        """字幕优先路径：第一次拿字幕（无音频），第二次补下载音频。"""
        from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline

        pipeline = VideoKnowledgePipeline(destination="none", format="raw", use_cache=False)
        pipeline.downloader = MagicMock()
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            side_effect=[
                (None, {"title": "T", "subtitle_text": "字幕全文", "duration": 30}),
                ("/tmp/audio.mp3", {"title": "T", "duration": 30}),
            ]
        )
        return pipeline

    def test_skipped_when_diff_not_requested(self):
        """with_diff=False 时状态为 skipped"""
        bundle = self._pipeline().collect_material(
            "https://example.com/v/1", with_diff=False
        )
        assert bundle["diff_status"] == "skipped"
        assert bundle["diff_reason"]

    def test_ok_when_cross_check_succeeds(self):
        """对照成功时状态为 ok"""
        pipeline = self._pipeline()
        with patch(
            "vidknot.core.transcriber.FasterWhisperASR.transcribe",
            return_value="[  0.0s -    3.4s] 字幕全文",
        ):
            bundle = pipeline.collect_material("https://example.com/v/1", with_diff=True)
        assert bundle["diff_status"] == "ok"
        assert bundle["diff_count"] == 0  # 两份一致

    def test_failed_when_cross_check_raises(self):
        """对照失败时状态为 failed，且带失败原因"""
        pipeline = self._pipeline()
        with patch(
            "vidknot.core.transcriber.FasterWhisperASR.transcribe",
            side_effect=RuntimeError("本地模型加载失败"),
        ):
            bundle = pipeline.collect_material("https://example.com/v/1", with_diff=True)
        assert bundle["diff_status"] == "failed"
        assert "本地模型加载失败" in bundle["diff_reason"]
        assert bundle["diff_count"] == 0

    def test_failed_when_cross_check_empty(self):
        """对照转写为空也视为 failed（否则会被读成「无差异」）"""
        pipeline = self._pipeline()
        with patch(
            "vidknot.core.transcriber.FasterWhisperASR.transcribe",
            return_value="",
        ):
            bundle = pipeline.collect_material("https://example.com/v/1", with_diff=True)
        assert bundle["diff_status"] == "failed"
        assert bundle["diff_reason"]

    def test_failed_when_audio_download_fails(self):
        """补下载音频失败时状态为 failed"""
        pipeline = self._pipeline()
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            side_effect=[
                (None, {"title": "T", "subtitle_text": "字幕全文", "duration": 30}),
                RuntimeError("下载失败"),
            ]
        )
        bundle = pipeline.collect_material("https://example.com/v/1", with_diff=True)
        assert bundle["diff_status"] == "failed"
        assert "下载失败" in bundle["diff_reason"]

    def test_notes_explain_diff_status(self):
        """notes 里要点明 diff_status 的语义"""
        bundle = self._pipeline().collect_material(
            "https://example.com/v/1", with_diff=False
        )
        assert "diff_status" in bundle["notes"]
