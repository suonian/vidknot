#!/usr/bin/env bash
#
# fix_audit_p0.sh — VidkNot 审计 P0 修复脚本
#
# 修复内容（对应《多源版本审计与优化方案报告》P0 项）：
#   P0-1 CI ruff 错误 5 个：
#        I001   src/vidknot/utils/__init__.py import 块未排序
#        F401×3 get_ffmpeg_path / retry_with_backoff / get_network_config
#               re-export 未声明 __all__（应补 __all__ 而非删除导入）
#        UP035  src/vidknot/utils/retry.py typing.Callable → collections.abc.Callable
#   P0-2 INSTALL.md 过时版本号 v0.2.1 → v0.6.4（5 处：第 3/42/45/51/65 行）
#
# 特性：幂等（已修复项自动跳过）；执行前要求工作区干净；执行后自动验证。
# 用法：bash scripts/fix_audit_p0.sh
#
set -euo pipefail
cd "$(dirname "$0")/.."

# ---------- 前置检查 ----------
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "✗ 工作区存在未提交改动，请先 commit/stash 后再执行。" >&2
    exit 1
fi

RUFF="$(command -v ruff || true)"
if [ -z "$RUFF" ] && [ -x ".venv/bin/ruff" ]; then
    RUFF=".venv/bin/ruff"
fi
if [ -z "$RUFF" ]; then
    echo "✗ 未找到 ruff，请先激活 .venv 或 pip install ruff。" >&2
    exit 1
fi

# ---------- P0-1a: ruff 自动修复（I001 + UP035） ----------
echo "==> [1/4] ruff 自动修复（I001 import 排序 + UP035 typing.Callable）"
"$RUFF" check src/ --fix --quiet || true

# ---------- P0-1b: __all__ 补齐 re-export（F401×3） ----------
echo "==> [2/4] 为 utils/__init__.py 的 __all__ 补齐 re-export（F401×3）"
python3 - <<'PY'
from pathlib import Path

p = Path("src/vidknot/utils/__init__.py")
text = p.read_text(encoding="utf-8")
changed = False

# get_ffmpeg_path 属于 Env 区块（get_install_guide 之后）
if '"get_ffmpeg_path"' not in text:
    anchor = '    "get_install_guide",\n'
    assert anchor in text, "锚点缺失：get_install_guide"
    text = text.replace(anchor, anchor + '    "get_ffmpeg_path",\n', 1)
    changed = True

# retry_with_backoff / get_network_config 属于新 Retry 区块（Logging 之前）
if '"retry_with_backoff"' not in text:
    anchor = '    # Logging\n'
    assert anchor in text, "锚点缺失：# Logging"
    text = text.replace(
        anchor,
        '    # Retry\n    "retry_with_backoff",\n    "get_network_config",\n' + anchor,
        1,
    )
    changed = True

if changed:
    p.write_text(text, encoding="utf-8")
    print("    __all__ 已补齐：get_ffmpeg_path / retry_with_backoff / get_network_config")
else:
    print("    __all__ 已包含全部 re-export，跳过")
PY

# ---------- P0-2: INSTALL.md 版本号对齐 ----------
echo "==> [3/4] INSTALL.md 版本号 v0.2.1 → v0.6.4"
python3 - <<'PY'
from pathlib import Path

p = Path("INSTALL.md")
text = p.read_text(encoding="utf-8")
count = text.count("v0.2.1")
if count:
    p.write_text(text.replace("v0.2.1", "v0.6.4"), encoding="utf-8")
    print(f"    已替换 {count} 处过时版本号")
else:
    print("    未发现 v0.2.1，跳过")
PY

# ---------- 验证 ----------
echo "==> [4/4] 验证"
"$RUFF" check src/
if grep -q 'v0\.2\.1' INSTALL.md; then
    echo "✗ INSTALL.md 仍残留 v0.2.1" >&2
    exit 1
fi
echo "    ✓ ruff 0 errors + 版本号无残留"

cat <<'EOF'

P0 修复完成。后续步骤（需人工确认后执行）：
  1. 运行测试回归：  .venv/bin/pytest -q          （预期 406 passed）
  2. 审阅改动：      git diff
  3. 提交：          git add -A && git commit -m "fix: ruff F401/I001/UP035 + INSTALL.md 版本号对齐 v0.6.4"
  4. 推送并观察 CI： git push && gh run watch        （Lint with ruff 应转绿）
  5. 重新发布 SkillHub 版本后，同步本地 skills/ 副本（skillhub CLI 会自动刷新 lock）
EOF
