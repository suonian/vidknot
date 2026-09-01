# VidkNot 常见问题 (FAQ)

## 快速导航

- [错误速查表](#错误速查表)
- [安装与环境](#安装与环境)
- [平台支持](#平台支持)
- [Cookie 与认证](#cookie-与认证)
- [API 与配置](#api-与配置)
- [输出与保存](#输出与保存)
- [反模式（不要这样做）](#反模式不要这样做)

---

## 错误速查表

CLI / API 报错时按此表自查。v0.6.0 起，CLI 会在出错时直接输出
「错误信息 + 建议」，建议文案与本表一致。

| 错误信息（关键词） | 类型 | 原因 | 解决 |
| --- | --- | --- | --- |
| `ffmpeg: command not found` / FFmpeg 缺失 | 配置错误 | 未安装 FFmpeg | `brew install ffmpeg` / `apt install ffmpeg`，或 `pip install 'vidknot[bundled-ffmpeg]'` 使用内置静态版本 |
| `Cookie 无效或已过期` / `Fresh cookies needed` | 配置错误 | Cookie 过期（抖音约 2-4 周） | 浏览器重新登录该平台，按 `COOKIE_GUIDE.md` 重新导出到 `cookies/<平台>.txt` |
| `无法获取抖音 Cookie` | 临时故障 | CDP / browser_cookie3 都失败 | 完全退出 Chrome 后重试；或手动导出 Netscape 文件 |
| `未配置 SILICONFLOW_API_KEY` | 配置错误 | 缺少转写 API Key | `.env` 中设置 `SILICONFLOW_API_KEY`（硅基流动免费注册），见 `docs/CONFIG.md` |
| `音频文件为空或无语音内容` | 能力边界 | 纯音乐 / 无声视频 | 更换有人声的内容重试 |
| `下载超时（600 秒）` | 临时故障 | 网络慢或视频过长 | 检查网络；长视频在 `config.yaml` `network.download_timeout` 调大 |
| `微信视频号暂不支持自动下载` | 能力边界 | 微信封闭生态 | 用 res-downloader / putyy 抓包导出后，走本地批量目录处理 |
| `所有第三方 API 均失败` | 临时故障 | 免费层与付费兜底都失败 | 检查链接是否有效；如启用 TikHub 检查 `TIKHUB_API_KEY` 额度 |
| `SABR-only` / YouTube 无法下载 | 临时故障 | YouTube 限制 web client | 自动降级处理；仍失败则导出 `cookies/youtube.txt` 后重试 |
| `会员 / 付费 / 403 权限` 类错误 | 能力边界 | 付费内容或授权限制 | VidkNot 不支持付费/会员内容，见 `docs/PLATFORMS.md` 判断标准；**不要重试** |
| `笔记生成失败` / LLM 错误 | 配置错误 | LLM 余额不足或配置错误 | 检查 provider 配置与余额；`config.yaml` 可切换 provider |
| `依赖检查失败` | 配置错误 | 缺 yt-dlp / faster-whisper | 运行 `python -m vidknot --check-env` 查看安装指引 |

> **类型说明**：
> - **临时故障**——网络、风控、浏览器状态问题，稍后或换条件重试可恢复；
> - **配置错误**——缺 key / Cookie 过期 / 缺依赖，必须人工修正配置后才能恢复；
> - **能力边界**——本工具不支持的内容形态，重试无效，请按建议换路径。

> 提示：所有异常都带 `hint` 字段；MCP / Python API 调用方可读取
> `e.hint` 获得修正建议（`e.message` 是错误本体，`e.details` 是补充详情）。

---

## 安装与环境

### Q: 运行时报 `ffmpeg: command not found`

**原因**：VidkNot 依赖 FFmpeg 进行音频提取，未安装则无法工作。

**解决**：

| 系统 | 命令 |
|------|------|
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Windows | `winget install Gyan.FFmpeg` |
| 任意（免系统安装） | `pip install 'vidknot[bundled-ffmpeg]'`（内置静态二进制） |

安装后验证：`ffmpeg -version`（或 `python -m vidknot --check-env`）

### Q: faster-whisper 首次运行很慢

**原因**：首次使用本地 ASR 时需要下载模型（`small` 约 500MB）。

**解决**：耐心等待一次下载完成，后续运行会自动使用缓存。也可改用 SiliconFlow 云端 ASR 跳过本地模型下载。

### Q: Python 版本要求？

**要求**：Python >= 3.10。低于 3.10 会安装失败。

---

## 平台支持

### Q: 哪些平台完全支持？哪些有限制？

| 状态 | 平台 |
|------|------|
| ✅ 稳定 | YouTube、B站、TikTok、Twitter/X、Instagram |
| ✅ 需 Cookie | 抖音（Cookie 2-4 周失效） |
| ✅ 已修复 | 小红书（v0.3.3 修复 4 个 Bug） |
| ⚠️ 依赖 yt-dlp | 快手、微博 |
|  不支持 | 直播回放、付费/会员内容 |

### Q: 抖音下载失败怎么办？

VidkNot 有四层 Fallback 策略：

1. **Layer 0**：f2 XBogus 签名（默认关闭，已过期）
2. **Layer 1**：f2 CLI 直接调用（推荐，实测最稳）
3. **Layer 2**：iesdouyin 分享页解析
4. **Layer 3**：TikHub 付费 API（兜底）

如果全部失败，请检查 Cookie 是否过期（见下方 Cookie 问题）。

### Q: 小红书短链接失效？

**原因**：`xhslink.cn` 短链接有时效性，过期后会被风控跳转首页。

**解决**：使用完整 URL（包含 `xsec_token` 参数），不要使用短链接。

---

## Cookie 与认证

### Q: Cookie 多久失效？

抖音 Cookie 通常 **2-4 周**失效。失效后需要重新获取。

### Q: 如何判断 Cookie 是否失效？

| 信号 | 含义 |
|------|------|
| `APIUnauthorizedError` | f2 Layer 1 鉴权失败 |
| `"Fresh cookies needed"` | yt-dlp 检测到 Cookie 过期 |
| 分享页返回 403 或 HTML | iesdouyin 被风控 |
| TikHub 返回 401 | API Key 过期（非 Cookie 问题） |

### Q: 如何自动检测 Cookie 健康度？

```bash
python -m vidknot --check-cookie /path/to/douyin-cookies.txt
```

或每周一用 cron 定时检查：

```python
from vidknot.utils.cookie_health_check import check_cookie_health, write_health_flag
report = check_cookie_health("/path/to/douyin-cookies.txt")
write_health_flag("/path/to/flags", report)
```

### Q: Cookie 文件应该放在哪里？

推荐放在项目外的安全目录，**不要**放在仓库内：

```
~/credentials/douyin-cookies.txt   ✅ 推荐
./douyin-cookies.txt               ⚠️ 可以但容易误提交
```

---

## API 与配置

### Q: 必须配置哪些 API Key？

**最低配置**（可运行）：

```bash
SILICONFLOW_API_KEY=your_key    # 转写（国内直连）
OPENAI_API_KEY=your_key         # 笔记生成
```

**可选配置**：

```bash
FEISHU_APP_ID / FEISHU_APP_SECRET   # 飞书保存
OBSIDIAN_VAULT_PATH                  # Obsidian 保存
NOTION_TOKEN / NOTION_PAGE_ID        # Notion 保存
YUQUE_TOKEN / YUQUE_LOGIN            # 语雀保存
TIKHUB_API_KEY                       # 抖音兜底（付费）
```

### Q: 不想用 SiliconFlow，可以用其他 ASR 吗？

可以。SiliconFlow 是默认推荐（国内直连、免费额度），但你可以配置任何 OpenAI 兼容的 ASR 服务。

### Q: TikHub 是必须的吗？

**不是**。TikHub 是抖音 Layer 3 兜底，仅在所有免费层失败时使用。日常使用不需要配置。

### Q: 可以只用本地 faster-whisper 不用云端 ASR 吗？

可以。设置 `SILICONFLOW_API_KEY` 为空，VidkNot 会自动回退到本地 faster-whisper。首次运行需下载模型（约 500MB）。

---

## 输出与保存

### Q: 笔记保存到哪里？

通过 `--destination` 参数控制：

| 值 | 行为 |
|----|------|
| `obsidian`（默认） | 保存到 Obsidian Vault |
| `feishu` | 保存到飞书云文档 |
| `notion` | 保存到 Notion 页面 |
| `yuque` | 保存到语雀知识库 |
| `none` | 仅输出到终端，不保存 |

### Q: 不想保存，只想看结果？

```bash
python -m vidknot "URL" --destination none
```

### Q: 生成的笔记长什么样？

见下方 [示例输出](#示例输出)。

---

## 反模式（不要这样做）

### ❌ 不要提交 Cookie 或 API Key 到 Git

```bash
# 错误：把敏感信息提交到仓库
git add .env
git add douyin-cookies.txt

# 正确：确保 .gitignore 已包含这些文件
cat .gitignore  # 应包含 .env, *cookies*, *.key
```

### ❌ 不要用短链接处理小红书

```bash
# 错误：短链接可能过期或被风控
python -m vidknot "https://xhslink.com/xxx"

# 正确：使用完整 URL
python -m vidknot "https://www.xiaohongshu.com/explore/xxx?xsec_token=xxx"
```

### ❌ 不要把 TikHub 作为首选

```yaml
# 错误：TikHub 是付费服务，不应作为第一选择
douyin:
  preferred_api: tikhub

# 正确：让免费层优先，TikHub 仅兜底
douyin:
  enable_f2: true        # Layer 1 免费
  enable_iesdouyin: true # Layer 2 免费
  # Layer 3 TikHub 自动兜底
```

### ❌ 不要处理无授权的视频内容

- 只下载你有权访问的视频
- 遵守各平台服务条款
- 下载内容仅供个人学习研究，商用可能侵权

### ❌ 不要忽略 FFmpeg 安装

没有 FFmpeg，VidkNot 无法提取音频，所有平台都会失败。安装前不要浪费时间排查其他问题。

---

## 示例输出

运行以下命令：

```bash
python -m vidknot "https://v.douyin.com/example/" --destination none
```

生成的 Markdown 笔记结构如下：

```markdown
# [视频标题]

> 来源：https://v.douyin.com/example/
> 处理时间：2026-08-24 10:30:00

## 核心主题

本文讨论了...

## 要点

1. **第一个要点**：详细说明...
2. **第二个要点**：详细说明...

## 细节

- 支撑论点的数据和案例...

## 重要引用

> "原文引用内容..."

## 术语解释

| 术语 | 解释 |
|------|------|
| 术语1 | 解释... |

## 完整转写

- [00:00] 开场白...
- [00:30] 第一个话题...
- [05:00] 总结...
```

---

## 其他问题

如果以上没有覆盖你的问题，请：

1. 查看 [docs/EXPERIENCES.md](EXPERIENCES.md) 获取实战经验
2. 查看 [docs/DOUYIN_FALLBACK.md](DOUYIN_FALLBACK.md) 了解抖音 Fallback 详情
3. 查看 [docs/PLATFORMS.md](PLATFORMS.md) 了解平台支持矩阵
4. 通过 [GitHub Issues](https://github.com/suonian/vidknot/issues) 提交问题
