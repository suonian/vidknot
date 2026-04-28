# VidkNot - Video Knowledge, Knotted

<div align="center">

**Tie your video knowledge together.**
**视频知识，结成一网。**

[![PyPI Version](https://img.shields.io/pypi/v/vidknot.svg)](https://pypi.org/project/vidknot/)
[![Python Versions](https://img.shields.io/pypi/pyversions/vidknot.svg)](https://pypi.org/project/vidknot/)
[![License](https://img.shields.io/github/license/suonian/vidknot.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/suonian/vidknot.svg)](https://github.com/suonian/vidknot/stargazers)

</div>

---

## 📖 项目介绍

VidkNot 是一个基于 AI 的视频知识提取与管理工具。它能够从抖音、YouTube、Bilibili 等主流视频平台下载视频，自动进行语音转文字，并通过 LLM 生成结构化笔记，最终支持将笔记同步到多种知识管理平台。

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🎬 **多平台下载** | 支持抖音、YouTube、Bilibili 等主流视频平台 |
| 🎤 **云端转录** | 基于 SiliconFlow SenseVoice 的高精度语音识别 |
| 🤖 **AI 笔记生成** | 使用大语言模型自动生成结构化笔记 |
| 📚 **多平台同步** | 支持飞书、语雀、Notion、Obsidian 等知识管理平台 |
| 🔧 **多种使用方式** | 提供 CLI 命令行、MCP 服务、Python API 三种接口 |

---

## 🚀 快速开始

### 安装

```bash
pip install vidknot
```

### 环境配置

VidkNot 需要以下环境变量，请在 `.env` 文件中配置：

```bash
# 必需
SILICONFLOW_API_KEY=your_siliconflow_api_key

# 可选 - 视频平台 Cookie（用于需要登录的视频）
DOUBIN_COOKIE=your_douyin_cookie
YOUTUBE_COOKIE=your_youtube_cookie

# 可选 - 笔记发布平台
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_FOLDER_TOKEN=your_feishu_folder_token
YUQUE_TOKEN=your_yuque_token
YUQUE_REPO=your_yuque_repo
NOTION_TOKEN=your_notion_token
NOTION_PAGE_ID=your_notion_page_id
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault
```

### 基本使用

#### 1. 命令行模式

```bash
# 处理单个视频
python -m vidknot "https://www.youtube.com/watch?v=example"

# 指定笔记保存位置
python -m vidknot "https://v.douyin.com/xxx" --destination feishu

# 检查环境配置
python -m vidknot --check-env
```

#### 2. MCP 服务模式

```bash
# 启动 MCP 服务器
python -m vidknot mcp

# 或使用 API 模式
python -m vidknot api
```

#### 3. Python API

```python
from vidknot import VideoKnowledgePipeline

pipeline = VideoKnowledgePipeline()

# 处理视频并生成笔记
result = pipeline.process(
    video_url="https://www.youtube.com/watch?v=example",
    destination="feishu"  # feishu, yuque, notion, obsidian, both, none
)

print(result["notes"])
```

---

## 📁 项目结构

```
vidknot/
├── src/vidknot/              # 源代码
│   ├── core/                 # 核心模块
│   │   ├── downloader.py     # 视频下载器
│   │   ├── transcriber.py    # 语音转录
│   │   └── processor.py      # 内容处理
│   ├── adapters/             # 平台适配器
│   │   ├── feishu_writer.py  # 飞书笔记写入
│   │   ├── yuque_writer.py   # 语雀笔记写入
│   │   ├── notion_writer.py  # Notion 笔记写入
│   │   └── obsidian_writer.py# Obsidian 笔记写入
│   └── pipeline/             # 处理流程
│       └── video_knowledge_pipeline.py
├── tests/                    # 测试文件
├── docs/                     # 文档
├── README.md                 # 项目说明
├── LICENSE                   # MIT 许可证
└── pyproject.toml           # 项目配置
```

---

## 🔧 开发

### 克隆项目

```bash
git clone https://github.com/suonian/vidknot.git
cd vidknot
```

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest tests/
```

---

## 📚 文档

| 文档 | 说明 |
|------|------|
| [INSTALL.md](INSTALL.md) | 详细安装指南 |
| [API_GUIDE.md](API_GUIDE.md) | API 使用指南 |
| [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | Cookie 获取教程 |
| [DEPENDENCIES.md](DEPENDENCIES.md) | 依赖说明 |
| [CREDITS.md](CREDITS.md) | 致谢列表 |

---

## 🛡️ 安全

- 请勿将包含敏感信息的 `.env` 文件提交到版本控制
- API Key 和 Token 仅用于本地配置，不会被上传到任何服务器
- 建议使用环境变量而非硬编码方式配置敏感信息

---

## ⚠️ 免责声明

**使用本项目即表示您理解并同意以下条款：**

1. **视频版权**：本工具仅用于个人学习、研究和教育目的。请勿使用本工具下载或处理受版权保护的视频内容，除非您拥有该视频的合法使用权或已获得版权持有人的明确授权。

2. **服务条款**：使用本工具下载视频时，请遵守各视频平台（如抖音、YouTube、Bilibili）的服务条款。使用本工具即表示您同意不会将其用于任何非法目的或违反平台政策。

3. **风险自担**：本工具按"原样"提供，不提供任何明示或暗示的保证。对于因使用本工具而导致的任何直接或间接损失，包括但不限于法律后果、数据丢失或设备损坏，我们不承担任何责任。

4. **第三方服务**：本工具依赖第三方 API 服务（SiliconFlow、OpenAI 等），这些服务的可用性、政策和条款由各自提供商负责。

5. **用户责任**：用户应确保其使用本工具的行为符合当地法律法规，并承担全部责任。

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。

---

## 🙏 致谢

本项目使用了以下开源项目：

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 视频下载
- [SiliconFlow](https://siliconflow.cn/) - 语音识别 API
- [OpenAI](https://openai.com/) - LLM API
- [Feishu SDK](https://github.com/larksuite/oapi-sdk-python) - 飞书 API
- [httpx](https://github.com/encode/httpx) - HTTP 客户端

---

## 📬 联系方式

- **GitHub Issues**: https://github.com/suonian/vidknot/issues
- **PyPI**: https://pypi.org/project/vidknot/

---

<div align="center">

**Made with ❤️ by VidkNot Team**

</div>
