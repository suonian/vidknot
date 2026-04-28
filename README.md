# VidkNot - Video Knowledge, Knotted

<div align="center">

**Tie your video knowledge together.**
**视频知识，结成一网。**

[![PyPI Version](https://img.shields.io/pypi/v/vidknot.svg)](https://pypi.org/project/vidknot/)
[![Python Versions](https://img.shields.io/pypi/pyversions/vidknot.svg)](https://pypi.org/project/vidknot/)
[![License](https://img.shields.io/github/license/suonian/vidknot.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/suonian/vidknot.svg)](https://github.com/suonian/vidknot/stargazers)
[![GitHub Release](https://img.shields.io/github/v/release/suonian/vidknot)](https://github.com/suonian/vidknot/releases)
[![Downloads](https://img.shields.io/pypi/dm/vidknot)](https://pypi.org/project/vidknot/)

</div>

---

## 🌍 Language | 语言

| [English](README.en.md) | [中文](README.md) |

---

## 📖 项目介绍 | Project Overview

VidkNot 是一个基于 AI 的视频知识提取与管理工具。它能够从抖音、YouTube、Bilibili 等主流视频平台下载视频，自动进行语音转文字，并通过 LLM 生成结构化笔记，最终支持将笔记同步到多种知识管理平台。

VidkNot is an AI-powered video knowledge extraction and management tool. It downloads videos from major platforms like Douyin, YouTube, and Bilibili, automatically transcribes speech to text, generates structured notes via LLM, and supports syncing notes to multiple knowledge management platforms.

---

## ✨ 核心功能 | Key Features

| Feature | Description | 功能 | 说明 |
|---------|-------------|------|------|
| 🎬 **Multi-Platform Download** | Support for Douyin, YouTube, Bilibili, and more | 🎬 **多平台下载** | 支持抖音、YouTube、Bilibili 等主流视频平台 |
| 🎤 **Cloud Transcription** | High-accuracy speech recognition via SiliconFlow SenseVoice | 🎤 **云端转录** | 基于 SiliconFlow SenseVoice 的高精度语音识别 |
| 🤖 **AI Note Generation** | Generate structured notes using LLM | 🤖 **AI 笔记生成** | 使用大语言模型自动生成结构化笔记 |
| 📚 **Multi-Platform Sync** | Notion, Obsidian, Feishu, Yuque, and more | 📚 **多平台同步** | 支持 Notion、Obsidian、飞书、语雀等知识管理平台 |
| 🔧 **Multiple Interfaces** | CLI, MCP Server, and Python API | 🔧 **多种使用方式** | 提供 CLI 命令行、MCP 服务、Python API 三种接口 |

---

## 🚀 快速开始 | Quick Start

### 安装 | Installation

```bash
pip install vidknot
```

### 环境配置 | Environment Setup

VidkNot requires the following environment variables. Please configure them in your `.env` file:

```bash
# Required | 必需
SILICONFLOW_API_KEY=your_siliconflow_api_key

# Optional - Video Platform Cookies | 可选 - 视频平台 Cookie
DOUBIN_COOKIE=your_douyin_cookie
YOUTUBE_COOKIE=your_youtube_cookie

# Optional - Note Publishing Platforms | 可选 - 笔记发布平台
NOTION_TOKEN=your_notion_token
NOTION_PAGE_ID=your_notion_page_id
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_FOLDER_TOKEN=your_feishu_folder_token
YUQUE_TOKEN=your_yuque_token
YUQUE_REPO=your_yuque_repo
```

### 基本使用 | Basic Usage

#### 1. CLI Mode | 命令行模式

```bash
# Process a single video | 处理单个视频
python -m vidknot "https://www.youtube.com/watch?v=example"

# Specify note destination | 指定笔记保存位置
python -m vidknot "https://v.douyin.com/xxx" --destination notion

# Check environment configuration | 检查环境配置
python -m vidknot --check-env
```

#### 2. MCP Server Mode | MCP 服务模式

```bash
# Start MCP server | 启动 MCP 服务器
python -m vidknot mcp

# Or use API mode | 或使用 API 模式
python -m vidknot api
```

#### 3. Python API

```python
from vidknot import VideoKnowledgePipeline

pipeline = VideoKnowledgePipeline()

# Process video and generate notes | 处理视频并生成笔记
result = pipeline.process(
    video_url="https://www.youtube.com/watch?v=example",
    destination="notion"  # notion, obsidian, feishu, yuque, both, none
)

print(result["notes"])
```

---

## 📁 项目结构 | Project Structure

```
vidknot/
├── src/vidknot/              # Source code | 源代码
│   ├── core/                 # Core modules | 核心模块
│   │   ├── downloader.py     # Video downloader | 视频下载器
│   │   ├── transcriber.py    # Speech transcription | 语音转录
│   │   └── processor.py      # Content processing | 内容处理
│   ├── adapters/             # Platform adapters | 平台适配器
│   │   ├── notion_writer.py  # Notion integration | Notion 集成
│   │   ├── obsidian_writer.py# Obsidian integration | Obsidian 集成
│   │   ├── feishu_writer.py  # Feishu integration | 飞书集成
│   │   └── yuque_writer.py   # Yuque integration | 语雀集成
│   └── pipeline/             # Processing pipeline | 处理流程
│       └── video_knowledge_pipeline.py
├── tests/                    # Test files | 测试文件
├── docs/                     # Documentation | 文档
├── README.md                 # Chinese documentation | 中文文档
├── README.en.md              # English documentation | 英文文档
├── LICENSE                   # MIT License | MIT 许可证
└── pyproject.toml           # Project configuration | 项目配置
```

---

## 🔧 开发 | Development

### Clone Project | 克隆项目

```bash
git clone https://github.com/suonian/vidknot.git
cd vidknot
```

### Install Dev Dependencies | 安装开发依赖

```bash
pip install -e ".[dev]"
```

### Run Tests | 运行测试

```bash
pytest tests/
```

---

## 📚 文档 | Documentation

| Document | Description | 文档 | 说明 |
|----------|-------------|------|------|
| [INSTALL.md](INSTALL.md) | Installation guide | [INSTALL.md](INSTALL.md) | 详细安装指南 |
| [API_GUIDE.md](API_GUIDE.md) | API usage guide | [API_GUIDE.md](API_GUIDE.md) | API 使用指南 |
| [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | Cookie tutorial | [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | Cookie 获取教程 |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Dependencies | [DEPENDENCIES.md](DEPENDENCIES.md) | 依赖说明 |
| [CREDITS.md](CREDITS.md) | Credits | [CREDITS.md](CREDITS.md) | 致谢列表 |

---

## 🛡️ 安全 | Security

- Do not commit `.env` files containing sensitive information | 请勿将包含敏感信息的 `.env` 文件提交到版本控制
- API Keys and Tokens are used for local configuration only | API Key 和 Token 仅用于本地配置，不会被上传到任何服务器
- Use environment variables instead of hardcoded credentials | 建议使用环境变量而非硬编码方式配置敏感信息

---

## ⚠️ 免责声明 | Disclaimer

**使用本项目即表示您理解并同意以下条款：**

**By using this project, you agree to the following terms:**

1. **视频版权 | Video Copyright**：本工具仅用于个人学习、研究和教育目的。请勿使用本工具下载或处理受版权保护的视频内容，除非您拥有该视频的合法使用权或已获得版权持有人的明确授权。| This tool is for personal learning, research, and educational purposes only. Please do not use this tool to download or process copyrighted video content without proper authorization.

2. **服务条款 | Terms of Service**：使用本工具下载视频时，请遵守各视频平台的服务条款。| Please comply with the terms of service of video platforms when using this tool.

3. **风险自担 | Risk Disclaimer**：本工具按"原样"提供，不提供任何明示或暗示的保证。| This tool is provided "as is" without any warranties.

4. **第三方服务 | Third-Party Services**：本工具依赖第三方 API 服务（SiliconFlow、OpenAI 等），这些服务的可用性、政策和条款由各自提供商负责。| This tool relies on third-party API services (SiliconFlow, OpenAI, etc.).

5. **用户责任 | User Responsibility**：用户应确保其使用本工具的行为符合当地法律法规。| Users are responsible for ensuring their use of this tool complies with local laws and regulations.

---

## 📄 许可证 | License

本项目采用 [MIT License](LICENSE) 开源。| This project is open source under the [MIT License](LICENSE).

---

## 🙏 致谢 | Acknowledgments

本项目使用了以下开源项目：

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloading | 视频下载
- [SiliconFlow](https://siliconflow.cn/) - Speech recognition API | 语音识别 API
- [OpenAI](https://openai.com/) - LLM API
- [Notion API](https://developers.notion.com/) - Notion integration | Notion 集成
- [Obsidian](https://obsidian.md/) - Local knowledge base | 本地知识库
- [Feishu SDK](https://github.com/larksuite/oapi-sdk-python) - Feishu API | 飞书 API
- [httpx](https://github.com/encode/httpx) - HTTP client | HTTP 客户端

---

## 📬 联系方式 | Contact

- **GitHub Issues**: https://github.com/suonian/vidknot/issues
- **PyPI**: https://pypi.org/project/vidknot/

---

<div align="center">

**Made with ❤️ by VidkNot Team**

</div>
