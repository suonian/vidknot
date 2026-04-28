"""
VidkNot - Video Knowledge, Knotted.
Copyright (c) 2026 VidkNot Team

This software is licensed under the MIT License.
See LICENSE file in the project root for details.

https://github.com/suonian/vidknot
"""

"""
VidkNot 智能下载管理器

自动管理多个下载工具，根据 URL 智能选择最优方案
支持: yt-dlp, f2, gallery-dl, lux, you-get
"""

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

import aiohttp
import requests


@dataclass
class DownloadTool:
    """下载工具配置"""
    name: str
    platforms: List[str]  # 支持的平台域名
    install_cmd: str
    update_cmd: str
    version_cmd: str
    download_template: str
    priority: int = 100
    fallback_tools: List[str] = field(default_factory=list)


@dataclass
class DownloadResult:
    """下载结果"""
    success: bool
    file_path: Optional[Path]
    tool_used: str
    message: str
    metadata: Dict = field(default_factory=dict)


class SmartDownloadManager:
    """
    智能视频下载管理器

    自动管理多个下载工具，根据 URL 智能选择最优方案
    """

    TOOLS = {
        'f2': DownloadTool(
            name='f2',
            platforms=['douyin.com', 'iesdouyin.com', 'kuaishou.com'],
            install_cmd='pip install -U f2',
            update_cmd='pip install -U f2',
            version_cmd='f2 --version',
            download_template='f2 {platform} -u "{url}" -o "{output}"',
            priority=10,
            fallback_tools=['yt-dlp', 'you-get']
        ),
        'yt-dlp': DownloadTool(
            name='yt-dlp',
            platforms=[
                'youtube.com', 'youtu.be', 'bilibili.com', 'b23.tv',
                'twitter.com', 'x.com', 'facebook.com', 'vimeo.com',
                'instagram.com', 'reddit.com', 'tiktok.com', 'xiaohongshu.com',
                'weibo.com', 'youtube.com'
            ],
            install_cmd='pip install -U yt-dlp',
            update_cmd='pip install -U yt-dlp',
            version_cmd='yt-dlp --version',
            download_template='yt-dlp -f bestaudio -x --audio-format mp3 "{url}" -o "{output}"',
            priority=20,
            fallback_tools=['you-get', 'gallery-dl']
        ),
        'gallery-dl': DownloadTool(
            name='gallery-dl',
            platforms=['tiktok.com', 'instagram.com', 'reddit.com', 'twitter.com', 'x.com'],
            install_cmd='pip install -U gallery-dl',
            update_cmd='pip install -U gallery-dl',
            version_cmd='gallery-dl --version',
            download_template='gallery-dl "{url}" -D "{output_dir}"',
            priority=30,
            fallback_tools=['yt-dlp']
        ),
        'you-get': DownloadTool(
            name='you-get',
            platforms=['bilibili.com', 'youtube.com', 'youtu.be', 'douyin.com'],
            install_cmd='pip install -U you-get',
            update_cmd='pip install -U you-get',
            version_cmd='you-get --version',
            download_template='you-get -o "{output_dir}" "{url}"',
            priority=50,
            fallback_tools=['yt-dlp']
        ),
    }

    def __init__(self, output_dir: str = './downloads', auto_update: bool = True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.auto_update = auto_update
        self._tool_availability: Dict[str, bool] = {}
        self._tool_versions: Dict[str, str] = {}

    async def initialize(self):
        """初始化: 检测工具并自动更新"""
        await self._detect_tools()
        if self.auto_update:
            await self._update_tools()

    async def _detect_tools(self):
        """检测已安装的工具"""
        for name, tool in self.TOOLS.items():
            try:
                result = subprocess.run(
                    tool.version_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                self._tool_availability[name] = result.returncode == 0
                if result.returncode == 0:
                    version = result.stdout.strip() or result.stderr.strip()
                    self._tool_versions[name] = version[:50]
            except Exception:
                self._tool_availability[name] = False

    async def _update_tools(self):
        """自动更新工具"""
        for name, tool in self.TOOLS.items():
            if not self._tool_availability.get(name):
                try:
                    subprocess.run(
                        tool.install_cmd,
                        shell=True,
                        capture_output=True,
                        timeout=120
                    )
                    self._tool_availability[name] = True
                except Exception:
                    pass

    def detect_platform(self, url: str) -> Tuple[str, List[str]]:
        """检测 URL 所属平台"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()

        platform_tools = []
        for tool_name, tool in self.TOOLS.items():
            for platform in tool.platforms:
                if platform in domain:
                    platform_tools.append((tool_name, tool.priority))
                    break

        platform_tools.sort(key=lambda x: x[1])

        if platform_tools:
            platform = platform_tools[0][0]
            candidates = [t[0] for t in platform_tools]
            return platform, candidates

        return 'unknown', ['yt-dlp', 'gallery-dl', 'you-get']

    def select_best_tool(self, url: str) -> Optional[str]:
        """选择最佳下载工具"""
        platform, candidates = self.detect_platform(url)

        for tool_name in candidates:
            if self._tool_availability.get(tool_name, False):
                return tool_name

        if candidates:
            return candidates[0]

        return None

    async def download(
        self,
        url: str,
        output_name: Optional[str] = None,
    ) -> DownloadResult:
        """智能下载视频"""
        tool_name = self.select_best_tool(url)

        if not tool_name:
            return DownloadResult(
                success=False,
                file_path=None,
                tool_used='none',
                message='没有可用的下载工具'
            )

        result = await self._try_download(url, tool_name, output_name)

        # 回退机制
        if not result.success:
            tool = self.TOOLS.get(tool_name)
            if tool and tool.fallback_tools:
                for fallback in tool.fallback_tools:
                    result = await self._try_download(url, fallback, output_name)
                    if result.success:
                        break

        return result

    async def _try_download(
        self,
        url: str,
        tool_name: str,
        output_name: Optional[str] = None,
    ) -> DownloadResult:
        """使用指定工具下载"""
        tool = self.TOOLS.get(tool_name)
        if not tool:
            return DownloadResult(
                success=False,
                file_path=None,
                tool_used=tool_name,
                message=f'未知工具: {tool_name}'
            )

        if output_name:
            output_path = self.output_dir / f"{output_name}.%(ext)s"
        else:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            output_path = self.output_dir / f"{url_hash}.%(ext)s"

        cmd = tool.download_template.format(
            url=url,
            output=str(output_path),
            output_dir=str(self.output_dir),
            platform=self._get_platform_short(url)
        )

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            )

            if result.returncode == 0:
                downloaded_file = self._find_downloaded_file()
                return DownloadResult(
                    success=True,
                    file_path=downloaded_file,
                    tool_used=tool_name,
                    message='下载成功',
                    metadata={'stdout': result.stdout}
                )
            else:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    tool_used=tool_name,
                    message=f'下载失败: {result.stderr[:200]}'
                )

        except subprocess.TimeoutExpired:
            return DownloadResult(
                success=False,
                file_path=None,
                tool_used=tool_name,
                message='下载超时(5分钟)'
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                file_path=None,
                tool_used=tool_name,
                message=f'下载异常: {str(e)}'
            )

    def _get_platform_short(self, url: str) -> str:
        """获取平台简称"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        if 'douyin' in domain:
            return 'dy'
        elif 'bilibili' in domain or 'b23' in domain:
            return 'bili'
        elif 'youtube' in domain or 'youtu' in domain:
            return 'yt'
        elif 'tiktok' in domain:
            return 'tt'
        elif 'xiaohongshu' in domain:
            return 'xhs'
        return 'auto'

    def _find_downloaded_file(self) -> Optional[Path]:
        """查找最新下载的文件"""
        extensions = ['.mp4', '.mp3', '.webm', '.mkv', '.m4a', '.wav', '.flac']
        files = []
        for ext in extensions:
            files.extend(self.output_dir.glob(f'*{ext}'))

        if not files:
            return None

        return max(files, key=lambda p: p.stat().st_mtime)

    def get_tool_status(self) -> Dict[str, Dict]:
        """获取工具状态"""
        return {
            name: {
                'installed': self._tool_availability.get(name, False),
                'version': self._tool_versions.get(name, 'unknown'),
                'priority': tool.priority,
            }
            for name, tool in self.TOOLS.items()
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

