# VidkNot Platform Support Matrix

VidkNot is a **general information retrieval and research framework**.
This document records which platforms have a working download / parse
path as of the current release, and which require user-supplied data
(cookies, accounts, etc.).

> **Framework-only philosophy**: VidkNot ships interfaces and
> reference implementations. Concrete account lists, cookies, and
> destination identifiers live in user-supplied configuration. See
> `docs/PRIVACY.md`.

---

## Quick matrix

| Platform | Type | Download status | Cookie dependency | Notes |
| --- | --- | --- | --- | --- |
| 抖音 (Douyin) | Short video | ✅ **Layer 1 verified** | 可选（显著提升成功率）：自动 CDP / browser_cookie3 / Netscape 文件 | 四层 fallback。See `docs/DOUYIN_FALLBACK.md`. |
| B站 (Bilibili) | Long / short video | ⚠️ Framework ready | 推荐：`cookies/bilibili.txt`（无 Cookie 时自动回退浏览器导出） | 字幕优先策略；依赖 yt-dlp 提取器。 |
| 小红书 (Xiaohongshu) | Image + short video | ✅ Image + video URLs extracted from `__INITIAL_STATE__` (v0.3.3) | 需要登录 Cookie（web_session/a1 等）；图片笔记必须保留 `xsec_token` | 短链 `xhslink.cn/com` 自动 302 解析。 |
| YouTube | Long-form video | ✅ Stable | 可选：`cookies/youtube.txt`；无 Cookie 时走 SABR bypass（android+web client） | 字幕优先策略默认开启。 |
| Vimeo | Long-form video | ✅ Stable | 不需要 | yt-dlp standard path. |
| TikTok | Short video | ✅ Stable | Chrome 浏览器 Cookie（`--cookies-from-browser`，需已登录） | International, no XBOGUS required. |
| Twitter / X | Short video | ✅ Stable | Chrome 浏览器 Cookie（需已登录） | yt-dlp. |
| Instagram (Reels) | Short video | ✅ Stable | Chrome 浏览器 Cookie；私密内容需已登录并关注 | yt-dlp. |
| 视频号 (WeChat Channels) | Short video | ⚠️ 预留（暂不可自动化） | 不适用 | 微信封闭生态；用 res-downloader 等抓包工具导出后走本地批处理。 |
| 快手 (Kuaishou) | Short video | ⚠️ Framework ready | 可选：`cookies/kuaishou.txt` | 依赖 yt-dlp 支持，未做实战验证。 |
| 微博 (Weibo) | Short video | ⚠️ Framework ready | 可选：`cookies/weibo.txt` | 依赖 yt-dlp 支持，未做实战验证。 |
| 其他任意链接 | Generic | ✅ 兜底 | 不需要 | 走 yt-dlp 通用提取，成功率视目标站而定。 |

> **Cookie 获取方式**：见根目录 `COOKIE_GUIDE.md`（浏览器扩展导出 Netscape 格式，
> 放到 `cookies/<平台名>.txt`）。⚠️ 平台未经实战验证不代表不可用，
> 仅代表当前版本未包含真实链接回归记录。

---

## 时长与文件大小约束

| 场景 | 建议 |
| --- | --- |
| 短视频（<10 分钟） | 默认配置即可，批量处理用 `--batch`（默认并发 3） |
| 中等时长（10–20 分钟） | 默认配置即可；Dual-ASR 校正耗时约为音频时长 0.5–1 倍 |
| 长视频（>20 分钟） | 建议 `config.yaml` 中切到 `faster-whisper` + `large` 模型；下载超时在 `network.download_timeout`（默认 600s）按需调大 |
| 超长（>1 小时） | 建议先手动切片分段处理，避免单次转录内存峰值 |

- 下载超时 / 重试统一由 `config.yaml` 的 `network:` 段控制（见 `docs/CONFIG.md`）。
- 转写与笔记生成为纯音频处理，**不上传视频画面**，只关心音轨大小。

---

## 付费 / DRM 内容判断标准

VidkNot **不支持**以下内容的提取，遇到时请直接告知用户而不是重试：

| 判断标准 | 典型特征 |
| --- | --- |
| 会员专属 | 播放页显示「会员专享」「VIP」「大会员」；未登录试看 6 分钟 |
| 付费合集 / 单集付费 | 显示「付费观看」「已购」「￥xx 解锁」 |
| 仅粉丝可见 | 「仅粉丝可见」「加入粉丝团」提示 |
| DRM 保护 | yt-dlp 报 `DRM` / `Widevine` / `no supported formats` |
| 私密内容 | 需要授权关系（互关/白名单）才能打开 |

识别信号（下载阶段）：

- 错误信息包含 `登录` / `权限` / `403` / `鉴权` → 大概率是授权问题而非网络问题
- 只拿到 6 分钟试看音频 → 该视频是会员内容，停止处理
- 解析出的直链返回 `403 Forbidden` → Cookie 过期或内容受限

---

## 第三方 API 兜底（**付费**）💰

所有平台通用。**仅当免费层（yt-dlp / f2 / iesdouyin）全部失败**时启用。

### TikHub（推荐第三方）

| 项 | 值 |
|---|---|
| **大陆端点（推荐）** | **`https://api.tikhub.dev`** ✅ 国内直连无需代理 |
| 国际端点（旧版，需代理） | `https://api.tikhub.io` |
| 覆盖平台 | 抖音 / B站 / 小红书 / YouTube / 微博 / 快手 / TikTok |
| 计费 | 按调用次数付费 |
| 环境变量 | `TIKHUB_API_KEY` |
| 推荐用途 | 兜底 / 关键样本 / 小批量 |

启用方式：
```yaml
douyin:
  enable_third_party: true
  third_party_provider: tikhub
```

**实战原则**：
- ❌ **不要**作为默认首选
- ❌ **不要**在批量任务里无脑开
- ✅ **仅当**免费层全部失败时启用

### 其他第三方

- **Evil0ctal/Douyin_TikTok_Download_API**：自部署版本，默认地址 `http://localhost:80`
- **apibyte / canxiang / alapi**：功能分散，不推荐

---

## 各平台详细说明

### 抖音 (Douyin) ✅

**已验证链路**：`f2 dy --mode one` + Netscape cookie。

详细四层 fallback + 实战时间预算，见 [`docs/DOUYIN_FALLBACK.md`](DOUYIN_FALLBACK.md)。

### B站 (Bilibili) ⚠️

**状态**：框架已注册，依赖 yt-dlp 的 B站提取器。

```bash
yt-dlp --cookies cookies/bilibili.txt \
       -f "bv*[height<=720]+bestaudio" \
       "https://www.bilibili.com/video/BVxxxxx"
```

需要用户自行导出 B站 cookie 文件。

### 小红书 (Xiaohongshu) ✅

**v0.3.3 实现**：
- 图片笔记：4 个 bug 已修复（含 `xhslink.cn` 短链、`xsec_token`、`sns-webpic-qc.xhscdn.com` CDN）
- 视频笔记：直链下载（`__INITIAL_STATE__.note.video.media.stream.h264[0].masterUrl`）

**实战要点**：图片笔记必须带 `xsec_token`，视频笔记通常不需要。

### YouTube ✅

`yt-dlp` 原生支持，最成熟路径。字幕优先策略默认开启。
无 Cookie 时自动启用 SABR bypass（`player_client=android,web`）。

### 视频号 ⚠️

无公开 API，需要浏览器抓取或用户提供的视频源。

---

## 平台扩展流程（贡献者指南）

要加新平台，需要：

1. **实现 `Platform` 协议** — `src/vidknot/core/platforms/<name>.py`
2. **提供下载函数** — `download(url, ...) -> (path, metadata)`
3. **加测试** — `tests/test_platforms.py::Test<Name>Platform`
5. **更新本表** — 在 matrix 加一行

接口定义见 `src/vidknot/core/platforms/base.py`。

---

## 已知限制

- ❌ **付费 / 会员内容**：所有平台都无解（判断标准见上文）
- ❌ **直播流**：实时 m3u8/HLS 需要单独处理
- ❌ **DRM 保护**：所有平台都不支持
- ⚠️ **私密笔记**（小红书）：即便有 Cookie 也可能被风控
- ⚠️ **批量整页爬取**：当前只支持单链接

---

*最后更新：2026-08-31（v0.6.0 评估优化：补 Cookie 依赖列、时长约束、付费内容判断标准；视频号状态如实更正为预留）*
