---
name: vidknot
version: 0.4.1
description: >
  Extract structured knowledge notes from 11+ self-media platforms
  (YouTube, Bilibili, Douyin, Xiaohongshu, Kuaishou, TikTok, Twitter/X,
  Instagram, WeChat Channels, Weibo, Vimeo). Dual-ASR cross-validation
  (SiliconFlow + faster-whisper), OpenAI-compatible LLM, pluggable
  storage backends, async periodic scheduler, batch runner,
  credential-leak-proof source loader.
author: VidkNot Team
license: MIT
homepage: https://github.com/suonian/vidknot
repository: https://github.com/suonian/vidknot
---

# VidkNot — Video Knowledge, Knotted

A general research platform framework that extracts knowledge from
**11+ self-media platforms** and saves structured notes to your
favorite knowledge base (Obsidian / Feishu / Notion / Yuque / SQLite / custom).

## When to use this skill

Use VidkNot when the user wants to:

- Extract **structured notes** (topic / summary / key points / terms) from
  a video link on YouTube, Bilibili, Douyin, Xiaohongshu, Kuaishou, TikTok,
  Twitter/X, Instagram, WeChat Channels, Weibo, or Vimeo.
- Process a **batch of video links** (URLs.txt file or YAML subscription list)
  into a unified notes corpus.
- Run a **periodic monitor** that polls a YouTube channel / Bilibili user /
  Xiaohongshu creator / etc. and ingests new videos automatically.
- Sync processed notes to **Obsidian vault**, **Feishu document**,
  **Notion page**, or **Yuque book**.

Do NOT use VidkNot for:

- Real-time video / audio streaming (not a media player).
- Live broadcast (livestream) ingestion (current code targets on-demand).
- DRMed / paid content (use official APIs of the platform).

## Quick start (one minute)

```bash
# 1. Install (one command)
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.4.1"

# 2. Configure (only one API key required)
echo "SILICONFLOW_API_KEY=sk-your-key" > .env

# 3. Try it (zero-config demo mode works without any key for the first test)
vidknot --demo "https://www.bilibili.com/video/BVxxxxx"

# 4. Real run
vidknot "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## Interfaces

VidkNot exposes four interfaces for agents / scripts:

| Interface | Invocation | Use case |
| --- | --- | --- |
| **CLI** | `vidknot <url> [--destination <obsidian|feishu|notion|yuque|none>]` | One-shot CLI |
| **Python API** | `from vidknot import VideoKnowledgePipeline; pipeline.run(url)` | Embedded scripting |
| **FastAPI** | `uvicorn vidknot.api:app --reload` | HTTP service for other tools |
| **MCP** | `vidknot --mcp` | Claude / Qoder / Cursor / Cline etc. via Model Context Protocol |

### MCP usage

```bash
vidknot --mcp
```

Once the MCP server is running, the agent gains these tools:

- `vidknot_extract(url: str, destination: str = "none") -> str` —
  full pipeline (download + ASR + LLM + save), returns Markdown
- `vidknot_transcribe_only(url: str) -> str` —
  only download + transcribe (no LLM, no save)
- `vidknot_status() -> dict` — version, configured providers, last run

## Configuration

Minimal configuration (only **1** key required):

```bash
# .env
SILICONFLOW_API_KEY=sk-xxxxxxxx
```

Full configuration (4 keys, recommended):

```bash
# .env
# Required: ASR
SILICONFLOW_API_KEY=sk-xxxxxxxx

# Required (for LLM-generated notes): any OpenAI-compatible endpoint
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1
VIDKNOT_LLM_MODEL=gpt-4o-mini

# Optional: storage destinations
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault
# or
FEISHU_APP_ID=cli_xxxx
FEISHU_APP_SECRET=xxxxxxxx

# Optional: vidknot-specific knobs
VIDKNOT_DOUYIN_COOKIE_FILE=/path/to/douyin-cookies.txt
```

See `.env.example` for the full reference and `docs/CONFIG.md` for
detailed documentation of every variable.

## Examples

### CLI

```bash
# One video, save to Obsidian
vidknot "https://www.bilibili.com/video/BV1xx411c7mD"

# One video, raw transcription only
vidknot --raw "https://www.youtube.com/watch?v=abc" -l zh

# One video, save to Feishu doc
vidknot "https://v.douyin.com/abc123" -d feishu

# Batch from urls.txt
vidknot --batch urls.txt -d obsidian --max-workers 3

# Local mp4
vidknot --batch-dir ./videos/ -d feishu
```

### Python API

```python
from vidknot import VideoKnowledgePipeline

pipeline = VideoKnowledgePipeline(destination="obsidian", language="zh")
result = pipeline.run("https://www.xiaohongshu.com/explore/abc")
print(result["markdown"])
```

### MCP (agent use)

```python
# From an MCP-aware agent (Claude / Qoder / Cursor / etc.)
result = call_tool("vidknot_extract", url="https://www.bilibili.com/video/BV1xx")
save_to_memory(result)
```

## Architecture (v0.4.x)

```
        11+ Self-Media Platforms
        ┌──────────────────────┐
        │ YouTube / Bilibili    │  Extract
        │ Douyin / Xiaohongshu  │  ───────►
        │ Kuaishou / TikTok     │           │
        │ Twitter/X / Instagram │           │
        │ WeChat / Weibo        │           │
        │ Vimeo                 │           │
        └──────────────────────┘           │
                                            ▼
        ┌─────────────────────────────────────────────────────────┐
        │                  core/  (pipeline)                      │
        │  downloader → transcriber (dual-ASR) → corrector        │
        │  → processor (LLM via OpenAI-compat) → writer           │
        └─────────────────────────────────────────────────────────┘
                                            │
                                            ▼
        4+ Storage Targets                    + v0.4.0 framework
        ┌──────────────────────┐            ┌──────────────────────┐
        │ Obsidian              │            │ core/backend/         │
        │ Feishu (飞书)         │  ────►     │ core/source/          │
        │ Notion                │            │ core/batch/           │
        │ Yuque (语雀)          │            │ core/monitor/         │
        └──────────────────────┘            └──────────────────────┘
```

## Configuration discovery

When the agent receives this skill, it should look for:

1. `pyproject.toml` → install dependencies, find entry points
2. `.env.example` → template for required environment variables
3. `docs/CONFIG.md` → full configuration reference
4. `SKILL.md` (this file) → when / how to use

## Files in this skill

| File | Purpose |
| --- | --- |
| `SKILL.md` | This file (YAML frontmatter + usage docs) |
| `README.md` / `README.zh.md` | Full English / Chinese README |
| `CHANGELOG.md` | Version history |
| `CONTRIBUTING.md` | Contribution guide |
| `SECURITY.md` | Security reporting |
| `DISCLAIMER.md` | Personal-learning-only disclaimer |
| `COOKIE_GUIDE.md` | Cookie handling guide |
| `API_GUIDE.md` | API key configuration |
| `INSTALL.md` | Install instructions |
| `docs/` | Supplementary docs (PRIVACY, BACKENDS, CONFIG, EXAMPLES) |
| `examples/sources.yaml.example` | YAML subscription source template |
| `scripts/install.sh` | One-line install + verify script |

## Versioning

This skill follows [Semantic Versioning](https://semver.org/):

- MAJOR: breaking changes to public API
- MINOR: new features, backward-compatible
- PATCH: bug fixes

Latest: **0.4.1** — see [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
