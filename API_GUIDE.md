# VidkNot API 使用指南

本文档详细说明 VidkNot 使用的各个 API 及其申请流程。

---

## 1. SiliconFlow（语音转录）

### 服务介绍

SiliconFlow 提供云端语音识别服务，使用阿里 SenseVoice 模型。

### 申请流程

1. 访问 [SiliconFlow 官网](https://cloud.siliconflow.cn/)
2. 注册账号（支持 GitHub/微信登录）
3. 进入控制台 → API Keys → 创建新密钥
4. 复制密钥并设置环境变量

### 费用说明

| 套餐 | 价格 | 免费额度 |
|------|------|----------|
| SenseVoiceSmall | ¥0.001/分钟 | 每月 10 小时免费 |

### 环境变量

```bash
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 支持的文件格式

| 格式 | 支持 | 说明 |
|------|------|------|
| MP3 | ✅ | 推荐 |
| WAV | ✅ | 无损格式 |
| M4A | ✅ | AAC 编码 |
| FLAC | ✅ | 无损格式 |
| OGG | ✅ | |
| WebM | ✅ | |
| AMR | ✅ | |

---

## 2. OpenAI 兼容 API（LLM 笔记生成）

### 支持的服务商

| 服务商 | API 地址 | 备注 |
|--------|----------|------|
| OpenAI | https://api.openai.com/v1 | 官方服务 |
| 智谱 AI | https://open.bigmodel.cn/api/paas/v4/ | 国内镜像 |
| 自建服务 | 任意 OpenAI 兼容地址 | 支持本地部署 |

### 申请流程（以 OpenAI 为例）

1. 访问 [OpenAI 官网](https://platform.openai.com/)
2. 注册账号并完成充值
3. 创建 API Key
4. 设置环境变量

### 环境变量

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1  # 可选，自定义端点
```

### 推荐模型

| 模型 | 用途 | 费用 | 推荐度 |
|------|------|------|--------|
| gpt-4o-mini | 笔记生成 | 低 | ⭐⭐⭐⭐⭐ |
| gpt-4o | 笔记生成 | 中 | ⭐⭐⭐⭐ |
| gpt-3.5-turbo | 笔记生成 | 低 | ⭐⭐⭐ |

### 智谱 AI（国内用户推荐）

1. 访问 [智谱 AI 大模型开放平台](https://open.bigmodel.cn/)
2. 注册账号
3. 创建 API Key

```bash
ZHIPUAI_API_KEY=xxxxxxxxxxxxxxxx
```

---

## 3. 语雀 Yuque（笔记存储）

### 服务介绍

语雀是阿里巴巴旗下的知识库工具，支持 Markdown 文档。

### 申请流程

1. 访问 [语雀官网](https://www.yuque.com/)
2. 注册并登录
3. 进入个人设置 → 开发者 → 访问令牌
4. 创建个人访问令牌
5. 获取个人登录名（yuque.com/你的登录名）

### 环境变量

```bash
YUQUE_TOKEN=xxxxxxxxxxxxxxxx
YUQUE_LOGIN=your-login-name
```

### 权限说明

- 个人访问令牌仅能访问你的个人文档
- 无法访问团队或他人的文档
- 令牌不会在代码中明文存储

---

## 4. 飞书 Feishu（笔记存储）

### 服务介绍

飞书文档，支持企业/个人文档存储。

### 申请流程

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建应用并获取 App ID 和 App Secret
3. 配置权限（文档写入权限）
4. 发布应用

### 环境变量

```bash
FEISHU_APP_ID=cli_xxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
```

### 权限申请

在飞书开放平台控制台申请以下权限：

- `docx:document:create` - 创建文档
- `docx:document:write` - 写入文档

---

## 5. Obsidian（本地存储）

### 服务介绍

Obsidian 是本地知识库工具，通过文件系统存储。

### 环境变量

```bash
OBSIDIAN_VAULT_PATH=/path/to/your/vault
```

### 说明

- 无需申请账号
- 数据存储在本地
- 完全离线可用

---

## 6. Notion（云端存储）

### 服务介绍

Notion 是云端笔记工具，支持富文本和数据库。

### 申请流程

1. 访问 [Notion 官网](https://www.notion.so/)
2. 注册账号并登录
3. 访问 [Notion Developers](https://www.notion.so/my-integrations)
4. 点击 "New integration" 创建集成
5. 设置集成名称和关联工作区
6. 复制 Integration Token

### 配置步骤

1. 创建集成后，复制 Token：
   ```
   secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

2. 在 Notion 中创建或选择一个页面作为父页面

3. 分享页面给集成：
   - 打开目标页面
   - 点击右上角 "..."
   - 选择 "Add connections"
   - 添加你的集成

### 环境变量

```bash
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_PAGE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 页面 ID 获取方式

在 Notion 页面 URL 中获取：
```
https://notion.so/你的页面名-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
最后的 32 位字符即为页面 ID。

### 权限说明

- 每个集成需要手动授权页面访问
- 集成只能访问被明确分享的页面
- 集成 Token 不要泄露给他人

---

## 环境变量配置示例

创建 `.env` 文件：

```bash
# 必填
SILICONFLOW_API_KEY=sk-xxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxx

# 选填（存储）
# 语雀
YUQUE_TOKEN=xxxxxxxx
YUQUE_LOGIN=your-login

# 飞书
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx

# Obsidian
OBSIDIAN_VAULT_PATH=./obsidian-vault

# Notion
NOTION_TOKEN=secret_xxxxxxxx
NOTION_PAGE_ID=xxxxxxxxxxxxxxxx
```

---

## 安全建议

1. **不要提交 .env 文件到 Git**
   ```bash
   # .gitignore 中已排除 .env 文件
   ```

2. **定期轮换 API Key**

3. **使用环境变量而非硬编码**
   ```python
   # ✅ 正确
   api_key = os.getenv("OPENAI_API_KEY")

   # ❌ 错误
   api_key = "sk-xxx"  # 不要硬编码
   ```
