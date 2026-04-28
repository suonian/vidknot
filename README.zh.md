# VidkNot - Video Knowledge, Knotted

<div align="center">

**Tie your video knowledge together.**

[![PyPI Version](https://img.shields.io/pypi/v/vidknot.svg)](https://pypi.org/project/vidknot/)
[![Python Versions](https://img.shields.io/pypi/pyversions/vidknot.svg)](https://pypi.org/project/vidknot/)
[![License](https://img.shields.io/github/license/suonian/vidknot.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/suonian/vidknot.svg)](https://github.com/suonian/vidknot/stargazers)
[![GitHub Release](https://img.shields.io/github/v/release/suonian/vidknot)](https://github.com/suonian/vidknot/releases)
[![Downloads](https://img.shields.io/pypi/dm/vidknot)](https://pypi.org/project/vidknot/)

</div>

---

## 🌍 Language

| [English](README.en.md) | [中文](README.md) |

---

## 📖 Project Overview

VidkNot is an AI-powered video knowledge extraction and management tool. It downloads videos from major platforms like Douyin, YouTube, and Bilibili, automatically transcribes speech to text, generates structured notes via LLM, and supports syncing notes to multiple knowledge management platforms.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🎬 **Multi-Platform Download** | Support for Douyin, YouTube, Bilibili, and more |
| 🎤 **Cloud Transcription** | High-accuracy speech recognition via SiliconFlow SenseVoice |
| 🤖 **AI Note Generation** | Generate structured notes using LLM |
| 📚 **Multi-Platform Sync** | Notion, Obsidian, Feishu, Yuque, and more |
| 🔧 **Multiple Interfaces** | CLI, MCP Server, and Python API |

---

## 🚀 Quick Start

### Installation

```bash
pip install vidknot
```

### Environment Setup

VidkNot requires the following environment variables. Please configure them in your `.env` file:

```bash
# Required
SILICONFLOW_API_KEY=your_siliconflow_api_key

# Optional - Video Platform Cookies
DOUBIN_COOKIE=your_douyin_cookie
YOUTUBE_COOKIE=your_youtube_cookie

# Optional - Note Publishing Platforms
NOTION_TOKEN=your_notion_token
NOTION_PAGE_ID=your_notion_page_id
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_FOLDER_TOKEN=your_feishu_folder_token
YUQUE_TOKEN=your_yuque_token
YUQUE_REPO=your_yuque_repo
```

### Basic Usage

#### 1. CLI Mode

```bash
# Process a single video
python -m vidknot "https://www.youtube.com/watch?v=example"

# Specify note destination
python -m vidknot "https://v.douyin.com/xxx" --destination notion

# Check environment configuration
python -m vidknot --check-env
```

#### 2. MCP Server Mode

```bash
# Start MCP server
python -m vidknot mcp

# Or use API mode
python -m vidknot api
```

#### 3. Python API

```python
from vidknot import VideoKnowledgePipeline

pipeline = VideoKnowledgePipeline()

# Process video and generate notes
result = pipeline.process(
    video_url="https://www.youtube.com/watch?v=example",
    destination="notion"  # notion, obsidian, feishu, yuque, both, none
)

print(result["notes"])
```

---

## 📁 Project Structure

```
vidknot/
├── src/vidknot/              # Source code
│   ├── core/                 # Core modules
│   │   ├── downloader.py     # Video downloader
│   │   ├── transcriber.py    # Speech transcription
│   │   └── processor.py      # Content processing
│   ├── adapters/             # Platform adapters
│   │   ├── notion_writer.py  # Notion integration
│   │   ├── obsidian_writer.py# Obsidian integration
│   │   ├── feishu_writer.py  # Feishu integration
│   │   └── yuque_writer.py   # Yuque integration
│   └── pipeline/             # Processing pipeline
│       └── video_knowledge_pipeline.py
├── tests/                    # Test files
├── docs/                     # Documentation
├── README.md                 # Chinese documentation
├── README.en.md              # English documentation
├── LICENSE                   # MIT License
└── pyproject.toml           # Project configuration
```

---

## 🔧 Development

### Clone Project

```bash
git clone https://github.com/suonian/vidknot.git
cd vidknot
```

### Install Dev Dependencies

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [INSTALL.md](INSTALL.md) | Detailed installation guide |
| [API_GUIDE.md](API_GUIDE.md) | API usage guide |
| [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | Cookie tutorial |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Dependencies reference |
| [CREDITS.md](CREDITS.md) | Credits and acknowledgments |

---

## 🛡️ Security

- Do not commit `.env` files containing sensitive information
- API Keys and Tokens are used for local configuration only and are never uploaded to any server
- Use environment variables instead of hardcoded credentials

---

## ⚠️ Disclaimer

**By using this project, you agree to the following terms:**

1. **Video Copyright**: This tool is for personal learning, research, and educational purposes only. Please do not use this tool to download or process copyrighted video content without proper authorization from the copyright holder.

2. **Terms of Service**: Please comply with the terms of service of video platforms (Douyin, YouTube, Bilibili, etc.) when using this tool. You agree not to use this tool for any illegal purposes or in violation of platform policies.

3. **Risk Disclaimer**: This tool is provided "as is" without any express or implied warranties. We are not liable for any direct or indirect losses, including but not limited to legal consequences, data loss, or device damage resulting from the use of this tool.

4. **Third-Party Services**: This tool relies on third-party API services (SiliconFlow, OpenAI, etc.). The availability, policies, and terms of these services are the responsibility of their respective providers.

5. **User Responsibility**: Users are responsible for ensuring their use of this tool complies with local laws and regulations.

---

## 📄 License

This project is open source under the [MIT License](LICENSE).

---

## 🙏 Acknowledgments

This project uses the following open-source projects:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloading
- [SiliconFlow](https://siliconflow.cn/) - Speech recognition API
- [OpenAI](https://openai.com/) - LLM API
- [Notion API](https://developers.notion.com/) - Notion integration
- [Obsidian](https://obsidian.md/) - Local knowledge base
- [Feishu SDK](https://github.com/larksuite/oapi-sdk-python) - Feishu API
- [httpx](https://github.com/encode/httpx) - HTTP client

---

## 📬 Contact

- **GitHub Issues**: https://github.com/suonian/vidknot/issues
- **PyPI**: https://pypi.org/project/vidknot/

---

<div align="center">

**Made with ❤️ by VidkNot Team**

</div>
