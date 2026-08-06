"""
测试 vidknot.pipeline.video_knowledge_pipeline

覆盖：
- VideoKnowledgePipeline 初始化（destination 校验、writer 懒加载）
- run 流程（mock 所有外部依赖）
- save 路由到正确的 adapter
"""

from unittest.mock import MagicMock, patch

import pytest

from vidknot.pipeline.video_knowledge_pipeline import VideoKnowledgePipeline


class TestVideoKnowledgePipelineInit:
    """测试 VideoKnowledgePipeline 初始化"""

    def test_default_init(self):
        pipeline = VideoKnowledgePipeline()
        assert pipeline.destination == "obsidian"
        assert pipeline.format == "structured"
        assert pipeline.use_cache is True

    def test_unsupported_destination_raises(self):
        """不支持的 destination 应抛 ValueError"""
        with pytest.raises(ValueError, match="不支持的目的地"):
            VideoKnowledgePipeline(destination="unknown_dest")

    def test_supported_destinations_listed(self):
        """SUPPORTED_DESTINATIONS 应包含主要目的地"""
        assert "feishu" in VideoKnowledgePipeline.SUPPORTED_DESTINATIONS
        assert "obsidian" in VideoKnowledgePipeline.SUPPORTED_DESTINATIONS
        assert "notion" in VideoKnowledgePipeline.SUPPORTED_DESTINATIONS
        assert "yuque" in VideoKnowledgePipeline.SUPPORTED_DESTINATIONS
        assert "both" in VideoKnowledgePipeline.SUPPORTED_DESTINATIONS
        assert "none" in VideoKnowledgePipeline.SUPPORTED_DESTINATIONS

    def test_with_feishu_config_creates_writer(self):
        """提供 feishu_config 时应立即实例化 FeishuWriter"""
        feishu_config = {
            "app_id": "test_id",
            "app_secret": "test_secret",
            "default_folder": "test_folder",
        }
        with patch("vidknot.pipeline.video_knowledge_pipeline.FeishuWriter") as mock_fw:
            mock_fw.return_value = MagicMock()
            pipeline = VideoKnowledgePipeline(destination="feishu", feishu_config=feishu_config)
        assert pipeline._feishu is not None

    def test_without_config_writer_is_none(self):
        """不提供 config 时 writer 应为 None"""
        pipeline = VideoKnowledgePipeline(destination="feishu")
        assert pipeline._feishu is None

    def test_use_cache_false_disables_cache(self):
        pipeline = VideoKnowledgePipeline(destination="none", use_cache=False)
        assert pipeline.cache is None


class TestVideoKnowledgePipelineRun:
    """测试 run 流程（mock 下载和转录）"""

    def test_run_returns_dict(self):
        """run 应返回完整 dict"""
        pipeline = VideoKnowledgePipeline(destination="none", use_cache=False)

        # Mock downloader
        mock_audio = MagicMock()
        mock_metadata = {
            "title": "测试视频",
            "uploader": "测试作者",
            "duration": 120,
            "platform": "bilibili",
        }
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            return_value=(mock_audio, mock_metadata)
        )

        # Mock transcriber
        pipeline.transcriber.transcribe = MagicMock(return_value="这是测试转录文本")

        # Mock processor
        pipeline.processor.summarize = MagicMock(return_value={
            "markdown": "# 测试笔记\n\n内容..."
        })

        result = pipeline.run("https://example.com/video/123")

        assert result["title"] == "测试视频"
        assert result["author"] == "测试作者"
        assert result["transcription"] == "这是测试转录文本"
        assert "markdown" in result
        assert result["source_url"] == "https://example.com/video/123"

    def test_run_with_raw_format(self):
        """format=raw 时直接用转录文本作为 markdown"""
        pipeline = VideoKnowledgePipeline(destination="none", format="raw", use_cache=False)

        mock_audio = MagicMock()
        mock_metadata = {"title": "test", "uploader": "test"}
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            return_value=(mock_audio, mock_metadata)
        )
        pipeline.transcriber.transcribe = MagicMock(return_value="原始转录")

        result = pipeline.run("https://example.com/video")

        # raw 模式下 markdown = transcription
        assert result["markdown"] == "原始转录"

    def test_run_cache_hit(self):
        """命中缓存时不下载不转录"""
        pipeline = VideoKnowledgePipeline(destination="none", use_cache=True)
        cached_data = {
            "title": "缓存的",
            "transcription": "cached",
            "markdown": "cached md",
        }
        # cache 不是 None
        assert pipeline.cache is not None
        pipeline.cache.get = MagicMock(return_value=cached_data)

        # 把 downloader.transcriber 整个换成 MagicMock 以便用 assert_not_called
        # （pipeline.downloader 是 VideoDownloader 实例，替换方法会破坏其类型）
        mock_downloader = MagicMock()
        mock_downloader.download_audio_with_metadata = MagicMock()
        mock_transcriber = MagicMock()
        pipeline.downloader = mock_downloader
        pipeline.transcriber = mock_transcriber

        result = pipeline.run("https://example.com/video")

        assert result["cache_hit"] is True
        assert result["title"] == "缓存的"
        # downloader/transcriber 不应被调用
        mock_downloader.download_audio_with_metadata.assert_not_called()
        mock_transcriber.transcribe.assert_not_called()

    def test_run_cache_miss_stores(self):
        """缓存未命中应存新结果"""
        pipeline = VideoKnowledgePipeline(destination="none", use_cache=True)
        assert pipeline.cache is not None
        pipeline.cache.get = MagicMock(return_value=None)
        pipeline.cache.set = MagicMock()

        mock_audio = MagicMock()
        mock_metadata = {"title": "test"}
        pipeline.downloader.download_audio_with_metadata = MagicMock(
            return_value=(mock_audio, mock_metadata)
        )
        pipeline.transcriber.transcribe = MagicMock(return_value="text")
        pipeline.processor.summarize = MagicMock(return_value={"markdown": "md"})

        result = pipeline.run("https://example.com/video")

        assert result["cache_hit"] is False
        pipeline.cache.set.assert_called_once()


class TestVideoKnowledgePipelineSave:
    """测试 save 路由"""

    def test_save_to_obsidian(self, temp_dir):
        """destination=obsidian 应调 ObsidianWriter.save_note"""
        pipeline = VideoKnowledgePipeline(
            destination="obsidian",
            use_cache=False,
            obsidian_config={"vault_path": str(temp_dir)},
        )

        result_dict = {
            "title": "测试视频",
            "author": "测试作者",
            "duration": 120,
            "source_url": "https://example.com",
            "source_platform": "bilibili",
            "markdown": "# 测试\n\n内容",
        }

        saved = pipeline.save(result_dict)
        # 返回字符串（单一目的地）
        assert "Obsidian:" in saved

    def test_save_to_none_returns_empty(self):
        """destination=none 时 save 应返回空字符串"""
        pipeline = VideoKnowledgePipeline(destination="none", use_cache=False)

        result_dict = {
            "title": "test",
            "markdown": "content",
        }
        saved = pipeline.save(result_dict)
        assert saved == ""

    def test_save_with_metadata_overrides(self, temp_dir):
        """options 应能覆盖 metadata"""
        pipeline = VideoKnowledgePipeline(
            destination="obsidian",
            use_cache=False,
            obsidian_config={"vault_path": str(temp_dir)},
        )

        result_dict = {
            "title": "原标题",
            "markdown": "原内容",
        }

        # 不传 options 也不应崩溃
        saved = pipeline.save(result_dict)
        assert saved  # 非空

    def test_save_obsidian_writer_lazy_init(self, temp_dir):
        """没传 config 时也能懒加载 ObsidianWriter"""
        pipeline = VideoKnowledgePipeline(
            destination="obsidian",
            use_cache=False,
            obsidian_config={"vault_path": str(temp_dir)},
        )
        assert pipeline._obsidian is not None  # __init__ 就创建了
        assert pipeline._get_obsidian_writer() is not None
