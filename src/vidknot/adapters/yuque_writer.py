"""
VidkNot 语雀文档写入适配器

使用语雀 API 创建文档
支持：个人文档、知识库、按目录组织
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


class YuqueWriter:
    """
    语雀文档写入器

    使用语雀 API 写入文档
    支持：
    - 创建新文档
    - 按目录组织
    - 知识库节点
    """

    def __init__(
        self,
        token: Optional[str] = None,
        login: Optional[str] = None,
        default_path: Optional[str] = None,
    ):
        self.token = token or os.getenv("YUQUE_TOKEN")
        self.login = login or os.getenv("YUQUE_LOGIN")
        self.default_path = default_path or os.getenv("YUQUE_PATH", "VidkNot")

        if not self.token:
            raise NoAPIKeyError(
                "语雀 Token 未设置，请配置 YUQUE_TOKEN"
            )

        self._client = None
        self._base_url = "https://www.yuque.com/api/v2"

    def _get_client(self):
        """获取语雀 API 客户端"""
        if self._client is None:
            import requests

            self._client = requests.Session()
            self._client.headers.update({
                "X-Auth-Token": self.token,
                "Content-Type": "application/json",
            })
        return self._client

    def create_document(
        self,
        title: str,
        markdown_content: str,
        path: Optional[str] = None,
        description: Optional[str] = None,
    ) -> str:
        """
        在语雀创建文档

        Args:
            title: 文档标题
            markdown_content: Markdown 内容
            path: 文档路径（如 "VidkNot/视频笔记"）
            description: 文档描述

        Returns:
            文档 URL
        """
        client = self._get_client()

        slug = self._generate_slug(title)
        doc_path = path or self.default_path

        body = {
            "title": title,
            "slug": slug,
            "body": markdown_content,
            "format": "markdown",
            "description": description or f"视频笔记: {title}",
            "public": 0,
        }

        if doc_path and self.login:
            body["namespace"] = self.login

        try:
            url = f"{self._base_url}/repos/{self.login}/{doc_path}/docs"
            response = client.post(url, json=body)
            response.raise_for_status()

            data = response.json()
            if data.get("data"):
                doc = data["data"]
                logger.info(f"[Yuque] 文档创建成功: {doc.get('url')}")
                return doc.get("url", "")

            raise StorageError(f"语雀返回数据格式错误: {data}")

        except Exception as e:
            raise StorageError(f"语雀文档创建失败: {e}")

    def _generate_slug(self, title: str) -> str:
        """生成 URL 友好的 slug"""
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        slug = slug.strip('-')[:50]
        import time
        return f"{slug}-{int(time.time())}"

    def save(
        self,
        title: str,
        markdown_content: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        保存文档（兼容接口）

        Args:
            title: 文档标题
            markdown_content: Markdown 内容
            options: 保存选项

        Returns:
            文档 URL
        """
        options = options or {}
        path = options.get("path", self.default_path)

        return self.create_document(
            title=title,
            markdown_content=markdown_content,
            path=path,
        )
