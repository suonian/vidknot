"""
pytest 全局 fixtures

提供测试所需的共享资源和 mock 对象。
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest


# 确保 src/ 路径在 sys.path 中（方便直接 import vidknot）
# 注意：collection 阶段就需要这个路径，所以用 conftest.py 根级别而非 fixture
import sys as _sys
_src_path = str(Path(__file__).parent.parent / "src")
if _src_path not in _sys.path:
    _sys.path.insert(0, _src_path)


# ===== 每个测试前重置 ConfigManager 单例 =====
import pytest


@pytest.fixture(autouse=True)
def reset_config_manager():
    """每个测试前重置 ConfigManager 单例状态，避免测试间污染"""
    from vidknot.utils.config_manager import ConfigManager
    ConfigManager._instance = None
    ConfigManager._initialized = False
    yield
    # 测试后也重置
    ConfigManager._instance = None
    ConfigManager._initialized = False


@pytest.fixture
def temp_dir():
    """提供临时目录，自动清理"""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def mock_env_vars():
    """提供测试用的干净环境变量，自动清理"""
    saved = {}
    test_vars = {
        "OPENAI_API_KEY": "test-openai-key-12345",
        "OPENAI_BASE_URL": "https://api.test.com/v1",
        "ZHIPUAI_API_KEY": "test-zhipu-key-12345",
        "FEISHU_APP_ID": "test-app-id",
        "FEISHU_APP_SECRET": "test-app-secret",
        "OBSIDIAN_VAULT_PATH": "/tmp/test-vault",
    }

    for key, val in test_vars.items():
        saved[key] = os.environ.get(key)
        os.environ[key] = val

    yield test_vars

    # 清理
    for key, val in saved.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


@pytest.fixture
def sample_metadata():
    """提供示例视频元数据"""
    return {
        "title": "Python 异步编程完全指南",
        "uploader": "测试UP主",
        "duration": 3600,
        "url": "https://example.com/video/123",
        "platform": "bilibili",
        "thumbnail": "https://example.com/thumb.jpg",
        "description": "这是一个测试视频",
    }


@pytest.fixture
def sample_transcription():
    """提供示例转录文本"""
    return """
    大家好，欢迎来到本期的技术分享。

    今天我们要聊的是 Python 异步编程。
    异步编程是一种并发编程的方式，它可以让我们在等待 I/O 操作时继续执行其他任务。

    第一个要点是 async 和 await 关键字。
    async 关键字用于定义一个协程函数，而 await 用于等待另一个协程完成。

    第二个要点是 asyncio 模块。
    asyncio 是 Python 标准库提供的异步编程框架，它包含了一系列用于协程调度的工具。

    第三个要点是事件循环。
    事件循环是异步编程的核心，它负责调度和执行协程。

    总结一下，我们学习了 async 和 await 关键字，asyncio 模块的基本用法，
    以及事件循环的工作原理。
    感谢观看，下次再见！
    """
