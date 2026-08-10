# VidkNot API 配置指南

VidkNot 需要两类服务：转写服务和笔记生成服务。存储平台按需配置。

## 必需配置

### SiliconFlow

用于语音转文字。当前默认模型为 `FunAudioLLM/SenseVoiceSmall`。

```bash
SILICONFLOW_API_KEY=sk-xxx
```

获取方式：

1. 打开 [SiliconFlow 控制台](https://cloud.siliconflow.cn/)
2. 创建 API Key
3. 写入 `.env`

### LLM（结构化笔记生成）

用于生成结构化笔记。VidkNot 通过 OpenAI 兼容接口调用 LLM，因此可以接入**任意**兼容服务：

```bash
# 默认推荐：通过 LLM_API_KEY + LLM_BASE_URL + VIDKNOT_LLM_MODEL 接入任意兼容服务
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.your-provider.com/v1
VIDKNOT_LLM_MODEL=your-model-name
```

支持的 LLM 服务示例（不限于）：

| 服务 | LLM_BASE_URL | LLM_MODEL 示例 |
|------|--------------|------------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Anthropic (via 代理) | 你的代理地址 | `claude-3-5-sonnet-...` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4/` | `glm-4-flash` |
| 阿里 Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 字节 Doubao | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-...` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| MiniMax | `https://api.MiniMax.com/v1` | `MiniMax-M3` |

也可以直接使用 `OPENAI_API_KEY` + `OPENAI_BASE_URL` 配置（仅兼容 OpenAI 协议的服务）。

## 可选：双 ASR 搜证

VidkNot 默认使用 SiliconFlow + faster-whisper 做双 ASR 交叉验证。`mmx` CLI 可作为搜证和差异仲裁后端；未安装时会自动回退，不影响主流程。

常用验证命令：

```bash
mmx auth status
mmx search query --q "papi酱 网红" --output json
mmx text chat --model MiniMax-M3 --message "你好"
```

## 可选：飞书

用于将笔记写入飞书文档。

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_FOLDER_TOKEN=xxx
```

需要在飞书开放平台给应用开通文档创建和写入权限，并确保目标文件夹对应用可用。

## 可选：Obsidian

用于将 Markdown 写入本地知识库。

```bash
OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault
OBSIDIAN_FOLDER=视频笔记
```

## 可选：Notion

用于将笔记写入指定 Notion 页面。

```bash
NOTION_TOKEN=secret_xxx
NOTION_PAGE_ID=xxx
```

配置要点：

1. 在 [Notion Integrations](https://www.notion.so/my-integrations) 创建集成
2. 复制 Integration Token
3. 在目标页面中添加该集成为 connection
4. 从页面 URL 中取最后的页面 ID

## 可选：语雀

用于将笔记写入语雀。

```bash
YUQUE_TOKEN=xxx
YUQUE_LOGIN=your-login
YUQUE_PATH=VidkNot
```

## 可选：抖音 Cookie

公开视频通常可以直接解析；遇到登录态、风控或短链解析失败时，配置 Cookie 文件：

```bash
VIDKNOT_DOUYIN_COOKIE_FILE=/path/to/douyin-cookies.txt
```

也可以在 `config.yaml` 中配置第三方解析后端：

```yaml
douyin:
  enable_third_party: true
  tikhub:
    api_key: YOUR_TIKHUB_API_KEY
```

对应环境变量：

```bash
TIKHUB_API_KEY=xxx
```

## 完整 `.env` 示例

```bash
SILICONFLOW_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_FOLDER_TOKEN=xxx

OBSIDIAN_VAULT_PATH=/path/to/obsidian/vault

NOTION_TOKEN=secret_xxx
NOTION_PAGE_ID=xxx

YUQUE_TOKEN=xxx
YUQUE_LOGIN=your-login

VIDKNOT_DOUYIN_COOKIE_FILE=/path/to/douyin-cookies.txt
TIKHUB_API_KEY=xxx
```

## 安全要求

- 不要把 `.env`、Cookie 文件或 API Key 提交到 Git
- 不要在代码中硬编码密钥
- 发现密钥泄露后立即吊销并重新生成
- 第三方平台的价格、权限和可用性以官方控制台为准
