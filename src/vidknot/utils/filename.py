"""文件名跨平台安全处理

Windows 除了禁用字符 `< > : " / \\ | ? *` 和控制字符之外，还保留了一批
「设备名」：CON / PRN / AUX / NUL / COM1-9 / LPT1-9。

保留名的判定看的是**第一个点之前**的部分，且带任意扩展名仍然保留——
`CON.md`、`CON.txt` 依旧指向控制台设备。在 Windows 上写 `CON.md` 时：
- 内容会被写进控制台，文件根本没生成；
- 删除时报 PermissionError（拒绝访问）。

macOS/Linux 不存在这些限制，所以这类问题只会在 Windows 上暴露。
"""

import re

#: Windows 保留设备名（不区分大小写）
WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

#: Windows 文件名禁用字符 + 控制字符
FORBIDDEN_CHARS_PATTERN = r'[<>:"/\\|?*\x00-\x1f]'


def is_windows_reserved_name(name: str) -> bool:
    """判断文件名是否是 Windows 保留设备名。

    判定依据是第一个 "." 之前的主体（与 Windows 的实际规则一致），
    并忽略首尾空格与结尾的点（Windows 也会忽略）。
    """
    if not name:
        return False
    base = name.split(".")[0].strip().rstrip(" ").rstrip(".").upper()
    return base in WINDOWS_RESERVED_NAMES


def escape_windows_reserved_name(name: str, prefix: str = "_") -> str:
    """若文件名命中 Windows 保留设备名，加前缀规避。"""
    if is_windows_reserved_name(name):
        return f"{prefix}{name}"
    return name


def sanitize_filename(
    name: str,
    *,
    forbidden_pattern: str = FORBIDDEN_CHARS_PATTERN,
    fallback: str = "note",
    whitespace_to_underscore: bool = True,
) -> str:
    """通用文件名清理：去禁用字符 + 规避保留设备名。

    Args:
        name: 原始文件名（不含扩展名）
        forbidden_pattern: 禁用字符正则
        fallback: 清理后为空时使用的兜底名
        whitespace_to_underscore: 是否把空白折叠成下划线
    """
    cleaned = re.sub(forbidden_pattern, "_", name)
    cleaned = cleaned.strip().strip(".")
    if whitespace_to_underscore:
        cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned or fallback
    return escape_windows_reserved_name(cleaned)
