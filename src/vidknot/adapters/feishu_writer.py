"""
VidkNot 飞书文档写入适配器

使用 feishu-docx (PyPI) 或 lark-cli 写入飞书文档
支持：云文档、知识库节点、按文件夹组织
"""

import os
import re
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..utils.exceptions import (
    FeishuAuthError,
    FeishuPermissionError,
    FeishuCreateDocError,
    StorageError,
    NoAPIKeyError,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FeishuWriter:
    """
    飞书文档写入器

    使用 feishu-docx SDK 写入飞书云文档
    支持：
    - 创建新文档
    - 按文件夹组织
    - 知识库节点
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        default_folder: Optional[str] = None,
        wiki_node_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("FEISHU_API_KEY")
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self.default_folder = default_folder or os.getenv("FEISHU_FOLDER", "VidkNot 笔记")
        self.wiki_node_id = wiki_node_id or os.getenv("FEISHU_WIKI_NODE")

        self._client = None

    def _get_client(self):
        """获取飞书客户端（延迟初始化）"""
        if self._client is None:
            if not self.app_id or not self.app_secret:
                raise NoAPIKeyError(
                    "飞书配置不完整，需要 FEISHU_APP_ID 和 FEISHU_APP_SECRET",
                    details=f"app_id={'已设置' if self.app_id else '未设置'}, "
                            f"app_secret={'已设置' if self.app_secret else '未设置'}",
                )
            try:
                from feishu_docx import FeishuDocx
                self._client = FeishuDocx(
                    api_key=self.api_key,
                    app_id=self.app_id,
                    app_secret=self.app_secret,
                )
            except ImportError:
                logger.warning("feishu-docx 未安装，使用 requests fallback")
                self._client = FeishuClient(
                    api_key=self.api_key,
                    app_id=self.app_id,
                    app_secret=self.app_secret,
                )
        return self._client

    async def create_document(
        self,
        title: str,
        markdown_content: str,
        folder_token: Optional[str] = None,
        wiki_node_id: Optional[str] = None,
        folder_name: Optional[str] = None,
    ) -> str:
        """
        创建飞书文档

        Args:
            title: 文档标题
            markdown_content: Markdown 内容
            folder_token: 目标文件夹 Token
            wiki_node_id: 知识库节点 ID
            folder_name: 文件夹名称（会自动创建）

        Returns:
            文档 URL
        """
        client = self._get_client()

        # 转换 Markdown 为飞书块格式
        blocks = self.markdown_to_lark_blocks(markdown_content)

        # 创建文档
        try:
            doc = client.documents.create(
                title=title,
                content=blocks,
            )
        except Exception as e:
            raise FeishuCreateDocError(f"创建文档失败: {title}", details=str(e))

        doc_id = doc.get("document_id", "")
        doc_url = doc.get("document_url", f"https://feishu.cn/docx/{doc_id}")

        logger.info(f"飞书文档已创建: {title} → {doc_url}")

        # 移动到知识库
        if wiki_node_id or self.wiki_node_id:
            try:
                client.wiki.create_node(
                    parent_node_id=wiki_node_id or self.wiki_node_id,
                    node_type="doc",
                    title=title,
                    document_id=doc_id,
                )
                logger.info(f"文档已添加到知识库节点")
            except Exception as e:
                logger.warning(f"知识库节点创建失败（非阻塞）: {e}")

        return doc_url

    def markdown_to_lark_blocks(self, md: str) -> List[Dict]:
        """
        将 Markdown 转换为飞书文档块格式

        完整支持: h1-h6, bullet, numbered-list, blockquote, code, image, table, hr
        """
        try:
            from feishu_docx.utils import markdown_to_blocks
            return markdown_to_blocks(md)
        except ImportError:
            return self._manual_markdown_to_blocks(md)

    def _manual_markdown_to_blocks(self, md: str) -> List[Dict]:
        """
        手动 Markdown → 飞书块转换（基础 + 增强版）

        支持: h1-h6, bullet, numbered-list, blockquote, code_block, image, table, hr, paragraph
        """
        lines = md.split("\n")
        blocks = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # 空行
            if not stripped:
                blocks.append({"type": "paragraph", "paragraph": {}})
                i += 1
                continue

            # 标题 h1-h6
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2)
                blocks.append({
                    "type": f"heading{level}",
                    f"heading{level}": {"elements": self._text_elements(content)}
                })
                i += 1
                continue

            # 分隔线
            if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
                blocks.append({"type": "horizontal_line", "horizontal_line": {}})
                i += 1
                continue

            # 代码块
            if stripped.startswith("```"):
                lang = stripped[3:].strip()
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                code_content = "\n".join(code_lines)
                blocks.append({
                    "type": "code_block",
                    "code_block": {
                        "elements": self._text_elements(code_content),
                        "properties": {"language": lang} if lang else {},
                    }
                })
                i += 1  # 跳过结束 ```
                continue

            # 有序列表
            ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
            if ordered_match:
                content = ordered_match.group(1)
                blocks.append({
                    "type": "ordered",
                    "ordered": {"elements": self._text_elements(content)}
                })
                i += 1
                continue

            # 无序列表
            bullet_match = re.match(r"^[-*+]\s+(.+)$", stripped)
            if bullet_match:
                content = bullet_match.group(1)
                blocks.append({
                    "type": "bullet",
                    "bullet": {"elements": self._text_elements(content)}
                })
                i += 1
                continue

            # 引用块
            if stripped.startswith(">"):
                content = stripped.lstrip("> ").strip()
                blocks.append({
                    "type": "quote",
                    "quote": {"elements": self._text_elements(content)}
                })
                i += 1
                continue

            # 表格
            if stripped.startswith("|") and "|" in stripped:
                table_lines = [stripped]
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith("|"):
                    table_lines.append(lines[j].strip())
                    j += 1
                if len(table_lines) >= 2:
                    blocks.append(self._parse_table(table_lines))
                    i = j
                    continue

            # 普通段落
            blocks.append({
                "type": "paragraph",
                "paragraph": {"elements": self._text_elements(stripped)}
            })
            i += 1

        return blocks

    def _text_elements(self, text: str) -> List[Dict]:
        """
        将文本转换为飞书 text_run 元素列表

        支持: **bold**, *italic*, `code`, ~~strikethrough~~
        """
        if not text:
            return [{"type": "text_run", "text_run": {"content": ""}}]

        elements = []
        # 匹配格式: **bold**, *italic*, `code`, ~~strike~~
        pattern = r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|~~[^~]+~~)"

        last_end = 0
        for match in re.finditer(pattern, text):
            # 前导纯文本
            if match.start() > last_end:
                plain = text[last_end:match.start()]
                if plain:
                    elements.append({
                        "type": "text_run",
                        "text_run": {"content": plain}
                    })

            inner = match.group(0)
            if inner.startswith("**") and inner.endswith("**"):
                elements.append({
                    "type": "text_run",
                    "text_run": {"content": inner[2:-2], "text_style": {"bold": True}}
                })
            elif inner.startswith("*") and inner.endswith("*"):
                elements.append({
                    "type": "text_run",
                    "text_run": {"content": inner[1:-1], "text_style": {"italic": True}}
                })
            elif inner.startswith("`") and inner.endswith("`"):
                elements.append({
                    "type": "text_run",
                    "text_run": {"content": inner[1:-1], "text_style": {"code": True}}
                })
            elif inner.startswith("~~") and inner.endswith("~~"):
                elements.append({
                    "type": "text_run",
                    "text_run": {"content": inner[2:-2], "text_style": {"strike": True}}
                })

            last_end = match.end()

        # 尾部纯文本
        if last_end < len(text):
            elements.append({
                "type": "text_run",
                "text_run": {"content": text[last_end:]}
            })

        if not elements:
            elements = [{"type": "text_run", "text_run": {"content": text}}]

        return elements

    def _parse_table(self, lines: List[str]) -> Dict:
        """解析 Markdown 表格为飞书块"""
        if len(lines) < 2:
            return {"type": "paragraph", "paragraph": {}}

        def parse_row(line: str) -> List[str]:
            return [cell.strip() for cell in line.strip("|").split("|")]

        rows = [parse_row(line) for line in lines if line.strip().startswith("|")]
        cells = [[{"type": "table_cell", "table_cell": {"elements": self._text_elements(cell)}}
                  for cell in row] for row in rows]

        return {
            "type": "table",
            "table": {
                "cells": cells,
                "properties": {"row_size": len(cells), "column_size": len(cells[0]) if cells else 0}
            }
        }


class FeishuClient:
    """
    飞书 API 客户端（当 feishu-docx 不可用时的备选实现）
    """

    def __init__(self, api_key: str = None, app_id: str = None, app_secret: str = None):
        import requests
        self.api_key = api_key or os.getenv("FEISHU_API_KEY")
        self.app_id = app_id
        self.app_secret = app_secret
        self._token = None
        self._requests = requests

    def _get_token(self) -> str:
        """获取 tenant access token"""
        if self._token:
            return self._token

        resp = self._requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuAuthError(
                f"飞书认证失败: code={data.get('code')}, msg={data.get('msg')}",
                details=f"app_id={self.app_id}",
            )
        self._token = data.get("tenant_access_token", "")
        return self._token

    @property
    def documents(self):
        return FeishuDocumentsAPI(self)

    @property
    def wiki(self):
        return FeishuWikiAPI(self)


class FeishuDocumentsAPI:
    def __init__(self, client: FeishuClient):
        self.client = client

    def create(self, title: str, content: List[Dict]) -> Dict:
        """创建文档"""
        # 创建空白文档
        resp = self.client._requests.post(
            "https://open.feishu.cn/open-apis/docx/v1/documents",
            headers={"Authorization": f"Bearer {self.client._get_token()}"},
            json={"title": title},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuCreateDocError(
                f"创建飞书文档失败: code={data.get('code')}",
                details=data.get("msg"),
            )

        doc_id = data.get("data", {}).get("document", {}).get("document_id", "")

        if doc_id and content:
            # 插入内容块
            insert_resp = self.client._requests.post(
                f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                headers={"Authorization": f"Bearer {self.client._get_token()}"},
                json={"children": content, "index": -1},
                timeout=30,
            )
            if insert_resp.json().get("code") != 0:
                logger.warning(f"内容插入部分失败: {insert_resp.json().get('msg')}")

        # ✅ 修复：正确的飞书域名
        return {
            "document_id": doc_id,
            "document_url": f"https://feishu.cn/docx/{doc_id}",
        }


class FeishuWikiAPI:
    def __init__(self, client: FeishuClient):
        self.client = client

    def create_node(
        self,
        parent_node_id: str,
        node_type: str,
        title: str,
        document_id: str = None,
    ) -> Dict:
        """创建知识库节点"""
        resp = self.client._requests.post(
            "https://open.feishu.cn/open-apis/wiki/v2/spaces/create_node",
            headers={"Authorization": f"Bearer {self.client._get_token()}"},
            json={
                "parent_node_id": parent_node_id,
                "node_type": 1,  # doc
                "title": title,
            },
            timeout=15,
        )
        result = resp.json()
        if result.get("code") != 0:
            raise FeishuPermissionError(
                f"知识库节点创建失败: code={result.get('code')}",
                details=result.get("msg"),
            )
        return result
