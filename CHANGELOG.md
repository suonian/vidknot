# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.2] - 2026-08-31

### 市场概述页中文化

### Changed

- **`SKILL.md` 全文中文化**：市场「概述」页直接渲染 SKILL.md 正文，
  此前正文为英文导致用户看到全英文页面；现已全部译为中文
  （使用指引、边界条件、快速开始、接口形态、MCP 用法、配置、
  示例、架构图、文件清单、版本规则、许可证），
  frontmatter description 保持中文不变
- 全量版本位点同步至 `v0.6.2`（pyproject / _version / install.sh /
  SECURITY / issue 模板 / README 双语 / SKILL.md 快速开始安装命令）

## [0.6.1] - 2026-08-31

### 修复时长格式化崩溃 + 展示信息中文化

### Fixed

- **视频时长格式化崩溃** (`core/processor.py`)
  - `_build_prompt` 中 duration 为 float（yt-dlp 返回值）时，
    `f"{hours:02d}"` 抛 `ValueError`，导致 B 站等实转链路在笔记生成阶段失败
  - 修复：先 `int(duration)` 再拆分时/分/秒
- **SECURITY.md 支持版本表过时**：仍标 `v0.3.x Active`，已更新为 `v0.6.x`

### Changed

- **展示信息中文化**
  - GitHub 仓库 About 描述改为中文优先
  - `SKILL.md` frontmatter description 改为中文（市场首页展示）
  - 市场副本首屏 `README.md` 改为中文版
- 全量版本位点同步至 `v0.6.1`（含补齐 `v0.6.0` 缺失的 git tag）

### Added

- **3 个新测试** (`tests/test_processor.py`)：float/int/缺失 duration 格式化
  回归（403 → 406）

## [0.6.0] - 2026-08-31

### 评估满分优化：错误引导 / 稳定性配置 / FFmpeg 兜底 / 大文件拆分

针对 skillhub 评估报告（v0.5.0）逐项优化：错误提示可引导修正、
统一重试与超时配置、FFmpeg 免安装兜底、国内镜像安装、文档边界补齐。

### Added

- **异常 hint 体系** (`utils/exceptions.py`)
  - `VidkNotError(message, details, hint)`，类级 `default_hint` 回退
  - 19 个高频异常内置修正建议；`__str__` 追加 `| 建议: ...`（无 hint 时输出不变）
- **统一重试工具** (`utils/retry.py`)
  - `retry_with_backoff()`：指数退避 + 永久错误（401/403/404）短路，零新增依赖
  - `get_network_config()`：network 配置段安全读取
- **`network:` / `cache:` 配置段** (`config.yaml`)
  - http_timeout / download_timeout / api_timeout / max_retries / backoff_base
  - cache.max_age_days 控制结果缓存过期（`CacheManager.from_config()`）
- **内置 FFmpeg 可选依赖** — `pip install 'vidknot[bundled-ffmpeg]'`
  - imageio-ffmpeg 静态二进制，离线可用；`env_check.get_ffmpeg_path()`
    四级解析（FFMPEG_PATH → which → Windows 常见路径 → imageio-ffmpeg）
  - yt-dlp `ffmpeg_location` 与子进程调用全链路贯通
- **CLI 友好错误** — `run_cli` 顶层捕获 `VidkNotError`，
  输出「❌ 错误 / 🔍 详情 / 💡 建议」并以退出码 1 结束，不再裸 traceback
- **FAQ 错误速查表** (`docs/FAQ.md`) — 错误 → 原因 → 解决，与异常 hint 对齐
- **PLATFORMS.md 增强** — Cookie 依赖列、时长/文件大小约束、付费/DRM 判断标准
- **install.sh 重写** — FFmpeg 自动安装（brew/apt/dnf/yum/pacman）、
  pip 源自动探测（清华镜像）、bundled-ffmpeg 开关
- **新测试 62 个**（341 → 403）：retry / douyin_api / xhs_parser /
  异常 hint / ⚠️ 平台（快手/微博/B站）行为

### Changed

- **大文件拆分**（评估点名）
  - `xiaohongshu.py` 620 → 471 行：解析逻辑抽取到 `core/xhs_parser.py`
  - `douyin.py` 544 → 395 行：第三方 API 客户端抽取到 `core/douyin_api.py`
    （重试改用 `utils.retry`；类上保留薄委托，测试零破坏）
- **资源加固** — 所有下载/转码子进程补 timeout；`tempfile.mktemp` → `mkstemp`
- **`_get_js_runtime_path` 修复** — macOS/Linux 上不再调用 Windows 专属 `where`
- **文档如实修正** — 微信视频号状态由 ✅ 更正为 ⚠️ 预留（代码未实现自动下载）
- 版本号 0.5.0 → 0.6.0（`pyproject.toml` / `_version.py` / SKILL.md / 双 README /
  install.sh / SECURITY.md）

## [0.5.0] - 2026-08-26

### YouTube SABR Bypass + OpenCC 繁简转换 + 审计体系 + Cookie 健康度

合并 feature/youtube-sop-and-audit 分支（Hermes/小云实战沉淀）。

### Added

- **YouTube SABR-only 绕过** (`youtube.py`)
  - `--extractor-args "youtube:player_client=android,web"` 绕过 Chrome SABR 限制
  - 无 Cookie 也能下载 YouTube 音频（Hermes 实测 7 条全部跑通）
  - 新增 `_download_audio_no_cookie()` 和 `_download_audio_direct()`
- **OpenCC 繁简自动转换** (`transcriber.py`)
  - SiliconFlow ASR 输出繁体中文时自动转简体
  - 启发式检测 + 优雅降级（opencc 未安装时跳过）
- **Post-run Audit** (`scripts/post_run_audit.py`)
  - 双重来源机械验证：笔记内容 vs 口播稿原文
  - 检测 LLM  paraphrase/drop/invent 问题
- **Cookie 健康度 Watchdog** (`utils/cookie_health_check.py`)
  - `check_cookie_health()` + `write_health_flag()`
  - 适用：周一早上自动检测，cookie 过期时生成 flag 文件
- **Codex Sample Curator** (`scripts/codex_sample_curator.py`)
  - 六关质量检查（ffprobe duration / file size / ASR chars / 关键词 / 类型覆盖 / ASR 头部）
- **F2 Helper CLI** (`scripts/f2_helper_cli.py`)
  - f2 CLI 封装，Layer 1 备用下载
- **TikHub key 凭证扫描** (`schema.py`)
  - 新增 TIKHUB_API_KEY 模式识别，防止误提交
- **文档**: `references/2026-08-25-HERMES-EXPERIENCE-REPORT.md`
- **15 个新测试** (326 → 341)

### Changed

- `_version.py` 0.4.2 → 0.5.0
- `pyproject.toml` 0.4.2 → 0.5.0

## [0.4.2] - 2026-08-10

### TikHub Layer 3 增强（小云外围硬化 + 小 Q 核心增强）

抖音 fallback 双重增强。小云（Hermes）做了外围工具层，
小 Q 在此基础上做了核心 TikHub API 集成增强。

### Added (Hermes / 小云 feature/douyin-fallback-hardening)

- **`scripts/f2_helper_cli.py`** — f2 CLI 封装 (Layer 1 备用)
- **`src/vidknot/utils/cookie_health_check.py`** — Cookie 健康度 watchdog
  - `check_cookie_health()` + `write_health_flag()`
  - 适用：周一早上自动检测，cookie 过期时生成 flag 文件
- **`scripts/codex_sample_curator.py`** — Codex 六关检查工具
  - ffprobe duration / file size / 转录字符 / 关键词匹配 / 类型覆盖 / ASR 头部
- **`src/vidknot/core/source/schema.py`** — TikHub key 模式识别
- **文献**: `docs/DOUYIN_FALLBACK.md`、`docs/PLATFORMS.md`、`docs/EXPERIENCES.md`
- **23 个新测试** (294 → 326)

### Added (小 Q — TikHub Layer 3 核心增强)

- **`_call_third_party_api`** — 新增 **exponential backoff retry**
  - max_retries=2，指数退避（1s / 2s / 4s）
  - 区分临时错误（429 限流 / 5xx 过载 / 网络超时 → 重试）
  - 区分永久错误（401 鉴权过期 / 403 无权限 / 404 不存在 → 跳过）
- **`_download_with_retry`** — 新建 CDN 直链下载重试
  - max_retries=2（1s / 2s 退避）
  - TikHub / apibyte 返回的视频直链可能来自 CDN 缓存，偶尔瞬断
- **`_parse_api_response`** — 独立的 response path 解析
  - 不再 hard-fail（DownloadError），改为 warn + return None
  - 让主循环继续到下一个 API

### Changed

- 旧 `_call_third_party_api` 方法已删除（无 retry / 无错误分类）
- `_version.py` 0.4.1 → 0.4.2
- `pyproject.toml` 0.4.1 → 0.4.2

### Verified

- 326 tests pass（294 core + 23 Hermes + 9 local fix）
- ruff lint 0 errors
- Zero regression on v0.4.1 全部功能

## [0.4.1] - 2026-08-10

## [Unreleased]

### Added

- **`scripts/codex_sample_curator.py`** — six-gate quality check
  distilled from Codex's three-round feedback (2026-08-10):
  - Gate 1: ffprobe duration ≥ 180 s
  - Gate 2: file size ≥ 1 MB
  - Gate 3: ASR transcript ≥ 1500 chars
  - Gate 4: filename-derived keywords match transcript head/tail (≥ 50%)
  - Gate 5: type coverage awareness (tool test / project retrospective /
    opinion / OPC super-individual)
  - Gate 6: transcript head rejection for known failure patterns
    (single-character spam, "音响设备故障", etc.)
- **`scripts/post_run_audit.py`** — post-run dual-source audit
  (Hermes iron rule 135 enforcement, 2026-08-25):
  - Fetches every docx in a Feishu folder, verifies each "原文"
    / "核心观点" / "原声金句" code-block line appears verbatim in
    the local `fw_corrected.txt` or `sf_corrected.txt`
  - Reports coverage + true_miss with section context
  - Returns exit code 0 iff all docs ≥ 99.0 % coverage with zero
    true_miss (CI-friendly)
  - Reference: Hermes iron rule 113 "笔记内容 = 口播稿原文" + 老大拷问
    "是否确定过笔记内容和口播稿内容一致"
- **`tests/test_post_run_audit.py`** — covers normalization, time-stamp
  stripping, OK / MISMATCH reporting, fw+sf 双源 boundary.

### Changed

- **YouTube platform** — Level 3 (audio download) now uses a 3-tier
  fallback (Hermes实战 2026-08-25, Lin Lili @linliliya 7 videos):
  1. local Cookie file (cookies/youtube.txt)
  2. **`--extractor-args "youtube:player_client=android,web"`** SABR-only
     bypass (no Cookie required, default for yt-dlp 2026+)
  3. Browser Cookie sniff (legacy fallback)
  - Hermes noted: "vt-dlp 2026+ 默认 SABR-only 拒签 web client, 必须
    指定 player_client=android,web 才能在无 Cookie 环境下下载"
- **SiliconFlowASR** — automatic Traditional Chinese → Simplified
  Chinese conversion (OpenCC `t2s`) when the transcript looks
  Traditional:
  - Heuristic: count of Traditional feature characters (經/學/聲/變/對/...)
    > 2× Simplified counterparts
  - Uses `opencc-python-reimplemented` if installed; gracefully skips
    conversion otherwise
  - Hermes noted: "Lin Lili @linliliya 全部 7 条视频都是繁体源, SF 输出
    也含繁体, 不转 LLM 提取会混入繁体"

### Documentation

- `references/2026-08-25-HERMES-EXPERIENCE-REPORT.md` — Hermes heavy-user
  perspective: 实战优势 + 上游改进建议清单
  (companion to this commit)

## [0.4.1] - 2026-08-10

### Standard Agent Skill Compliance

本次为 patch 版本（minor bump），专门为达到**标准 Agent Skill 格式**：
vidknot 现在可被 Claude / Qoder / Cursor / Cline 等 AI agent 一键识别为 skill。

### Added

- **SKILL.md**（根目录）— Agent skill 标准格式入口
  - YAML frontmatter: name / version / description / when-to-use
  - Quick start (1 minute)、4 种接口说明、配置指南、架构图
- **`--demo` 模式** — 零配置烟雾测试
  - `python -m vidknot --demo` 不需要任何 API key
  - 输出 mock 笔记展示完整 pipeline（6 步 + 模拟 Markdown）
  - 适合：agent 首次接触 / README 演示 / 教学场景
- **`.env.minimal`** — 单 API key 最小配置模板
  - 只需 `SILICONFLOW_API_KEY` 即可跑（其他 LLM/存储可选）
- **`scripts/install.sh`** — 一键安装 / 验证脚本
  - 检查 Python / ffmpeg / 安装 / .env 准备 / demo 验证
  - 可通过 `curl ... | bash` 远程运行
  - 支持 `VERSION=` `SKIP_DEMO=` `REPO_URL=` 自定义
- **MCP 工具说明** — 三个工具接口文档
  - `vidknot_extract` / `vidknot_transcribe_only` / `vidknot_status`
- **重点强调 11+ 自媒体平台**（输入源）
  - 不再以"笔记平台"为重点
  - 在所有 manifest（pyproject/README/__init__/__main__）明确"自媒 体平台 vs 笔记平台"分层

### Changed

- 项目定位重写：视频转笔记工具 → 通用研究平台框架，**重点是 11+ 自媒体平台**
- 文档交叉验证（5 个 manifest 文件 + GitHub repo description 全部一致）
- ruff lint 自动修复 4 个 errors（UP015 / W292 / 格式）

### Verified

- 294 tests pass（v0.4.0 全部保留）
- ruff lint 0 errors
- `--demo` 模式零配置可用
- `bash scripts/install.sh` 一键安装验证
- 现有核心模块零改动

### Install

```bash
# 一键安装（验证 demo）
bash scripts/install.sh

# 或手动
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.4.1"
vidknot --demo
```

## [0.4.0] - 2026-08-10

## [0.4.0] - 2026-08-10

### Platform Evolution: 视频转笔记工具 → 通用研究平台框架

本次为大版本（major bump）：vidknot 从"视频转笔记工具"升级为"通用研究平台框架"。
**完全向后兼容** —— 现有 CLI / FastAPI / MCP / Python API、11 个平台插件、ASR + 校正流水线零改动。
v0.3.4 已发布的所有功能在新版本中完全保留。

### Added (Hermes / 小云 feature/general-platform-framework)

#### 核心框架模块
- **core/backend/** — 可插拔存储抽象层
  - `NotePayload` / `StorageResult` / `BackendError` 数据类
  - `BackendStorage` 协议 + `BackendRegistry` 注册表
  - `SqliteBackend` 内置实现（路径由 `VIDKNOT_SQLITE_PATH` env 控制）
  - `build_default_registry()` 工厂函数
- **core/source/** — 订阅源 schema + 凭证注入保护
  - `SourceConfig` / `SourceKind` / `SourcesFile` 数据类
  - `load_sources_file(path)` 解析 YAML / JSON
  - **凭证拒绝机制**：加载时主动拒绝 8 类危险模式（`sessionid=` / `ttwid=` / `odin_ttid=` / `fpk1=` / `fpk2=` / `web_session=` / `AI_PASS=` / `Bearer ` / `sk-` / `SK-`）
- **core/batch/** — 批处理 driver
  - `BatchSummary` / `collect_urls()` / `run_batch()`
- **core/monitor/** — 通用周期调度器
  - `MonitorTask` (base) / `TaskRegistry` / `MonitorScheduler` / `ScheduledRun`
  - async `run_once()` 和 `run_forever(max_ticks=...)` 带上限防止泄漏
  - 错误 per-task 捕获不抛出

#### 文档
- `docs/PRIVACY.md` — 隐私声明（仓库零用户数据 / 零嵌入凭证）
- `docs/BACKENDS.md` — 后端配置（含飞书机器人接法）
- `docs/CONFIG.md` — 全部环境变量参考
- `docs/EXAMPLES.md` — 自定义 backend / task / batch / source 配方
- `examples/sources.yaml.example` — 空模板（零真实账号）

#### Tests
- `tests/test_backend.py` — 9 个测试
- `tests/test_source.py` — 20 个测试（含凭证拒绝反例）
- `tests/test_batch.py` — 8 个测试
- `tests/test_monitor.py` — 10 个测试
- **新增 47 个测试**（247 → 294）

#### Dev Dependencies
- 加 `pytest-asyncio>=0.21`（core/monitor 异步测试需要）

### Privacy & Safety

- 仓库**无 cookies / tokens / API keys**
- 仓库**无账号列表 / 频道列表 / KOL 标识**
- 仓库**无私有文件夹 / 文档 / 聊天 ID**
- `load_sources_file` 主动拒绝凭证模式注入
- 所有示例使用占位 URL

### Verified

- 294 tests pass
- ruff lint 0 errors
- 现有核心模块（platforms / transcriber / processor / downloader / cookie_provider）零改动
- v0.3.4 已发布功能完全保留

## [0.3.4] - 2026-08-10

## [0.3.4] - 2026-08-10

### Changed

- **抖音 Layer 0 (f2 XBogus) 默认改为 disabled**。Hermes agent (上海服务器) 2026-08 实测 f2 0.0.1.7 签名算法已被抖音更新，签名后 API 返回空 body。仍可通过 `enable_f2: true` 手动开启，但默认走 Layer 1+2 路径。文件: `src/vidknot/core/platforms/douyin.py:71`

### Added

- **本地 mp4/mkv/mov 视频自动转码为 mp3** (`process_local_video`)。Hermes agent 实战发现：SiliconFlow 不接受 mp4，错误信息误导为"SSL 握手失败"实际是格式不支持。`__main__.py:328-340` 检测视频格式后调 ffmpeg 抽音频，再传给 SiliconFlow。文件: `src/vidknot/__main__.py`

### Verified

- 247 个单元测试全部通过
- 与 Hermes agent 通过飞书 DM 协作完成（Qoder agent 代号"小 Q"）

## [0.3.3] - 2026-08-10

### Added

- **小红书视频笔记直链下载** (`xiaohongshu.py`)：从 `__INITIAL_STATE__.note.video.media.stream.h264[0].masterUrl` 拿无水印视频直链，多清晰度候选（HD/SD/原链）自动尝试；下载后调用 `dl._extract_audio` 抽音频用于转写。
- **笔记类型探测** (`XiaoHongShuPlatform._probe_note_type`)：从 HTML 提取 `video.media.stream` 字段判断笔记是视频还是图片，避免 yt-dlp 对小红书不可靠的 fallback。
- **平衡括号 JSON 提取器** (`_extract_balanced_json`)：处理 `__INITIAL_STATE__` 多行 JSON 截断问题，修复之前正则非贪婪导致的解析失败。
- **抖音 Layer 0: f2 X-Bogus 集成** (`scripts/f2_helper.py`)：调用 f2 库的 `XBogusManager.str_2_endpoint` 自动签名 POST_DETAIL URL，通过 `.venv-f2` 隔离依赖（结构就绪；f2 0.0.1.7 签名算法已被抖音更新，运行时仍回退 Layer 1）。
- **抖音 Cookie 支持** (`douyin_parser.parse(cookie_str=...)`)：Layer 1 自动从 `cookie_provider` 获取 Cookie 并注入请求头。
- **`COOKIE_GUIDE.md` 能力地图章节**：记录各平台可用性、抖音四层 Fallback 状态、行业级未解难题（如 X-Bogus 纯开源签名）。

### Changed

- TikHub 端点从 `api.tikhub.io`（国际）切换到 `api.tikhub.dev`（大陆直连，无需代理）。
- 小红书 `_extract_from_state` 返回签名扩展为 `(title, image_urls, video_url)`，同时支持图片和视频直链提取。
- 小红书主下载流程重构：`probe → video/image → yt-dlp → XHS-Downloader` 三层回退；探测失败（短链被风控跳首页）时自动让 video 路径接管，避免走错分支。

### Fixed

- 小红书 `_extract_note_id` 正则不支持 `xhslink.cn` 短链 → 修复。
- 小红书 `_download_images` 未保留 `xsec_token`（短链 302 后 404）→ 修复。
- 小红书 httpx.Client 未传入 Cookie → 修复。
- 小红书图片 CDN 正则未覆盖 `sns-webpic-qc.xhscdn.com` → 修复。

### Verified

- 端到端测试：一条小红书视频笔记（4:54 时长 / 7.6 MB）跑完整 pipeline：下载视频 → 抽音频 → SiliconFlow + FasterWhisper 双 ASR 转录 → 双 ASR diff → LLM 校正 → 生成结构化 Markdown 笔记，全部成功。
- 242 个单元测试全部通过。

## [0.3.2] - 2026-08-06

### Added

- **`.env` file support**: `ConfigManager` now loads `dotenv_values` from local
  `.env` files, and `python -m vidknot` calls `load_dotenv` at entry for
  consistent env views across all consumers.
- **`VIDKNOT_ENV_FILE`**: comma-separated shared credential file paths for
  multi-agent hosts (e.g. `~/.hermes/.env`). Generic `OPENAI_*` / `ZHIPUAI_MODEL`
  keys in shared files are stripped to prevent key leakage from host agents.
- **`openai-compatible` provider**: new provider block for generic OpenAI-compatible
  LLM endpoints (MiniMax, DeepSeek, etc.), configurable via `LLM_API_KEY`,
  `LLM_BASE_URL`, and `VIDKNOT_LLM_MODEL`.
- **`LLM_API_KEY` dual mapping**: applies to both `openai` and `openai-compatible`
  providers for backward compatibility.

### Changed

- `OpenAITranscribeASR._get_client()` no longer falls back to `os.getenv("OPENAI_API_KEY")`;
  key resolution is centralized in `ConfigManager._apply_env_overrides()`.
- `yt-dlp` bumped to `>=2026.07`.

### Fixed

- PyPI trove classifier `Natural Language :: Chinese (Simplified)` (was invalid
  `Chinese`, causing all release workflows to fail since v0.2.0).

## [0.3.1] - 2026-08-06

### Added

- CLI `--version` flag.
- `pipeline.run()` now includes `result["structured"]` (with `segments`) in
  structured format mode, so direct pipeline consumers get the same structured
  JSON as the CLI path.

## [0.3.0] - 2026-08-05

### Added

- **Platform plugin architecture**: new `vidknot.core.platforms` package with
  `BasePlatform` / `YtDlpPlatform` abstract classes and a `PlatformRegistry`
  (register/detect/list). Adding a platform now requires only one file + registration.
- **12 registered platforms**: YouTube, Douyin, Bilibili, XiaoHongShu, TikTok,
  Twitter/X, Instagram, Kuaishou, Weibo, Vimeo, WeChat Channels (reserved), and a
  generic yt-dlp fallback.
- **YouTube subtitle-first strategy**: youtube-transcript-api → yt-dlp subtitle
  extraction → audio download + ASR fallback, preserving timestamped segments.
- **Bilibili CC subtitle-first** with fallback to audio + ASR.
- **Douyin**: three-tier fallback migrated into the plugin (parser → browser cookie
  yt-dlp → optional third-party API, incl. self-hosted Evil0ctal via `api_base_url`).
- **XiaoHongShu**: image notes kept, video path added, optional XHS-Downloader fallback.
- **TikTok**: cobalt API integration with yt-dlp fallback.
- **Transcription layer**: new `SubtitleExtractor` (.srt/.vtt parsing) and
  `OpenAITranscribeASR` (Whisper API); `get_transcriber()` supports `openai_whisper`.
- **Structured JSON output**: `result["structured"]` with `segments`, `topics`,
  `entities`, `key_points`, `summary_one_line`, `tags`, and `correction_confidence`
  via `ContentProcessor.extract_structured()`.
- **Batch processing**: `pipeline.run_batch()` (ThreadPoolExecutor, default 3 workers)
  and CLI flags `--batch urls.txt`, `--batch-dir ./videos/`, `--max-workers`.
- **MCP multi-tool server**: `video_to_notes`, `batch_process`, `platform_status`,
  `search_video` (reserved) for both the FastMCP path and the fallback stdio server.
- **Agent bridge**: `get_all_tools_metadata()` and tool-name routing in
  `execute_tool(arguments, tool=...)`.
- **New config block** `platforms`: per-platform subtitle/cookie options plus
  `transcription.strategy` (subtitle_first/siliconflow_only/faster_whisper_only/dual_asr)
  and `transcription.fallback_provider`.
- **New dependency**: `youtube-transcript-api>=0.6.0`.
- **93 new unit tests** (226 total passing) covering platforms, batch processing,
  structured JSON, and MCP/agent tooling.

### Changed

- `VideoDownloader._download_sync()` delegates to `PlatformRegistry.detect(url)`;
  `downloader.py` reduced from ~774 to ~350 lines by moving platform logic into plugins.
- `process_video()` and `pipeline.run()` apply the subtitle-first strategy and skip ASR
  when a platform provides official subtitles.
- `agent_bridge.execute_tool()` calls the pipeline synchronously (fixes incorrect
  `asyncio.run()` usage on sync methods).

## [0.2.1] - 2026-07-30

### Changed

- Cleaned README, installation, API, dependency, and Cookie documentation.
- Updated public installation instructions to use the current GitHub release.
- Raised the optional `feishu-docx` lower bound to `>=0.2.7`.
- Synchronized `.env.example` with documented environment variables.

## [0.2.0] - 2026-07-30

### Added

- **Dual-ASR Cross-Validation Correction Pipeline**: Run two independent ASR systems
  (SiliconFlow SenseVoice + local faster-whisper) and use mmx search + LLM to
  detect and correct transcription errors.
- **New CLI flags**:
  - `--correct` / `--no-correct`: enable or disable dual-ASR correction
  - `--correction-version {v3,v4}`: choose correction strategy (v4 conservative, v3 aggressive)
- **New config block** `faster_whisper`: configure local ASR model/device/compute
- **New config keys** under `settings`: `enable_correction`, `correction_version`
- **New exception** `CorrectionError` in `vidknot.utils.exceptions`
- **New module** `vidknot.core.corrector`: `DualASRCorrector` class and
  `run_correction_pipeline()` factory function
- **New class** `vidknot.core.transcriber.FasterWhisperASR`: local CPU ASR with
  timestamped output (used as the cross-validation source)
- **Comprehensive unit tests**: 133 passing tests covering transcriber, corrector,
  pipeline, and adapters (up from 47)
- **`.gitignore`**: excludes `.vidknot_cache/`, `cookies/`, `.vidknot_tmp*.md`

### Changed

- `vidknot.__main__.process_video` now runs dual-ASR correction by default
  (controlled by `settings.enable_correction`)
- README, INSTALL, DEPENDENCIES, CREDITS docs updated to reflect dual-ASR pipeline

### Notes

- The dual-ASR pipeline falls back to SiliconFlow-only when the local ASR or
  mmx is unavailable; the rest of the flow keeps running.

## [0.1.0] - 2026-04-28

### Added

- **Video Download**: Support for multiple platforms (YouTube, Bilibili, Douyin, etc.) via yt-dlp
- **Cloud Transcription**: SiliconFlow SenseVoice API for fast and accurate speech-to-text
- **LLM Note Generation**: AI-powered structured note generation from video content
- **Multi-Platform Storage**:
  - Feishu (飞书) document integration
  - Yuque (语雀) integration
  - Notion integration
  - Obsidian local vault support
- **Multiple Run Modes**:
  - CLI mode (`python -m vidknot <url>`)
  - MCP mode for AI agent integration
  - FastAPI server mode
- **Cache System**: Intelligent caching to avoid redundant processing
- **Cookie Management**: Support for authenticated video downloads

### Features

- Synchronous processing pipeline for simplicity and reliability
- Environment-based configuration via `.env` files
- Comprehensive error handling and logging
- Cross-platform support (Windows, macOS, Linux)

### Documentation

- README.md - Project overview and quick start
- INSTALL.md - Detailed installation guide
- API_GUIDE.md - API documentation
- COOKIE_GUIDE.md - Browser cookie extraction guide
- DEPENDENCIES.md - Dependency management
- CREDITS.md - Third-party acknowledgments
- DISCLAIMER.md - Legal disclaimer

## [0.0.1] - 2026-04-01

### Added

- Initial project setup
- Basic video download functionality
- Proof of concept for video-to-notes pipeline
