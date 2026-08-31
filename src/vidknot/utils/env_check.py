"""
VidkNot 环境检测模块

自动检测 FFmpeg 和其他依赖是否可用
提供跨平台安装引导

FFmpeg 解析优先级（get_ffmpeg_path）：
1. FFMPEG_PATH 环境变量
2. PATH 中的 ffmpeg
3. Windows 常见安装路径
4. imageio-ffmpeg 内置静态二进制（pip install 'vidknot[bundled-ffmpeg]'）
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_ffmpeg_path() -> str | None:
    """解析可用的 FFmpeg 二进制路径，全部不可用时返回 None。

    调用方（下载器、yt-dlp ffmpeg_location、音频转码）应统一使用本函数，
    而不是硬编码 "ffmpeg"，以支持 FFMPEG_PATH 与内置静态版本。
    """
    # 1. 环境变量显式指定
    ffmpeg_path = os.getenv("FFMPEG_PATH")
    if ffmpeg_path and Path(ffmpeg_path).exists():
        return ffmpeg_path

    # 2. PATH 查找
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 3. Windows 常见路径
    if sys.platform == "win32":
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for path in common_paths:
            if Path(path).exists():
                return path

    # 4. imageio-ffmpeg 内置静态二进制（可选依赖，离线可用）
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return bundled
    except Exception:
        pass

    return None


def check_ffmpeg() -> tuple[bool, str]:
    """
    检测 FFmpeg 是否可用

    Returns:
        (是否可用, FFmpeg 路径或错误信息)
    """
    path = get_ffmpeg_path()
    if path:
        return True, path
    return False, "FFmpeg 未找到"


def check_python_version() -> tuple[bool, str]:
    """检测 Python 版本"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        return True, f"{version.major}.{version.minor}.{version.micro}"
    return False, f"{version.major}.{version.minor}.{version.micro} (需要 3.10+)"


def check_yt_dlp() -> tuple[bool, str]:
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


def check_whisper() -> tuple[bool, str]:
    """检测 faster-whisper 是否可用"""
    try:
        import faster_whisper
        return True, faster_whisper.__version__
    except ImportError:
        return False, "faster-whisper 未安装"


def check_openai() -> tuple[bool, str]:
    """检测 OpenAI SDK 是否可用"""
    try:
        import openai
        return True, openai.__version__
    except ImportError:
        return False, "openai SDK 未安装"


def check_all_requirements() -> tuple[bool, list[str]]:
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
    bundled_option = """
通用方式 (任意平台, 无需系统权限):
  pip install 'vidknot[bundled-ffmpeg]'
  （使用 imageio-ffmpeg 内置静态二进制，离线可用，无需管理员权限）
"""
    if sys.platform == "win32":
        return bundled_option + """
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
        return bundled_option + """
FFmpeg 安装指南 (macOS):

  brew install ffmpeg
"""
    else:
        return bundled_option + """
FFmpeg 安装指南 (Linux):

  # Debian/Ubuntu
  sudo apt update && sudo apt install ffmpeg

  # Fedora
  sudo dnf install ffmpeg

  # Arch
  sudo pacman -S ffmpeg
"""
