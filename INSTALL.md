# VidkNot 安装指南

本文档只覆盖当前仓库版本 `v0.6.11` 的本地安装和验证。

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

当前 GitHub Release 是 `v0.6.11`。推荐直接安装该版本：

```bash
pip install "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.11"
```

如需飞书写入支持：

```bash
pip install "vidknot[feishu] @ git+https://github.com/suonian/vidknot.git@v0.6.11"
```

开发安装：

```bash
git clone https://github.com/suonian/vidknot.git
cd vidknot
pip install -e ".[all]"
```

如果下载 Python 包较慢，可以临时使用清华源：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.11"
```

一键安装 / 验证（含 FFmpeg 检查、`.env` 模板、demo 验证，自动切换清华镜像）：

```bash
# macOS / Linux
bash scripts/install.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
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

## Windows 用户注意

项目在 macOS 上开发，Windows 有一批特有的坑。框架内部已做兼容处理，
但下面几点仍需留意。

### 标准流编码

Windows 的标准输入输出默认是本地代码页（简体中文为 GBK/cp936），
而 MCP stdio 协议、JSON-RPC、CI 日志都要求 UTF-8。

`python -m vidknot` 与 `--mcp` 启动时会自动把 stdin / stdout / stderr
切换到 UTF-8，一般无需干预。若你在自己的脚本里直接调用
`vidknot.adapters.mcp_server.run_mcp_server()`，请先调用：

```python
from vidknot.utils.stdio import ensure_utf8_stdio
ensure_utf8_stdio()
```

### 中文控制台乱码

在 PowerShell 里输出中文若出现乱码，设置环境变量：

```powershell
$env:PYTHONUTF8 = "1"
```

或永久生效：`setx PYTHONUTF8 1`

### 子进程输出编码（双 ASR 校正）

双 ASR 校正依赖 `mmx` CLI（Node 工具），其输出恒为 UTF-8；而
`subprocess.run(text=True)` 在 Windows 上按本地代码页（GBK）解码，
字节流解不了时会抛 `UnicodeDecodeError`，并最终以
`json.loads(None)` 的误导性报错暴露。该问题会让**双 ASR 校正静默失效**
（流程不报错，但交叉校验被跳过）。

v0.6.11 起所有以文本模式捕获子进程输出的调用点都显式指定
`encoding="utf-8"` + `errors="replace"`。若你看到日志里出现
`双 ASR 校正失败，回退到 SiliconFlow 单源`，请确认 `mmx` 已安装且在
`PATH` 中：

```powershell
mmx --version
```

### PyAV 版本上界

PyAV 19.0.0 移除了 `av.open()` 的 `metadata_errors` 参数，而
faster-whisper <= 1.2.1 仍在传该参数，会导致本地 ASR 直接不可用
（表现为双 ASR 交叉校验静默失效）。v0.6.11 起锁定 `av>=11,<19`，
如遇此问题请重装依赖：

```powershell
pip install -e ".[all]"
```

### 保留设备名

Windows 保留 `CON` / `PRN` / `AUX` / `NUL` / `COM1-9` / `LPT1-9`，
且保留名带任意扩展名仍然保留（`CON.md` 依然是控制台设备，
写入时内容会进控制台、文件不会生成）。VidkNot 生成的文件名会自动加
`_` 前缀规避。

### FFmpeg

Windows 推荐用内置静态版本，无需管理员权限：

```powershell
pip install "vidknot[bundled-ffmpeg]"
```

或用 winget：`winget install Gyan.FFmpeg`

### 抖音 Cookie

从 Chrome 导出 Cookie 前需完全退出 Chrome，否则 yt-dlp 无法复制被占用的
Cookie 库（yt-dlp issue #7271）。详见 [COOKIE_GUIDE.md](COOKIE_GUIDE.md)。

### 本地 ASR 模型下载

双 ASR 校正需要下载 faster-whisper 模型（约 500MB），国内建议走镜像：

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

也可以直接写进 `.env`（VidkNot 启动时会加载）。

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
