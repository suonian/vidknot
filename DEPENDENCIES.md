# VidkNot 依赖说明

本文档只列出项目直接依赖和用途。完整版本约束以 [pyproject.toml](pyproject.toml) 为准。

## 运行依赖

| 依赖 | 版本约束 | 用途 |
| --- | --- | --- |
| `yt-dlp` | `>=2026.3.17` | 视频/音频下载 |
| `fastapi` | `>=0.136.0` | HTTP API |
| `uvicorn[standard]` | `>=0.27.0` | ASGI 服务运行 |
| `httpx` | `>=0.27.0` | HTTP 请求 |
| `pyyaml` | `>=6.0.1` | 读取 `config.yaml` |
| `openai` | `>=1.0.0` | OpenAI 兼容 LLM 调用 |
| `faster-whisper` | `>=1.0.0` | 本地 ASR 交叉验证 |
| `av` (PyAV) | `>=11,<19` | faster-whisper 音频解码（见下方说明） |

> **`av` 上界说明**：PyAV 19.0.0（2026-09-29）移除了 `av.open()` 的
> `metadata_errors` 参数，而 faster-whisper <=1.2.1 的 `decode_audio()`
> 仍在传该参数，直接调用会抛
> `TypeError: open() got an unexpected keyword argument 'metadata_errors'`。
> faster-whisper 1.2.1 为当前最新版，暂无上游修复，因此必须限制 `av<19`。
> 该问题会导致**双 ASR 校正静默失效**（CLI 捕获异常后回退到 SiliconFlow
> 单源转写，主流程不中断），仅在安装依赖时未生效。

## 可选依赖

| 依赖 | 版本约束 | 用途 |
| --- | --- | --- |
| `feishu-docx` | `>=0.2.7` | 飞书文档写入 |
| `opencc-python-reimplemented` | `>=0.1.7` | 自动繁体 → 简体（Hermes实战 2026-08-25: 台湾/香港创作者视频源）|

安装飞书支持：

```bash
pip install "vidknot[feishu] @ git+https://github.com/suonian/vidknot.git@v0.2.1"
```

## 开发依赖

| 依赖 | 版本约束 | 用途 |
| --- | --- | --- |
| `pytest` | `>=8.0.0` | 单元测试 |
| `ruff` | `>=0.2.0` | 代码检查和格式化 |

开发安装：

```bash
pip install -e ".[all]"
```

## 外部工具

| 工具 | 必需 | 用途 |
| --- | --- | --- |
| FFmpeg | 是 | 音视频处理 |
| `mmx` CLI | 否 | 双 ASR 校正中的联网搜证与差异仲裁 |

`mmx` 不可用时，VidkNot 会保留主转写结果并继续执行主流程。

## Python 版本

`pyproject.toml` 声明 `requires-python = ">=3.10"`。当前测试环境覆盖仓库 CI 和本地开发环境，新增 Python 版本适配时应先跑完整测试。
