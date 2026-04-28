"""
VidkNot 环境检测模块

自动检测 FFmpeg 和其他依赖是否可用
提供跨平台安装引导
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple, List


def check_ffmpeg() -> Tuple[bool, str]:
    """
    检测 FFmpeg 是否可用

    Returns:
        (是否可用, FFmpeg 路径或错误信息)
    """
    # 1. 检查环境变量
    ffmpeg_path = os.getenv("FFMPEG_PATH")
    if ffmpeg_path and Path(ffmpeg_path).exists():
        return True, ffmpeg_path

    # 2. 尝试直接调用 ffmpeg
    if shutil.which("ffmpeg"):
        return True, shutil.which("ffmpeg")

    # 3. Windows 常见路径
    if sys.platform == "win32":
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for path in common_paths:
            if Path(path).exists():
                return True, path

    return False, "FFmpeg 未找到"


def check_python_version() -> Tuple[bool, str]:
    """检测 Python 版本"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        return True, f"{version.major}.{version.minor}.{version.micro}"
    return False, f"{version.major}.{version.minor}.{version.micro} (需要 3.10+)"


def check_yt_dlp() -> Tuple[bool, str]:
    """检测 yt-dlp 是否安装"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "yt-dlp 未安装"
    except Exception:
        return False, "yt-dlp 未安装"


def check_whisper() -> Tuple[bool, str]:
    """检测 faster-whisper 是否可用"""
    try:
        import faster_whisper
        return True, faster_whisper.__version__
    except ImportError:
        return False, "faster-whisper 未安装"


def check_openai() -> Tuple[bool, str]:
    """检测 OpenAI SDK 是否可用"""
    try:
        import openai
        return True, openai.__version__
    except ImportError:
        return False, "openai SDK 未安装"


def check_all_requirements() -> Tuple[bool, List[str]]:
    """
    检测所有依赖是否满足

    Returns:
        (是否全部满足, 问题消息列表)
    """
    checks = [
        ("Python 版本 (>=3.10)", check_python_version),
        ("FFmpeg", check_ffmpeg),
        ("yt-dlp", check_yt_dlp),
        ("faster-whisper", check_whisper),
    ]

    messages = []
    all_ok = True

    for name, check_fn in checks:
        ok, info = check_fn()
        if ok:
            messages.append(f"[OK] {name}: {info}")
        else:
            messages.append(f"[FAIL] {name}: {info}")
            all_ok = False

    return all_ok, messages


def get_install_guide() -> str:
    """获取 FFmpeg 安装指南"""
    if sys.platform == "win32":
        return """
FFmpeg 安装指南 (Windows):

方式 1: Scoop (推荐)
  scoop install ffmpeg

方式 2: Chocolatey
  choco install ffmpeg

方式 3: Winget
  winget install Gyan.FFmpeg

方式 4: 手动安装
  1. 下载: https://www.gyan.dev/ffmpeg/builds/
  2. 解压到 C:\\ffmpeg
  3. 将 C:\\ffmpeg\\bin 添加到系统 PATH

方式 5: 设置环境变量
  $env:FFMPEG_PATH = "C:\\path\\to\\ffmpeg.exe"
"""
    elif sys.platform == "darwin":
        return """
FFmpeg 安装指南 (macOS):

  brew install ffmpeg
"""
    else:
        return """
FFmpeg 安装指南 (Linux):

  # Debian/Ubuntu
  sudo apt update && sudo apt install ffmpeg

  # Fedora
  sudo dnf install ffmpeg

  # Arch
  sudo pacman -S ffmpeg
"""
