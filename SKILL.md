---
name: vidknot
displayName: VidkNot（影音笔记舱）
slug: vidknot
version: 0.6.5
description: >
  一键提取视频文案和知识笔记：把一个视频链接丢进来，VidkNot 自动听懂内容、
  转成完整文字稿，并整理出内容摘要与重点，还能一键保存到
  Obsidian、飞书、Notion、语雀。支持 YouTube、B站、抖音、小红书、快手、
  TikTok、Twitter/X、Instagram、微信视频号、微博、Vimeo 等 11+ 平台，
  不用手敲字幕、不用反复回看视频。当用户要求总结视频、提取视频文案、
  生成视频笔记、把视频转成文字稿或知识笔记时使用。
author: VidkNot Team
license: MIT
homepage: https://github.com/suonian/vidknot
repository: https://github.com/suonian/vidknot
---

# VidkNot — 影音笔记舱（Video Knowledge, Knotted）

把一个视频链接丢进来，VidkNot 会自动「听懂」视频里说的话：
先转成完整文字稿，再整理成带主题、摘要、要点的笔记，
一键存进你常用的知识库（Obsidian / 飞书 / Notion / 语雀 / SQLite / 自定义）。
支持 YouTube、B站、抖音等 **11+ 平台**，课程、访谈、口播、测评都能处理。

## 什么时候使用本技能

当用户希望：

- 从 YouTube、B站、抖音、小红书、快手、TikTok、Twitter/X、Instagram、
  微信视频号、微博或 Vimeo 的视频链接中提取**结构化笔记**
  （主题 / 摘要 / 要点 / 术语）。
- 批量处理**一批视频链接**（URLs.txt 文件或 YAML 订阅列表），
  汇总成统一的笔记库。
- 运行**周期监控**，轮询 YouTube 频道 / B站用户 / 小红书创作者等，
  自动收录新视频。
- 把处理好的笔记同步到 **Obsidian 仓库**、**飞书文档**、
  **Notion 页面**或**语雀知识库**。

本技能能做什么、不能做什么的完整清单（含常见错误用法），
见下方 [应避免的用法（反模式）](#应避免的用法反模式) 章节。

### 长视频 vs 短视频（触发指引）

| 场景 | 建议 |
| --- | --- |
| 短视频（<10 分钟） | 默认配置；链接多时用批处理模式（`--batch`） |
| 中等（10–20 分钟） | 默认配置；双 ASR 校正约需 0.5–1 倍实时时长 |
| 长视频（>20 分钟） | 优先用 `faster-whisper` + `large` 模型；可考虑分段 |
| 超长（>1 小时） | 先分段处理；调大 `network.download_timeout` |

### 边界与前提条件

- **Cookie**：抖音 / B站 / 小红书使用登录态 Cookie 效果最好
  （`cookies/<platform>.txt`，见 `COOKIE_GUIDE.md`）；TikTok / Twitter/X /
  Instagram 直接读取 Chrome 浏览器 Cookie（浏览器须已登录）。
  YouTube / Vimeo / 通用链接无需 Cookie。
- **时长**：无硬性上限，但超过 1 小时的下载应调大
  `network.download_timeout`（默认 600 秒，见 `docs/CONFIG.md`）。
- **不支持付费 / 仅会员 / 仅粉丝可见内容**——判断标准见
  `docs/PLATFORMS.md`。
- 各平台完整支持状态与 Cookie 依赖矩阵：`docs/PLATFORMS.md`。

## 快速开始（一分钟）

```bash
# 1. 安装（一条命令）
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.5"

# 2. 配置（只需要 1 个 API key）
echo "SILICONFLOW_API_KEY=sk-your-key" > .env

# 3. 试跑（demo 模式零配置，首次测试无需任何 key）
vidknot --demo "https://www.bilibili.com/video/BVxxxxx"

# 4. 正式运行
vidknot "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

> 不想装 FFmpeg？用 `pip install 'vidknot[bundled-ffmpeg]'` 即可
> （自带静态 FFmpeg，免系统安装）。

## 应避免的用法（反模式）

以下场景**不要用**本技能，会直接失败或产生误导：

| ❌ 不要这样做 | ✅ 应该这样做 |
| --- | --- |
| 用它播放视频 / 音频 | 本工具不是播放器，只产出文字稿与笔记 |
| 采集直播或实时流 | 当前面向点播（已发布）内容；直播等回放生成后再处理 |
| 下载 DRM / 付费 / 会员 / 仅粉丝可见内容 | 判断标准见 `docs/PLATFORMS.md`；改用平台官方 API |
| 用小红书短链接（`xhslink.com/...`） | 短链易过期被风控；使用带 `xsec_token` 的完整 URL |
| 把 TikHub 等付费第三方 API 当首选 | 它只是免费层（yt-dlp / f2 / iesdouyin）全失败后的兜底 |
| 处理无授权的视频内容 | 只处理你有权访问的内容，遵守平台条款，商用前确认版权 |
| 没装 FFmpeg 就排查其他问题 | 没有 FFmpeg 无法提取音频，先 `brew install ffmpeg` 或装 `[bundled-ffmpeg]` |
| Cookie 过期后反复重试下载 | 报错含 `403` / `Fresh cookies needed` / `登录` 时先重新导出 Cookie（见 `COOKIE_GUIDE.md`） |

Cookie 并不是所有平台的硬门槛：YouTube / Vimeo / 通用链接**无需**
Cookie；只有抖音 / B站 / 小红书建议提供（导出方法三步见
`COOKIE_GUIDE.md`），TikTok / Twitter/X / Instagram 直接复用你已登录的
Chrome。配置不全时可先用 `vidknot --demo` 验证环境。

更多反模式与错误速查见 `docs/FAQ.md` 的「反模式（不要这样做）」与
「错误速查表」。

## 接口形态

VidkNot 为 Agent / 脚本提供四种接口：

| 接口 | 调用方式 | 适用场景 |
| --- | --- | --- |
| **CLI** | `vidknot <url> [--destination <obsidian|feishu|notion|yuque|none>]` | 单次命令行处理 |
| **Python API** | `from vidknot import VideoKnowledgePipeline; pipeline.run(url)` | 嵌入式脚本 |
| **FastAPI** | `uvicorn vidknot.api:app --reload` | 为其他工具提供 HTTP 服务 |
| **MCP** | `vidknot --mcp` | Claude / Qoder / Cursor / Cline 等通过 Model Context Protocol 调用 |

### MCP 用法

```bash
vidknot --mcp
```

MCP 服务启动后（stdio 传输），Agent 获得以下工具：

- `video_knowledge(url, destination="obsidian", format="structured", language="auto", feishu_folder=None, obsidian_tags=None) -> str` —
  完整流水线（下载 + ASR + LLM + 保存），返回 Markdown 笔记；
  `destination` 可选 `feishu/obsidian/both/none`
- `video_to_notes(...)` — 同上（别名工具，参数一致）
- `batch_process(urls: list[str], destination="none", format="structured", language="auto", max_workers=3) -> str` —
  并发批处理，返回 JSON：`{"total": N, "success": N, "results": [{url, success, title, error}, ...]}`
- `platform_status() -> str` — 查询各平台支持状态（域名、字幕支持、
  Cookie 配置、转录策略），返回 JSON
- `search_video(query, platform) -> str` — 预留接口（未实现，直接提示
  改用 URL 调用）

## 配置

配置按「先跑通，再按需加」分三组，日常只需第 ① 组。

### ① 必填（能跑通的最小配置）

```bash
# .env —— 只要 1 个 key（语音转文字）
SILICONFLOW_API_KEY=sk-xxxxxxxx
```

要生成结构化笔记时再补上 LLM（任何 OpenAI 兼容端点）：

```bash
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1
VIDKNOT_LLM_MODEL=gpt-4o-mini
```

### ② 可选：存储目标（用哪个配哪个）

```bash
# Obsidian
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault

# 飞书文档
FEISHU_APP_ID=cli_xxxx
FEISHU_APP_SECRET=xxxxxxxx

# Notion
NOTION_TOKEN=secret_xxxx
NOTION_PAGE_ID=xxxx

# 语雀
YUQUE_TOKEN=xxxx
YUQUE_LOGIN=xxxx
```

### ③ 可选：高级开关

```bash
# 抖音 Cookie（提升成功率；其他平台见 COOKIE_GUIDE.md）
VIDKNOT_DOUYIN_COOKIE_FILE=/path/to/douyin-cookies.txt

# 转写引擎切换（留空则用本地 faster-whisper，免云端 key）
SILICONFLOW_API_KEY=
```

完整变量参考见 `.env.example`，逐项详解见 `docs/CONFIG.md`。

## 使用示例

### CLI

```bash
# 单个视频，保存到 Obsidian
vidknot "https://www.bilibili.com/video/BV1xx411c7mD"

# 单个视频，只输出原始转写
vidknot --raw "https://www.youtube.com/watch?v=abc" -l zh

# 单个视频，保存到飞书文档
vidknot "https://v.douyin.com/abc123" -d feishu

# 从 urls.txt 批量处理
vidknot --batch urls.txt -d obsidian --max-workers 3

# 本地 mp4
vidknot --batch-dir ./videos/ -d feishu
```

### Python API

```python
from vidknot import VideoKnowledgePipeline

pipeline = VideoKnowledgePipeline(destination="obsidian", language="zh")
result = pipeline.run("https://www.xiaohongshu.com/explore/abc")
print(result["markdown"])
```

### MCP（Agent 调用）

在支持 MCP 的 Agent（Claude / Qoder / Cursor / Cline 等）中：

```python
# 单个视频：提取并保存到 Obsidian
note = call_tool(
    "video_knowledge",
    url="https://www.bilibili.com/video/BV1xx",
    destination="obsidian",       # feishu / obsidian / both / none
)

# 批量：一次处理多个链接，单个失败不影响其他
summary = call_tool(
    "batch_process",
    urls=["https://...link1", "https://...link2"],
    destination="obsidian",
    max_workers=3,
)
# summary 是 JSON 字符串：{"total": 2, "success": 2, "results": [...]}
```

## 架构（v0.4.x）

```
        11+ 自媒体平台
        ┌──────────────────────┐
        │ YouTube / Bilibili    │  提取
        │ Douyin / Xiaohongshu  │  ───────►
        │ Kuaishou / TikTok     │           │
        │ Twitter/X / Instagram │           │
        │ WeChat / Weibo        │           │
        │ Vimeo                 │           │
        └──────────────────────┘           │
                                            ▼
        ┌─────────────────────────────────────────────────────────┐
        │                  core/（流水线）                         │
        │  downloader → transcriber (双 ASR) → corrector          │
        │  → processor (LLM, OpenAI 兼容) → writer                │
        └─────────────────────────────────────────────────────────┘
                                            │
                                            ▼
        4+ 存储目标                           + v0.4.0 框架能力
        ┌──────────────────────┐            ┌──────────────────────┐
        │ Obsidian              │            │ core/backend/         │
        │ Feishu (飞书)         │  ────►     │ core/source/          │
        │ Notion                │            │ core/batch/           │
        │ Yuque (语雀)          │            │ core/monitor/         │
        └──────────────────────┘            └──────────────────────┘
```

## 配置文件发现

Agent 拿到本技能后，应查找：

1. `pyproject.toml` → 安装依赖、定位入口点
2. `.env.example` → 必填环境变量模板
3. `docs/CONFIG.md` → 完整配置参考
4. `SKILL.md`（本文件）→ 何时 / 如何使用

## 本技能包含的文件

| 文件 | 用途 |
| --- | --- |
| `SKILL.md` | 本文件（YAML frontmatter + 使用说明） |
| `README.md` / `README.en.md` | 中文默认首页 / 英文辅助 |
| `CHANGELOG.md` | 版本历史 |
| `CONTRIBUTING.md` | 贡献指南 |
| `SECURITY.md` | 安全问题报告 |
| `DISCLAIMER.md` | 仅限个人学习用途声明 |
| `COOKIE_GUIDE.md` | Cookie 处理指南 |
| `API_GUIDE.md` | API key 配置 |
| `INSTALL.md` | 安装说明 |
| `docs/` | 补充文档（PRIVACY、BACKENDS、CONFIG、EXAMPLES 等） |
| `examples/sources.yaml.example` | YAML 订阅源模板 |
| `scripts/install.sh` | 一键安装 + 验证脚本 |

## 版本规则

本技能遵循[语义化版本](https://semver.org/lang/zh-CN/)：

- MAJOR：公共 API 破坏性变更
- MINOR：向后兼容的新功能
- PATCH：缺陷修复

最新版：**0.6.5** — 详见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

MIT — 见 [LICENSE](LICENSE)。
