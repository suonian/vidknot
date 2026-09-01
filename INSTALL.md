# VidkNot 安装指南

本文档只覆盖当前仓库版本 `v0.6.5` 的本地安装和验证。

## 环境要求

- Python `>=3.10`
- FFmpeg
- 可用的 `SILICONFLOW_API_KEY`
- 用于生成笔记的 OpenAI 兼容 API Key，例如 `OPENAI_API_KEY`
- 首次使用本地 faster-whisper 时需要下载模型，默认 `small` 模型约 500MB

## 安装 FFmpeg

macOS:

```bash
brew install ffmpeg
```

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

Windows:

```powershell
winget install Gyan.FFmpeg
```

验证：

```bash
ffmpeg -version
```

## 安装 VidkNot

当前 GitHub Release 是 `v0.6.5`。推荐直接安装该版本：

```bash
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.5"
```

如需飞书写入支持：

```bash
pip install "vidknot[feishu] @ git+https://github.com/suonian/vidknot.git@v0.6.5"
```

开发安装：

```bash
git clone https://github.com/suonian/vidknot.git
cd vidknot
pip install -e ".[all]"
```

如果下载 Python 包较慢，可以临时使用清华源：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.5"
```

## 配置

复制环境变量模板：

```bash
cp .env.example .env
```

最小配置：

```bash
SILICONFLOW_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
```

常用可选配置：

```bash
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault

FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_FOLDER_TOKEN=xxx

NOTION_TOKEN=secret_xxx
NOTION_PAGE_ID=xxx

YUQUE_TOKEN=xxx
YUQUE_LOGIN=your-login

VIDKNOT_DOUYIN_COOKIE_FILE=/path/to/douyin-cookies.txt
```

## 双 ASR 校正

VidkNot 默认启用双 ASR 校正：

- SiliconFlow SenseVoice：主转写源
- faster-whisper：本地交叉验证源
- `mmx`：可选搜证与差异仲裁工具，不可用时自动回退

预下载默认模型：

```bash
python -c "from faster_whisper import WhisperModel; WhisperModel('small')"
```

禁用校正：

```bash
python -m vidknot "URL" --no-correct
```

## 验证

检查本地依赖：

```bash
python -m vidknot --check-env
```

只输出笔记，不写入任何平台：

```bash
python -m vidknot "https://v.douyin.com/example/" --destination none --no-cache
```

运行测试：

```bash
pytest
```

## 常见问题

### `ffmpeg` 找不到

确认 `ffmpeg -version` 可以在同一个终端中执行。Windows 安装后可能需要重启终端。

### GitHub 或 PyPI 下载慢

非中国大陆资源建议使用本地代理；Python 包可优先尝试清华源。

### 飞书写入失败

确认飞书应用已经开通文档创建/写入权限，并且 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、目标文件夹权限配置正确。

### 抖音解析不稳定

优先配置 `VIDKNOT_DOUYIN_COOKIE_FILE`，或在 `config.yaml` 中启用第三方解析后端并配置 `TIKHUB_API_KEY`。
