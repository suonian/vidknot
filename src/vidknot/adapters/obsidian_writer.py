"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot Obsidian Vault 写入适配器

将笔记保存到本地 Obsidian Vault
支持：自动文件名生成、文件夹组织、YAML Frontmatter、双向链接
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..utils.exceptions import (
    ObsidianVaultNotFoundError,
    ObsidianWriteError,
    StorageError,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ObsidianWriter:
    """
    Obsidian Vault 写入器

    将笔记保存到本地 Obsidian Vault
    自动处理：
    - 文件名生成（处理特殊字符）
    - 文件夹组织（按日期/标签）
    - YAML Frontmatter（Obsidian 规范格式）
    - 双向链接索引
    """

    def __init__(
        self,
        vault_path: Optional[str] = None,
        default_folder: str = "视频笔记",
        auto_create_folders: bool = True,
    ):
        self.vault = Path(vault_path or os.getenv("OBSIDIAN_VAULT_PATH", "./obsidian-vault"))
        self.default_folder = default_folder
        self.auto_create_folders = auto_create_folders

    def save_note(
        self,
        markdown_content: str,
        metadata: Dict[str, Any],
        folder: Optional[str] = None,
        filename: Optional[str] = None,
        tags: Optional[List[str]] = None,
        add_timestamp: bool = True,
    ) -> Path:
        """
        保存笔记到 Obsidian Vault

        Args:
            markdown_content: Markdown 内容
            metadata: 元数据字典 (title, author, duration, source_url, etc.)
            folder: 保存文件夹（None=使用默认）
            filename: 文件名（None=自动生成）
            tags: 标签列表
            add_timestamp: 是否添加时间戳到文件名

        Returns:
            保存的文件路径
        """
        # 验证 Vault 路径
        if self.vault.exists() and not self.vault.is_dir():
            raise ObsidianVaultNotFoundError(
                f"Vault 路径存在但不是目录: {self.vault}",
            )

        # 构建 Frontmatter
        frontmatter = self._build_frontmatter(metadata, tags)

        # 组合完整内容
        full_content = frontmatter + "\n\n" + markdown_content

        # 生成文件名
        if filename is None:
            filename = self._generate_filename(metadata, add_timestamp)

        if not filename.endswith(".md"):
            filename += ".md"

        # 确定保存路径
        save_folder = self.vault / (folder or self.default_folder)
        if self.auto_create_folders:
            save_folder.mkdir(parents=True, exist_ok=True)

        file_path = save_folder / filename
        file_path = self._resolve_filename_conflict(file_path)

        # 写入文件
        try:
            file_path.write_text(full_content, encoding="utf-8")
        except OSError as e:
            raise ObsidianWriteError(
                f"写入文件失败: {file_path}",
                details=str(e),
            )

        logger.info(f"Obsidian 笔记已保存: {file_path.relative_to(self.vault)}")

        # 更新索引
        self._update_index(metadata, file_path, tags)

        return file_path

    def _build_frontmatter(self, metadata: Dict[str, Any], tags: Optional[List[str]] = None) -> str:
        """
        构建 YAML Frontmatter

        Obsidian 规范：
        - tags 使用数组格式: [tag1, tag2]
        - 标签中不应有 # 符号（# 在 Obsidian 中是搜索语法）
        - 所有字符串值使用双引号
        """
        frontmatter_lines = ["---"]

        # title
        title = metadata.get("title", "视频笔记")
        frontmatter_lines.append(f'title: "{self._escape_yaml(title)}"')

        # author
        if metadata.get("author"):
            frontmatter_lines.append(f'author: "{self._escape_yaml(metadata["author"])}"')

        # source URL
        if metadata.get("source_url"):
            frontmatter_lines.append(f"source: {metadata['source_url']}")

        # duration
        if metadata.get("duration"):
            duration = metadata["duration"]
            if isinstance(duration, int):
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = str(duration)
            frontmatter_lines.append(f"duration: {duration_str}")

        # platform
        if metadata.get("source_platform"):
            frontmatter_lines.append(f"platform: {metadata['source_platform']}")

        # date
        frontmatter_lines.append(f"date: {datetime.now().strftime('%Y-%m-%d')}")

        # tags — Obsidian 规范：不带 #，纯字符串数组
        all_tags: List[str] = list(tags) if tags else []
        all_tags.extend(metadata.get("tags", []))
        all_tags.extend(["视频笔记", "VidkNot"])

        if all_tags:
            # 去重保持顺序
            seen = set()
            unique_tags = []
            for t in all_tags:
                t = t.strip().lstrip("#")  # 移除可能的 #
                if t and t not in seen:
                    seen.add(t)
                    unique_tags.append(t)

            # Obsidian 规范：数组格式，带引号
            tags_repr = ", ".join(f'"{t}"' for t in unique_tags)
            frontmatter_lines.append(f"tags: [{tags_repr}]")

        frontmatter_lines.append("---")
        return "\n".join(frontmatter_lines)

    def _generate_filename(self, metadata: Dict[str, Any], add_timestamp: bool = True) -> str:
        """生成文件名"""
        title = metadata.get("title", "视频笔记")
        clean_title = self._sanitize_filename(title)

        if len(clean_title) > 50:
            clean_title = clean_title[:50]

        if add_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d")
            return f"{timestamp}_{clean_title}"
        else:
            return clean_title

    def _sanitize_filename(self, name: str) -> str:
        """
        清理文件名中的特殊字符

        Windows 文件名禁止: < > : " / \\ | ? * 以及控制字符
        """
        forbidden = r'[<>:"/\\|?*\x00-\x1f]'
        name = re.sub(forbidden, "_", name)
        name = name.strip().strip(".")
        name = re.sub(r"\s+", "_", name)
        return name or "视频笔记"

    def _resolve_filename_conflict(self, file_path: Path) -> Path:
        """解决文件名冲突"""
        if not file_path.exists():
            return file_path

        counter = 1
        while file_path.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            file_path = file_path.parent / f"{stem}_{counter}{suffix}"
            counter += 1

        return file_path

    def _escape_yaml(self, text: str) -> str:
        """转义 YAML 特殊字符"""
        text = str(text)
        # 转义双引号、反斜杠、换行
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        text = text.replace("\n", " ")
        text = text.replace("\r", "")
        return text

    def _update_index(
        self,
        metadata: Dict[str, Any],
        file_path: Path,
        tags: Optional[List[str]] = None,
    ):
        """更新 Obsidian 索引文件"""
        if not self.vault.exists():
            return

        index_path = self.vault / "vidknot-index.md"

        title = metadata.get("title", "视频笔记")
        source_url = metadata.get("source_url", "")
        date = datetime.now().strftime("%Y-%m-%d")
        platform = metadata.get("source_platform", "")

        relative_path = file_path.relative_to(self.vault)
        platform_icon = f"[{platform}] " if platform else ""
        index_entry = f"- {platform_icon}[{title}]({relative_path.as_posix()}) | {date}"

        if index_path.exists():
            content = index_path.read_text(encoding="utf-8")
        else:
            content = "# VidkNot 视频笔记索引\n\n## 最近笔记\n\n"

        # 检查是否已存在（按 URL 去重）
        if source_url and f"[{title}]" in content:
            return

        content += index_entry + "\n"
        try:
            index_path.write_text(content, encoding="utf-8")
        except OSError:
            logger.warning(f"索引更新失败（非阻塞）: {index_path}")

    def get_vault_stats(self) -> Dict[str, Any]:
        """获取 Vault 统计信息"""
        if not self.vault.exists():
            return {"exists": False}

        md_files = list(self.vault.rglob("*.md"))
        total_files = len(md_files)
        total_size = sum(f.stat().st_size for f in md_files)

        return {
            "exists": True,
            "vault_path": str(self.vault),
            "total_notes": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }


# -----------------------------------------------------------------------------
# VidkNot - Video Knowledge, Knotted.
# -----------------------------------------------------------------------------
# Copyright (c) 2026 VidkNot Team
# 
# This software is licensed under the MIT License.
# See LICENSE file in the project root for details.
# 
# Repository: https://github.com/suonian/vidknot
# -----------------------------------------------------------------------------

