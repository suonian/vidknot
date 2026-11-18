---
name: vidknot
displayName: VidkNot（影音笔记舱）
slug: vidknot
version: 0.6.13
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

## 两种工作模式（重要）

VidkNot 有两种用法，**由你（宿主智能体）选择**：

| | 模式 A：两段式契约（推荐给 Agent） | 模式 B：一键成稿 |
| --- | --- | --- |
| 谁做搜证与纠错 | **你自己** —— 用你自带的搜索工具与你自己的模型 | VidkNot 内部用可配置的 LLM provider |
| VidkNot 做什么 | 只做确定性采集：下载 → 转写 → 双 ASR 差异 → 待搜证词 | 下载 → 转写 → 校正 → 生成笔记 → 保存 |
| 用到的工具 | `video_material` + `save_note` | `video_to_notes` / `batch_process` |
| 厂商绑定 | **无** | 无（`providers.default_provider` 可配任意 OpenAI 兼容端点） |

**模式 A 的关键点**：`video_material` **不调用任何大模型、不发起任何联网搜索**，
它只产出一份「素材包」——转写全文、双 ASR 差异清单、以及从差异里算法提取的
待搜证词。拿到素材包后：

1. 用**你自己的搜索工具**对 `search_candidates` 逐个搜证；
2. 用**你自己的模型**结合搜索结果完成纠错与结构化成稿；
3. 调用 `save_note` 把成稿落库（此步同样不调用任何大模型）。

这样搜证走你信任的搜索通道、模型走你已付费已配置的模型，
VidkNot 不再替你决定用哪家厂商。

### 模式 A 调用示例（MCP）

```python
# 第一段：采集素材包（零 LLM、零搜索）
bundle = call_tool(
    "video_material",
    url="https://www.bilibili.com/video/BV1xx",
    with_diff=True,        # 跑 faster-whisper 对照，产出差异清单
    max_candidates=12,     # 待搜证词上限
)
# bundle 是 JSON 字符串：
# {"schema": "vidknot.material/1", "title": ..., "duration": ...,
#  "transcription": "字幕/ASR 完整转写",
#  "fw_segments": "[00:00.0 - 00:07.2] faster-whisper 时间戳段",
#  "diffs": ["[0] replace: SF='...' ↔ FW='...' | ctx: ..."],
#  "search_candidates": ["ByteDance", "字节跳动"], ...}
#
# search_candidates 是**原文词级**差异里提取的待搜证词：
#   拉丁词须含大写字母或数字（ByteDance / iPhone / GPT-4 / 2024），
#   中文取差异位置前后 2-4 个汉字的词块；
#   英文句首大写的常见词与标点碎片已被过滤，不会拿噪声去搜。

# ← 这里用你自己的搜索工具搜证，用你自己的模型成稿 → markdown

# 第二段：成稿落库
result = call_tool(
    "save_note",
    markdown=markdown,                 # 你生成的笔记正文
    url="https://www.bilibili.com/video/BV1xx",
    title=bundle["title"],
    destination="obsidian",
    tags=["视频笔记"],
)
```

### 模式 A 调用示例（CLI）

```bash
# 第一段：采集素材包到 material.json
vidknot "URL" --material -o material.json

# ← 你自己搜证、自己成稿 → note.md

# 第二段：成稿落库
vidknot "URL" --save-note note.md --destination obsidian
```

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
- 性能调优、长视频分段、排障步骤等最佳实践：`docs/BEST_PRACTICES.md`。

## 快速开始（一分钟）

```bash
# 1. 安装（一条命令）
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.13"

# 2. 配置（只需要 1 个 API key）
echo "SILICONFLOW_API_KEY=sk-your-key" > .env

# 3. 试跑（demo 模式零配置，首次测试无需任何 key）
vidknot --demo "https://www.bilibili.com/video/BVxxxxx"

# 4. 正式运行
vidknot "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

> 不想装 FFmpeg？用 `pip install 'vidknot[bundled-ffmpeg]'` 即可
> （自带静态 FFmpeg，免系统安装）。

### 运行环境（macOS / Windows / Linux）

三个平台均已支持。Windows 用户可直接用一键脚本完成安装与验证：

```powershell
# 自动探测 pip 镜像（优先清华源）、检查并安装 FFmpeg、准备 .env、跑 demo 验证
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

| 平台 | 安装脚本 | 环境自检 |
| --- | --- | --- |
| macOS / Linux | `bash scripts/install.sh` | `python -m vidknot --check-env` |
| Windows | `powershell -File scripts/install.ps1` | `python -m vidknot --check-env` |

> Windows 用户注意：命令行中文默认是 GBK 编码，MCP / JSON-RPC 场景需
> UTF-8 标准流，VidkNot 的 CLI 与 MCP 入口已自动处理，无需手动设置
> `PYTHONUTF8`。

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
| **CLI** | `vidknot <url> [--destination <obsidian|feishu|notion|yuque|none|fw|fw_file>]` | 单次命令行处理 |
| **CLI（两段式）** | `vidknot <url> --material` / `vidknot <url> --save-note <file>` | Agent 自己搜证与成稿，VidkNot 只做采集与落库 |
| **Python API** | `from vidknot import VideoKnowledgePipeline; pipeline.run(url)` | 嵌入式脚本 |
| **FastAPI** | `uvicorn vidknot.api:app --reload` | 为其他工具提供 HTTP 服务 |
| **MCP** | `vidknot --mcp` | Claude / Qoder / Cursor / Cline 等通过 Model Context Protocol 调用 |

### MCP 用法

```bash
vidknot --mcp
```

MCP 服务启动后（stdio 传输），Agent 获得以下工具：

| 工具 | 用途 | 签名要点 |
| --- | --- | --- |
| `video_knowledge` | 完整流水线 → Markdown | `(url, destination="obsidian", …)`，`destination` 可选 `feishu/obsidian/both/none/fw/fw_file` |
| `video_to_notes` | 同上（别名） | 参数完全一致 |
| `batch_process` | 并发批处理 → JSON | `(urls: list[str], destination="none", max_workers=3, …)` |
| `platform_status` | 平台支持状态查询 → JSON | 域名、字幕、Cookie、策略 一键查看 |
| `search_video` | 预留搜索接口 | 当前直接提示改用 URL 调用 |
| `video_material` | **两段式第一段**：采集素材包（零 LLM、零搜索） | `(url, with_diff=True, max_candidates=12, language="auto")` |
| `save_note` | **两段式第二段**：把成稿落库（零 LLM） | `(markdown, url="", title="", destination="obsidian", tags=[])` |

> `fw`：不保存，输出 SF 文本 + FW 时间戳段；`fw_file`：FW 段写到 `<输出文件>.fw.txt`（须配合路径）。

实际调用示例见下方 [MCP（Agent 调用）](#mcpagent-调用)。

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

### ④ 双 ASR 校正 / 搜证后端（不绑定任何厂商）

仅在用**模式 B（一键成稿）**并开启双 ASR 校正时才需要；
**模式 A（两段式）**下搜证与校正由智能体自己完成，这些开关一律不生效。

```bash
# 校正后端：auto(默认, provider → mmx → 跳过) / provider / mmx / none
VIDKNOT_CORRECTION_BACKEND=auto

# 搜证后端：mmx / none（mmx 未安装时自动跳过搜证，不报错）
VIDKNOT_SEARCH_BACKEND=mmx

# mmx 后端使用的模型（留空则用 mmx CLI 自身默认模型）
VIDKNOT_CORRECTION_MODEL=MiniMax-M3
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

# 输出 SF 完整文本 + FW 时间戳段（不保存，给结构分析用）
vidknot "URL" -d fw
vidknot "URL" -d fw_file -o out.txt   # FW 段另存 out.fw.txt

# 从 urls.txt 批量处理
vidknot --batch urls.txt -d obsidian --max-workers 3

# 本地 mp4
vidknot --batch-dir ./videos/ -d feishu

# ===== 两段式契约（Agent 模式）=====

# 第一段：采集素材包（不调 LLM、不联网搜索）
vidknot "URL" --material -o material.json
vidknot "URL" --material --no-diff          # 跳过 faster-whisper 对照

# 第二段：把智能体写好的成稿落库（不调 LLM）
vidknot "URL" --save-note note.md --destination obsidian
cat note.md | vidknot "URL" --save-note -    # 从 stdin 读
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
        │           core/（确定性部分：无 LLM、无联网搜索）          │
        │  downloader → transcriber (字幕 / 双 ASR) → diff          │
        │  → agent_material（待搜证词，算法提取）                    │
        └─────────────────────────────────────────────────────────┘
                        │                          │
        模式 A（两段式） │                          │ 模式 B（一键成稿）
                        ▼                          ▼
        ┌───────────────────────────┐   ┌────────────────────────────┐
        │ 宿主智能体（你）            │   │ processor（LLM provider，   │
        │  自己的搜索工具 → 自己的模型  │   │  可配任意 OpenAI 兼容端点）  │
        └───────────────────────────┘   │  → corrector（后端可插拔）    │
                        │                └────────────────────────────┘
                        ▼                          │
              save_note（只落库）                   ▼
                        └──────────►  4+ 存储目标
                                    ┌──────────────────────┐
                                    │ Obsidian              │
                                    │ Feishu (飞书)         │
                                    │ Notion                │
                                    │ Yuque (语雀)          │
                                    └──────────────────────┘
```

## 配置文件发现

Agent 拿到本技能后，应查找：

1. `pyproject.toml` → 安装依赖、定位入口点
2. `.env.example` → 必填环境变量模板
3. `docs/CONFIG.md` → 完整配置参考
4. `docs/BEST_PRACTICES.md` → 性能调优、排障流程
5. `SKILL.md`（本文件）→ 何时 / 如何使用

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
| `docs/` | 补充文档（PRIVACY、BACKENDS、CONFIG、EXAMPLES、BEST_PRACTICES 等） |
| `examples/sources.yaml.example` | YAML 订阅源模板 |
| `scripts/install.sh` | 一键安装 + 验证脚本（macOS / Linux） |
| `scripts/install.ps1` | 一键安装 + 验证脚本（Windows PowerShell） |

## 版本规则

本技能遵循[语义化版本](https://semver.org/lang/zh-CN/)：

- MAJOR：公共 API 破坏性变更
- MINOR：向后兼容的新功能
- PATCH：缺陷修复

最新版：**0.6.13** — 解绑厂商绑定，改为「两段式 Agent 契约」。

- **不再强制 MiniMax、不再强制某类大模型**：新增 `video_material` +
  `save_note` 两个 MCP 工具与 `--material` / `--save-note` 两个 CLI 模式。
  第一段只做确定性采集（下载 / 转写 / 双 ASR 差异 / 待搜证词），**零 LLM、
  零联网搜索**；搜证用宿主智能体自己的搜索工具，纠错与成稿用它自己的模型。
- **双 ASR 校正后端可插拔**：`settings.correction_backend` 支持
  `auto`（默认，provider → mmx → 跳过）/ `provider` / `mmx` / `none`，
  `settings.search_backend` 支持 `mmx` / `none`，
  `settings.correction_model` 可指定 mmx 后端使用的模型。
  此前校正硬编码 `MiniMax-M3`，且 mmx 未安装时静默降级。
- **修复保存链路从未生效**：`save()` 此前只在传入**非空** config 时才实例化
  写入器，CLI 传的空 dict 与 MCP 完全不传都会让写入器变成 `None`，
  保存静默返回空串；同时 `FeishuWriter.create_document` 被误声明为
  `async`，同步调用拿到的只是从未被 await 的协程对象。两者均已修复，
  凭证缺失现在会明确报错而不是静默跳过。
- **修复 `siliconflow.model` 死键**：该配置此前从未生效，现已真正透传给
  ASR 请求，并支持 `providers.siliconflow.base_url` 覆盖。

v0.6.12 的「消除测试用例对运行环境的依赖（CI 全矩阵转绿）」与 v0.6.11 的
13 项 Windows 跨平台兼容性修复不变，其中最关键的一项是**双 ASR 校正在
Windows 上静默失效**，已修复。不改变付费 / 会员 / DRM 内容的授权边界。
详见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

MIT — 见 [LICENSE](LICENSE)。
