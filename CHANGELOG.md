# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
