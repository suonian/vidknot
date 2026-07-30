# VidkNot

视频知识提取与笔记沉淀工具。给 VidkNot 一个视频链接，它会下载音频、转写内容、生成结构化笔记，并保存到 Obsidian、飞书、Notion 或语雀。

[![GitHub Release](https://img.shields.io/github/v/release/suonian/vidknot)](https://github.com/suonian/vidknot/releases)
[![License](https://img.shields.io/github/license/suonian/vidknot.svg)](LICENSE)

| [English](README.md) | 中文 |

## 适合什么场景

- 把课程、访谈、播客、行业分析视频整理成可检索的文字笔记
- 将短视频平台上的有效内容沉淀到个人知识库
- 给 Agent / MCP 客户端提供“视频转笔记”工具能力
- 对转写结果做双 ASR 交叉校验，减少专有名词和口播误识别

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 视频解析与下载 | 支持抖音、Bilibili、YouTube 等 yt-dlp 可处理的平台，并包含抖音短链解析 |
| 双 ASR 转写 | SiliconFlow SenseVoice + 本地 faster-whisper，默认启用交叉校正 |
| 结构化笔记 | 生成主题、要点、细节、引用、术语和完整转写 |
| 多端保存 | 支持 Obsidian、飞书、Notion、语雀，也可只输出 Markdown |
| Agent 集成 | 支持 CLI、FastAPI、MCP 和 Python API |

## 安装

当前 GitHub 版本为 `v0.2.1`。如果需要最新仓库代码，请从 GitHub 安装：

```bash
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.2.1"
```

开发安装：

```bash
git clone https://github.com/suonian/vidknot.git
cd vidknot
pip install -e ".[all]"
```

运行前需要本机安装 FFmpeg：

```bash
ffmpeg -version
```

## 配置

复制 `.env.example` 为 `.env`，至少配置转写和笔记生成所需的 API Key：

```bash
SILICONFLOW_API_KEY=your_siliconflow_api_key
OPENAI_API_KEY=your_openai_compatible_api_key

# 可选：飞书
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_FOLDER_TOKEN=your_feishu_folder_token

# 可选：Obsidian
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault

# 可选：Notion
NOTION_TOKEN=your_notion_token
NOTION_PAGE_ID=your_notion_page_id

# 可选：语雀
YUQUE_TOKEN=your_yuque_token
YUQUE_LOGIN=your_yuque_login

# 可选：抖音 Cookie 文件
VIDKNOT_DOUYIN_COOKIE_FILE=/path/to/douyin-cookies.txt
```

默认配置在 [config.yaml](config.yaml) 中。双 ASR 校正默认开启：

```yaml
settings:
  enable_correction: true
  correction_version: v4
faster_whisper:
  model: small
  device: cpu
  compute_type: int8
```

`v4` 是默认保守策略，只在证据充分时修改；`v3` 更激进，适合愿意承担更高误改风险的场景。

## 使用

命令行：

```bash
# 生成笔记并保存到默认目的地 Obsidian
python -m vidknot "https://v.douyin.com/example/"

# 只输出结果，不保存
python -m vidknot "https://v.douyin.com/example/" --destination none

# 保存到飞书
python -m vidknot "https://v.douyin.com/example/" --destination feishu

# 禁用双 ASR 校正
python -m vidknot "https://v.douyin.com/example/" --no-correct

# 检查运行环境
python -m vidknot --check-env
```

MCP：

```bash
python -m vidknot --mcp
```

FastAPI：

```bash
uvicorn vidknot.api:app --reload
```

Python API：

```python
from vidknot import VideoKnowledgePipeline

pipeline = VideoKnowledgePipeline(destination="none")
result = pipeline.run("https://v.douyin.com/example/")

print(result["markdown"])
```

## 输出内容

VidkNot 默认生成 Markdown 笔记，包含：

- 视频标题、来源链接和处理时间
- 核心主题与摘要
- 结构化要点和细节
- 重要原文引用
- 术语解释
- 带时间戳的完整转写

## 更多文档

| 文档 | 用途 |
| --- | --- |
| [INSTALL.md](INSTALL.md) | 本地安装和环境检查 |
| [API_GUIDE.md](API_GUIDE.md) | 第三方 API 配置 |
| [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | Cookie 获取与安全说明 |
| [DEPENDENCIES.md](DEPENDENCIES.md) | 直接依赖清单 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |

## 安全与合规

- 不要提交 `.env`、Cookie 文件或任何 API Key
- 只处理你有权访问和使用的视频内容
- 遵守视频平台、云服务和笔记平台的服务条款
- 第三方服务的稳定性、价格和权限策略以各平台官方说明为准

## License

[MIT](LICENSE)
