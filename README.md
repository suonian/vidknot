# VidkNot

视频知识提取与研究平台（v0.6.0 通用研究平台框架）。从 **11+ 自媒体平台**（YouTube、B 站、抖音、小红书、快手、TikTok、Twitter/X、Instagram、微信视频号、微博、Vimeo）提取视频笔记：下载音频、双 ASR 交叉校验、生成结构化笔记，保存到 Obsidian、飞书、Notion、语雀。v0.4.0 新增可插拔存储后端、异步周期调度器、批处理 driver 和凭证注入保护的订阅源加载器；v0.5.0 新增标准 Agent Skill 合规（SKILL.md + `--demo` 模式 + `scripts/install.sh`）；v0.6.0 新增统一重试/超时配置、内置 FFmpeg 可选依赖（`[bundled-ffmpeg]`）、异常修正建议（hint）与 CLI 友好错误、国内镜像安装支持。

[![GitHub Release](https://img.shields.io/github/v/release/suonian/vidknot)](https://github.com/suonian/vidknot/releases)
[![License](https://img.shields.io/github/license/suonian/vidknot.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-403%20passed-brightgreen)](https://github.com/suonian/vidknot/actions)

| 中文 | [English](README.en.md) |

## 适合什么场景

- 把课程、访谈、播客、行业分析视频整理成可检索的文字笔记
- 将短视频平台上的有效内容沉淀到个人知识库
- 给 Agent / MCP 客户端提供“视频转笔记”工具能力
- 对转写结果做双 ASR 交叉校验，减少专有名词和口播误识别

## 支持的平台

| 平台 | 类型 | 状态 |
| --- | --- | --- |
| YouTube、Vimeo | 长视频 | ✅ yt-dlp 成熟路线 |
| B 站 | 长视频 | ✅ 字幕/弹幕均支持 |
| 抖音 | 短视频 | ✅ Cookie 直采 + 四层 fallback |
| TikTok | 短视频 | ✅ yt-dlp 稳定支持 |
| Twitter / X | 短视频 | ✅ yt-dlp 稳定支持 |
| Instagram | Reels | ✅ yt-dlp 稳定支持 |
| 微信视频号 | 短视频 | ⚠️ 预留接口（微信封闭生态，需抓包工具导出后走本地批处理） |
| 小红书（图片笔记） | 图集 | ✅ v0.3.3 修复 4 个 Bug（v0.6.0 仍生效）|
| 小红书（视频笔记） | 短视频 | ✅ 从 `__INITIAL_STATE__` 拿无水印直链 |
| 快手、微博 | 短视频 | ⚠️ 框架已就位，依赖 yt-dlp |
| 任何 yt-dlp 支持的站点 | 混合 | ✅ GenericPlatform 兜底 |

完整能力地图（含各平台 Cookie 依赖、时长约束、付费内容判断标准）见
[docs/PLATFORMS.md](docs/PLATFORMS.md)。

## 核心能力

| 能力 | 说明 |
| --- | --- |
| 视频解析与下载 | 11 个平台 + yt-dlp 兜底，抖音四层 fallback |
| 双 ASR 转写 | SiliconFlow SenseVoice + 本地 faster-whisper，默认启用交叉校正 |
| 结构化笔记 | 生成主题、要点、细节、引用、术语和完整转写 |
| 多端保存 | 支持 Obsidian、飞书、Notion、语雀，也可只输出 Markdown |
| Agent 集成 | 支持 CLI、FastAPI、MCP 和 Python API |

## 安装

> ️ **前置依赖**：运行前必须有 FFmpeg，否则所有平台都会失败。
>
> macOS: `brew install ffmpeg` | Ubuntu: `sudo apt install ffmpeg` | Windows: `winget install Gyan.FFmpeg`
>
> **不想装系统 FFmpeg？** 使用内置静态版本（wheel 自带二进制，离线可用）：
> `pip install "vidknot[bundled-ffmpeg] @ git+https://github.com/suonian/vidknot.git@v0.6.0"`
>
> 环境自检：`python -m vidknot --check-env`（会给出缺失项的安装命令）

当前 GitHub 版本为 `v0.6.0`。从 GitHub 安装：

```bash
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.0"
```

> 🇨🇳 **大陆网络提示**：如访问 GitHub 缓慢，可给 pip 指定国内镜像加速依赖下载
> （Git 仓库本身仍需可达，可用 `git clone` 镜像站或代理）：
>
> ```bash
> pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
>   "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.0"
> ```
>
> 一键脚本 `scripts/install.sh` 会自动探测并切换到清华镜像。

开发安装：

```bash
git clone https://github.com/suonian/vidknot.git
cd vidknot
pip install -e ".[all]"
```

运行前确认 FFmpeg 可用：

```bash
ffmpeg -version   # 或 python -m vidknot --check-env
```

## 选择使用方式

VidkNot 提供四种使用方式，根据你的场景选择：

| 方式 | 适用场景 | 命令 |
|------|----------|------|
| **CLI** | 日常使用、脚本批处理 | `python -m vidknot "URL"` |
| **Python API** | 集成到自己的 Python 项目 | `from vidknot import VideoKnowledgePipeline` |
| **FastAPI** | 部署为 Web 服务 | `uvicorn vidknot.api:app` |
| **MCP** | 接入 AI Agent（如 Claude、Codex） | `python -m vidknot --mcp` |

不确定用哪个？**CLI 适合大多数用户**，一条命令搞定。

## 配置

复制 `.env.example` 为 `.env`，至少配置转写和笔记生成所需的 API Key：

> 硅基流动（SiliconFlow）提供**免费**的语音识别模型（SenseVoice），注册后即可获取免费 API Key。
> 前往 [siliconflow.cn](https://siliconflow.cn) 注册账号，在控制台生成 API Key 即可免费使用。

```bash
SILICONFLOW_API_KEY=your_siliconflow_api_key   # 语音转写（硅基流动免费模型）
OPENAI_API_KEY=your_openai_compatible_api_key  # 笔记生成（任意 OpenAI 兼容服务）

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

VidkNot 默认生成 Markdown 笔记，示例如下：

```markdown
# [视频标题]

> 来源：https://v.douyin.com/example/
> 处理时间：2026-08-24 10:30:00

## 核心主题

本文讨论了...

## 要点

1. **第一个要点**：详细说明...
2. **第二个要点**：详细说明...

## 细节 / 重要引用 / 术语解释 / 完整转写
```

包含：视频标题、来源链接、核心主题、结构化要点、细节、原文引用、术语解释、带时间戳的完整转写。

## 更多文档

| 文档 | 用途 |
| --- | --- |
| [INSTALL.md](INSTALL.md) | 本地安装和环境检查 |
| [API_GUIDE.md](API_GUIDE.md) | 第三方 API 配置 |
| [COOKIE_GUIDE.md](COOKIE_GUIDE.md) | Cookie 获取与安全说明 |
| [DEPENDENCIES.md](DEPENDENCIES.md) | 直接依赖清单 |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史 |
| [docs/PRIVACY.md](docs/PRIVACY.md) | 隐私红线声明与凭证扫描机制 |
| [docs/CONFIG.md](docs/CONFIG.md) | 环境变量参考 |
| [docs/BACKENDS.md](docs/BACKENDS.md) | 后端存储配置（含飞书机器人权限） |
| [docs/PLATFORMS.md](docs/PLATFORMS.md) | 平台支持矩阵 + TikHub 接口地址 |
| [docs/DOUYIN_FALLBACK.md](docs/DOUYIN_FALLBACK.md) | 抖音四层 Fallback 实战策略 |
| [docs/EXPERIENCES.md](docs/EXPERIENCES.md) | 实战经验汇总 |
| [docs/EXAMPLES.md](docs/EXAMPLES.md) | 自定义后端 / 任务 / 批量 / 订阅源示例 |
| [docs/FAQ.md](docs/FAQ.md) | 常见问题与反模式（遇到问题先看这里）|
| [scripts/codex_sample_curator.py](scripts/codex_sample_curator.py) | Codex 高质量样本筛选（六关检查）|

## 安全与合规

- 不要提交 `.env`、Cookie 文件或任何 API Key
- 只处理你有权访问和使用的视频内容
- 遵守视频平台、云服务和笔记平台的服务条款
- 第三方服务的稳定性、价格和权限策略以各平台官方说明为准

## 联系作者

项目咨询与讨论，请扫描下方二维码添加作者微信：

<img src="assets/wechat-qr.jpg" width="140" alt="微信二维码">

## License

本项目采用 MIT 许可证。

**权限**
- 商业使用（指本工具软件本身）
- 修改
- 分发
- 专利使用
- 私人使用

**条件**
- 必须包含版权声明和许可声明

**限制**
- 无担保
- 无责任

> **重要说明**：本工具仅用于个人学习和研究目的。用户通过本工具下载的视频内容，其版权归原博主或平台所有。将下载内容用于商业用途可能侵犯他人版权，请遵守各平台服务条款及相关法律法规。本工具不对用户的使用行为承担任何责任。

完整许可证文本请查看 [LICENSE](LICENSE) 文件。
