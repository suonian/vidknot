"""
测试 vidknot.adapters 下的所有 writer

覆盖：
- ObsidianWriter: save_note、文件夹创建、frontmatter 处理
- NotionWriter: 实例化、API 校验
- YuqueWriter: 实例化、API 校验
- FeishuWriter: 实例化、markdown 转换
- agent_bridge: tool metadata
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ========== ObsidianWriter ==========


class TestObsidianWriter:
    """测试 ObsidianWriter"""

    def test_init_with_default_folder(self, temp_dir):
        from vidknot.adapters.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter(vault_path=str(temp_dir), default_folder="视频笔记")
        # 注意：vault_path 可能是私有属性
        assert writer is not None
        assert writer.default_folder == "视频笔记"

    def test_save_note_creates_file(self, temp_dir):
        from vidknot.adapters.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter(vault_path=str(temp_dir), default_folder="视频笔记")

        markdown = "## 测试标题\n\n这是内容。"
        metadata = {
            "title": "测试视频",
            "author": "测试作者",
            "date": "2026-07-30",
            "source_url": "https://example.com",
            "duration": 120,
        }

        path = writer.save_note(
            markdown_content=markdown,
            metadata=metadata,
            folder="测试笔记",
            filename="test.md",
        )
        assert path.exists()
        assert path.read_text(encoding="utf-8")

    def test_save_note_creates_subfolder(self, temp_dir):
        from vidknot.adapters.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter(vault_path=str(temp_dir), default_folder="视频笔记")

        markdown = "## 内容"
        metadata = {"title": "t", "author": "a"}
        path = writer.save_note(
            markdown_content=markdown,
            metadata=metadata,
            folder="新建子文件夹/子文件夹2",
            filename="nested.md",
        )
        assert path.exists()
        assert "子文件夹2" in str(path)

    def test_save_note_with_tags(self, temp_dir):
        from vidknot.adapters.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter(vault_path=str(temp_dir))

        markdown = "## 内容"
        metadata = {"title": "t", "author": "a", "tags": ["tag1", "tag2"]}
        path = writer.save_note(
            markdown_content=markdown,
            metadata=metadata,
            filename="with_tags.md",
        )
        content = path.read_text(encoding="utf-8")
        # 自动添加的 frontmatter 应包含 tags
        assert "tag1" in content or "tags" in content

    def test_save_note_returns_path_object(self, temp_dir):
        from vidknot.adapters.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter(vault_path=str(temp_dir))

        path = writer.save_note(
            markdown_content="# content",
            metadata={"title": "t"},
            filename="check_path.md",
        )
        assert isinstance(path, Path)

    def test_save_note_existing_file_adds_timestamp(self, temp_dir):
        """同名文件存在时应加时间戳而不是覆盖"""
        from vidknot.adapters.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter(vault_path=str(temp_dir))

        path1 = writer.save_note(
            markdown_content="v1",
            metadata={"title": "t"},
            filename="same.md",
        )
        path2 = writer.save_note(
            markdown_content="v2",
            metadata={"title": "t"},
            filename="same.md",
        )
        assert path1.exists() and path2.exists()
        # 第二次应使用不同的文件名（带时间戳）
        assert path1 != path2

    def test_get_vault_stats(self, temp_dir):
        """get_vault_stats 应返回 vault 统计信息"""
        from vidknot.adapters.obsidian_writer import ObsidianWriter
        writer = ObsidianWriter(vault_path=str(temp_dir))

        # 创建一些笔记
        writer.save_note(
            markdown_content="a", metadata={"title": "a"}, folder="f1"
        )
        writer.save_note(
            markdown_content="b", metadata={"title": "b"}, folder="f2"
        )

        stats = writer.get_vault_stats()
        assert isinstance(stats, dict)
        # 应包含 note_count 等字段（具体字段取决于实现）
        # 至少应该是个非空 dict
        assert stats


# ========== NotionWriter ==========


class TestNotionWriter:
    """测试 NotionWriter"""

    def test_init_without_token_raises(self):
        """无 token 应抛 NoAPIKeyError"""
        from vidknot.adapters.notion_writer import NotionWriter
        from vidknot.utils.exceptions import NoAPIKeyError
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(NoAPIKeyError, match="Notion"):
                NotionWriter()

    def test_init_with_token(self):
        from vidknot.adapters.notion_writer import NotionWriter
        writer = NotionWriter(token="test_token")
        assert writer is not None

    def test_init_with_page_and_database(self):
        from vidknot.adapters.notion_writer import NotionWriter
        writer = NotionWriter(
            token="test", parent_page_id="page_123", database_id="db_456"
        )
        assert writer is not None


# ========== YuqueWriter ==========


class TestYuqueWriter:
    """测试 YuqueWriter"""

    def test_init_without_token_raises(self):
        """无 token 应抛 NoAPIKeyError"""
        from vidknot.adapters.yuque_writer import YuqueWriter
        from vidknot.utils.exceptions import NoAPIKeyError
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(NoAPIKeyError, match="语雀"):
                YuqueWriter()

    def test_init_with_token_and_login(self):
        from vidknot.adapters.yuque_writer import YuqueWriter
        writer = YuqueWriter(token="test_token", login="test_user")
        assert writer.token == "test_token"
        assert writer.login == "test_user"

    def test_init_with_path(self):
        from vidknot.adapters.yuque_writer import YuqueWriter
        writer = YuqueWriter(token="t", login="u", default_path="/some/path")
        assert writer.default_path == "/some/path"


# ========== FeishuWriter ==========


class TestFeishuWriter:
    """测试 FeishuWriter"""

    def test_init_with_minimal_config(self):
        from vidknot.adapters.feishu_writer import FeishuWriter
        writer = FeishuWriter(app_id="id", app_secret="secret")
        assert writer is not None

    def test_init_with_default_folder(self):
        from vidknot.adapters.feishu_writer import FeishuWriter
        writer = FeishuWriter(
            app_id="id", app_secret="secret", default_folder="my_folder"
        )
        assert writer.default_folder == "my_folder"

    def test_markdown_to_lark_blocks_returns_list(self):
        """markdown 转换应返回 list of dict"""
        from vidknot.adapters.feishu_writer import FeishuWriter
        writer = FeishuWriter(app_id="id", app_secret="secret")

        md = "# 标题\n\n段落\n\n- 列表项 1\n- 列表项 2"
        blocks = writer.markdown_to_lark_blocks(md)
        assert isinstance(blocks, list)
        assert len(blocks) > 0

    def test_markdown_to_lark_blocks_handles_empty(self):
        from vidknot.adapters.feishu_writer import FeishuWriter
        writer = FeishuWriter(app_id="id", app_secret="secret")

        blocks = writer.markdown_to_lark_blocks("")
        assert isinstance(blocks, list)


# ========== agent_bridge ==========


class TestAgentBridge:
    """测试 agent_bridge 模块"""

    def test_get_tool_metadata(self):
        """get_tool_metadata 应返回工具元数据"""
        import vidknot.adapters.agent_bridge as bridge
        meta = bridge.get_tool_metadata()
        assert isinstance(meta, dict)
        # 应有工具名和 schema
        assert "name" in meta or len(meta) > 0

    def test_execute_tool_returns_dict(self):
        """execute_tool 应返回 dict"""
        import vidknot.adapters.agent_bridge as bridge
        result = bridge.execute_tool({})
        assert isinstance(result, dict)