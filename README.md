# VidkNot

VidkNot turns video links into structured knowledge notes. It downloads audio, transcribes speech, generates Markdown notes, and saves them to Obsidian, Feishu, Notion, or Yuque.

[![GitHub Release](https://img.shields.io/github/v/release/suonian/vidknot)](https://github.com/suonian/vidknot/releases)
[![License](https://img.shields.io/github/license/suonian/vidknot.svg)](LICENSE)

| English | [中文](README.zh.md) |

## Use Cases

- Convert courses, interviews, podcasts, and industry videos into searchable notes
- Save useful short-video content into a personal knowledge base
- Expose video-to-note capability to agents through MCP
- Reduce transcription mistakes with dual-ASR cross-validation

## Capabilities

| Capability | Description |
| --- | --- |
| Video parsing and download | Supports Douyin, Bilibili, YouTube, and other yt-dlp-compatible platforms |
| Dual-ASR transcription | SiliconFlow SenseVoice + local faster-whisper correction, enabled by default |
| Structured notes | Generates topic, summary, key points, details, quotes, terms, and full transcript |
| Storage targets | Obsidian, Feishu, Notion, Yuque, or Markdown-only output |
| Agent integration | CLI, FastAPI, MCP, and Python API |

## Installation

The current GitHub release is `v0.2.1`. Install this repository version from GitHub:

```bash
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.2.1"
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
