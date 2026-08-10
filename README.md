# VidkNot

VidkNot is a **general research platform framework** (v0.4.0) that extracts knowledge from **11+ self-media platforms** (YouTube, Bilibili, Douyin, Xiaohongshu, Kuaishou, TikTok, Twitter/X, Instagram, WeChat Channels, Weibo, Vimeo). It downloads audio, transcribes speech via dual-ASR cross-validation, generates Markdown notes, and saves them to Obsidian, Feishu, Notion, or Yuque. v0.4.0 adds pluggable storage backends, an async periodic scheduler, a batch runner, and a credential-leak-proof subscription source loader.

[![GitHub Release](https://img.shields.io/github/v/release/suonian/vidknot)](https://github.com/suonian/vidknot/releases)
[![License](https://img.shields.io/github/license/suonian/vidknot.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-294%20passed-brightgreen)](https://github.com/suonian/vidknot/actions)

| English | [中文](README.zh.md) |

## Use Cases

- Convert courses, interviews, podcasts, and industry videos into searchable notes
- Save useful short-video content into a personal knowledge base
- Expose video-to-note capability to agents through MCP
- Reduce transcription mistakes with dual-ASR cross-validation

## Supported Platforms

| Platform | Type | Status |
| --- | --- | --- |
| YouTube, Vimeo | Long-form video | ✅ Stable via yt-dlp |
| Bilibili | Long-form video | ✅ Stable with subtitle/danmaku |
| Douyin (TikTok China) | Short video | ✅ Cookie-based direct fetch + 4-layer fallback |
| TikTok (International) | Short video | ✅ Stable via yt-dlp |
| Twitter / X | Short video | ✅ Stable via yt-dlp |
| Instagram (Reels) | Short video | ✅ Stable via yt-dlp |
| WeChat Channels (视频号) | Short video | ✅ |
| Xiaohongshu (Image notes) | Image gallery | ✅ 4 bugs fixed in v0.3.3 (still active in v0.4.0) |
| Xiaohongshu (Video notes) | Short video | ✅ Direct-link extraction from `__INITIAL_STATE__` |
| Kuaishou, Weibo | Short video | ⚠️ Framework ready, depends on yt-dlp support |
| Any yt-dlp-supported site | Mixed | ✅ GenericPlatform fallback |

See [COOKIE_GUIDE.md](COOKIE_GUIDE.md) for the full capability matrix.

## Capabilities

| Capability | Description |
| --- | --- |
| Video parsing and download | 11 platforms + generic yt-dlp fallback, 4-layer fallback for Douyin |
| Dual-ASR transcription | SiliconFlow SenseVoice + local faster-whisper correction, enabled by default |
| Structured notes | Generates topic, summary, key points, details, quotes, terms, and full transcript |
| Storage targets | Obsidian, Feishu, Notion, Yuque, or Markdown-only output |
| Agent integration | CLI, FastAPI, MCP, and Python API |

## Installation

The current GitHub release is `v0.4.0`. Install from GitHub:

```bash
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.4.0"
```

For development:

```bash
git clone https://github.com/suonian/vidknot.git
cd vidknot
pip install -e ".[all]"
```

FFmpeg must be available locally:

```bash
ffmpeg -version
```

## Configuration

Copy `.env.example` to `.env` and configure the keys you need:

```bash
SILICONFLOW_API_KEY=your_siliconflow_api_key
OPENAI_API_KEY=your_openai_compatible_api_key

# Optional: Feishu
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_FOLDER_TOKEN=your_feishu_folder_token

# Optional: Obsidian
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault

# Optional: Notion
NOTION_TOKEN=your_notion_token
NOTION_PAGE_ID=your_notion_page_id

# Optional: Yuque
YUQUE_TOKEN=your_yuque_token
YUQUE_LOGIN=your_yuque_login

# Optional: Douyin cookie file
VIDKNOT_DOUYIN_COOKIE_FILE=/path/to/douyin-cookies.txt
```

Default settings live in [config.yaml](config.yaml). Dual-ASR correction is enabled by default:

```yaml
settings:
  enable_correction: true
  correction_version: v4
faster_whisper:
  model: small
  device: cpu
  compute_type: int8
```

`v4` is the conservative default. `v3` makes broader corrections and carries a higher risk of changing valid text.

## Usage

CLI:

```bash
# Generate a note and save to the default destination, Obsidian
python -m vidknot "https://v.douyin.com/example/"

# Print output only
python -m vidknot "https://v.douyin.com/example/" --destination none

# Save to Feishu
python -m vidknot "https://v.douyin.com/example/" --destination feishu

# Disable dual-ASR correction
python -m vidknot "https://v.douyin.com/example/" --no-correct

# Check local requirements
python -m vidknot --check-env
```

MCP:

```bash
python -m vidknot --mcp
```

FastAPI:

```bash
uvicorn vidknot.api:app --reload
```

Python API:

```python
from vidknot import VideoKnowledgePipeline

pipeline = VideoKnowledgePipeline(destination="none")
result = pipeline.run("https://v.douyin.com/example/")

print(result["markdown"])
```

## Output

VidkNot writes Markdown notes with:

- Video title, source URL, and processing metadata
- Topic and summary
- Structured key points and details
- Important quotes
- Terms and explanations
- Timestamped transcript

## Documentation

| Document | Purpose |
| --- | --- |
| [INSTALL.md](INSTALL.md) | Local installation and environment checks |
| [API_GUIDE.md](API_GUIDE.md) | Third-party API configuration |
| [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | Cookie setup and security |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Direct dependencies |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## Security And Compliance

- Do not commit `.env`, cookie files, or API keys
- Only process video content you are allowed to access and use
- Follow the terms of video platforms, cloud services, and note platforms
- Third-party service availability, pricing, and permissions are controlled by their providers

## License

[MIT](LICENSE)
