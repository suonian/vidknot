"""标准输入输出编码归一化

跨平台要点：
- Windows 的控制台/管道默认编码是本地代码页（简体中文为 cp936/GBK），
  而 MCP stdio 协议、JSON-RPC、CI 日志都要求 UTF-8。
- Python 的 `sys.stdout` 在管道场景下使用 `locale.getpreferredencoding()`，
  在中文 Windows 上就是 GBK。此时 `json.dumps(..., ensure_ascii=False)`
  写出的是 GBK 字节，MCP 客户端按 UTF-8 解码会得到乱码或解析失败。
- 同理，MCP 客户端送来的 JSON 是 UTF-8 字节，若 stdin 按 GBK 解码，
  请求内容会在进入 json.loads() 之前就被破坏。

因此在 CLI / MCP 入口统一把 stdin / stdout / stderr 切到 UTF-8。
"""

import sys
from typing import Any


def _is_utf8(stream: Any) -> bool:
    encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
    return encoding in ("utf8", "utf_8")


def _reconfigure(stream: Any) -> bool:
    """尝试把一个流切到 UTF-8。返回是否发生了更改。"""
    if stream is None:
        return False
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        # 被替换成了自定义对象（测试里常见），跳过
        return False
    if _is_utf8(stream):
        return False
    try:
        reconfigure(encoding="utf-8", errors="replace")
        return True
    except Exception:
        return False


def ensure_utf8_stdio() -> bool:
    """把 stdin / stdout / stderr 强制切到 UTF-8。

    返回是否至少有一个流被重新配置（便于测试断言）。
    """
    changed = False
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if _reconfigure(stream):
            changed = True
    return changed


def stdio_encodings() -> dict[str, str]:
    """返回三个标准流的当前编码（诊断用）。"""
    return {
        "stdin": (getattr(sys.stdin, "encoding", "") or "unknown").lower(),
        "stdout": (getattr(sys.stdout, "encoding", "") or "unknown").lower(),
        "stderr": (getattr(sys.stderr, "encoding", "") or "unknown").lower(),
    }
