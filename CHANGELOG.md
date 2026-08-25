# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
