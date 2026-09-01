# PR: 审计 P0 — 恢复 CI 绿灯 + 文档版本对齐

## Summary

多源版本审计（本地 / GitHub / SkillHub 三端）发现的 P0 问题修复：

- **fix(lint)**：`src/vidknot/utils/__init__.py` 为 `get_ffmpeg_path` / `retry_with_backoff` / `get_network_config` 补齐 `__all__` re-export（F401×3）；`src/vidknot/utils/retry.py` 将 `typing.Callable` 迁移至 `collections.abc.Callable`（UP035）；修复 import 块排序（I001）
- **docs(install)**：`INSTALL.md` 中 5 处 `v0.2.1` 更新为 `v0.6.4`（第 3/42/45/51/65 行）

## Root Cause

- CI `Lint with ruff` 步骤因 5 个 lint 错误失败（run 33455743908），3.10/3.11 因 `fail-fast` 被取消，Build job 被跳过，main 分支持续红灯
- `INSTALL.md` 自 v0.2.1 之后未随版本发布流程同步更新版本号

## Changes

| 文件 | 改动 | 规则 |
|---|---|---|
| `src/vidknot/utils/__init__.py` | `__all__` 补 3 个 re-export | F401 |
| `src/vidknot/utils/retry.py` | `Callable` 导入路径迁移 | UP035 |
| `src/vidknot/utils/__init__.py` | import 块排序 | I001 |
| `INSTALL.md` | 5 处版本号 v0.2.1 → v0.6.4 | — |

## Verification

- [ ] `ruff check src/` → 0 errors
- [ ] `.venv/bin/pytest -q` → 406 passed
- [ ] CI 全矩阵转绿（Python 3.10 / 3.11 / 3.12）
- [ ] Build job 恢复执行（dist 产物正常生成）

## SkillHub 评分影响

| 子项 | 当前 | 预期 | 依据 |
|---|---|---|---|
| effectiveness.usability | 4.5 | 4.9+ | 消除「INSTALL.md 版本号过时」扣分点 |
| effectiveness.accuracy | 4.6 | 4.9+ | 安装文档与实际 Release 一致 |

## Not in this PR（后续独立处理）

- LICENSE 纯净化（GitHub 识别为 NOASSERTION → 恢复 MIT 识别）
- dependabot #5 / #6 / #7 合并（actions 大版本升级需单独验证）
- SKILL.md「3 分钟入门」摘要（progressive 4.5 → 5.0）
- 错误提示本地化（errorHandling 4.5 → 5.0）
