"""
VidkNot Notion 文档写入适配器

使用 Notion API 创建笔记页面
支持：创建页面、数据库条目
"""

import os
import re
from typing import Optional, Dict, Any

from ..utils.exceptions import (
    StorageError,
    NoAPIKeyError,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class NotionWriter:
    """
    Notion 笔记写入器

    使用 Notion API 写入笔记
    支持：
    - 创建独立页面
    - 添加到数据库
    """

    def __init__(
        self,
        token: Optional[str] = None,
        parent_page_id: Optional[str] = None,
        database_id: Optional[str] = None,
    ):
        self.token = token or os.getenv("NOTION_TOKEN")
        self.parent_page_id = parent_page_id or os.getenv("NOTION_PAGE_ID")
        self.database_id = database_id or os.getenv("NOTION_DATABASE_ID")

        if not self.token:
            raise NoAPIKeyError(
                "Notion Token 未设置，请配置 NOTION_TOKEN"
            )

        self._base_url = "https://api.notion.com/v1"
        self._client = None

    def _get_client(self):
        """获取 Notion API 客户端"""
        if self._client is None:
            import requests

            self._client = requests.Session()
            self._client.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            })
        return self._client

    def _markdown_to_notion_blocks(self, markdown: str) -> list:
        """将 Markdown 转换为 Notion blocks"""
        blocks = []
        lines = markdown.split("\n")
        current_block = None

        for line in lines:
            line = line.rstrip()

            if not line:
                current_block = None
                continue

            if line.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": line[4:]}}]
                    }
                })
            elif line.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                    }
                })
            elif line.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                    }
                })
            elif line.startswith("- "):
                if current_block and current_block["type"] == "bulleted_list_item":
                    current_block["bulleted_list_item"]["rich_text"].append({
                        "type": "text",
                        "text": {"content": line[2:]}
                    })
                else:
                    blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                        }
                    })
                    current_block = blocks[-1]
            elif line.startswith("1. ") or line.startswith("1) "):
                if current_block and current_block["type"] == "numbered_list_item":
                    current_block["numbered_list_item"]["rich_text"].append({
                        "type": "text",
                        "text": {"content": re.sub(r"^\d+[\.\)]\s*", "", line)}
                    })
                else:
                    blocks.append({
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": [{"type": "text", "text": {
                                "content": re.sub(r"^\d+[\.\)]\s*", "", line)
                            }}]
                        }
                    })
                    current_block = blocks[-1]
            elif line.startswith("```"):
                if current_block and current_block["type"] == "code":
                    current_block["code"]["rich_text"].append({
                        "type": "text",
                        "text": {"content": line[3:]}
                    })
                else:
                    blocks.append({
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [{"type": "text", "text": {"content": ""}}],
                            "language": "plain text"
                        }
                    })
                    current_block = blocks[-1]
            else:
                text_content = line
                text_content = re.sub(r'\*\*(.+?)\*\*', r'\1', text_content)
                text_content = re.sub(r'\*(.+?)\*', r'\1', text_content)
                text_content = re.sub(r'__(.+?)__', r'\1', text_content)
                text_content = re.sub(r'_(.+?)_', r'\1', text_content)
                text_content = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text_content)

                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": text_content}}]
                    }
                })
                current_block = blocks[-1]

        return blocks

    def create_page(
        self,
        title: str,
        markdown_content: str,
        parent_id: Optional[str] = None,
    ) -> str:
        """
        在 Notion 创建页面

        Args:
            title: 页面标题
            markdown_content: Markdown 内容
            parent_id: 父页面 ID（可选，默认使用配置的 parent_page_id）

        Returns:
            页面 URL
        """
        client = self._get_client()
        parent_page = parent_id or self.parent_page_id

        if not parent_page:
            raise StorageError("未设置 Notion 父页面 ID，请配置 NOTION_PAGE_ID")

        blocks = self._markdown_to_notion_blocks(markdown_content)

        payload = {
            "parent": {"page_id": parent_page},
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
            "children": blocks[:100]
        }

        try:
            response = client.post(f"{self._base_url}/pages", json=payload)
            response.raise_for_status()

            data = response.json()
            page_id = data.get("id", "").replace("-", "")
            url = f"https://notion.so/{page_id}"

            logger.info(f"[Notion] 页面创建成功: {url}")
            return url

        except Exception as e:
            raise StorageError(f"Notion 页面创建失败: {e}")

    def save(
        self,
        title: str,
        markdown_content: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        保存笔记（兼容接口）

        Args:
            title: 笔记标题
            markdown_content: Markdown 内容
            options: 保存选项

        Returns:
            页面 URL
        """
        options = options or {}
        parent_id = options.get("parent_id", self.parent_page_id)

        return self.create_page(
            title=title,
            markdown_content=markdown_content,
            parent_id=parent_id,
        )
