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

| Platform | Type | Download status | Notes |
| --- | --- | --- | --- |
| 抖音 (Douyin) | Short video | ✅ **Layer 1 verified** | `f2 dy --mode one` + Netscape cookie. See `docs/DOUYIN_FALLBACK.md`. |
| B站 (Bilibili) | Long / short video | ⚠️ Framework ready | Requires user B站 cookie. Use `yt-dlp` with the cookie file. |
| 小红书 (Xiaohongshu) | Image + short video | ✅ Image + video URLs extracted from `__INITIAL_STATE__` (v0.3.3) | Image download needs cookie + `xsec_token`. Video direct link works without cookie in many cases. |
| YouTube | Long-form video | ✅ Stable | yt-dlp standard path. Subtitles first. |
| Vimeo | Long-form video | ✅ Stable | yt-dlp standard path. |
| TikTok | Short video | ✅ Stable | yt-dlp. International, no XBOGUS required. |
| Twitter / X | Short video | ✅ Stable | yt-dlp. |
| Instagram (Reels) | Short video | ✅ Stable | yt-dlp, needs cookie for private. |
| 视频号 (WeChat Channels) | Short video | ✅ | Requires cookie for non-public videos. |
| 快手 (Kuaishou) | Short video | ⚠️ Framework ready | Depends on yt-dlp support. |
| 微博 (Weibo) | Short video | ⚠️ Framework ready | Depends on yt-dlp support. |

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

- ❌ **付费 / 会员内容**：所有平台都无解
- ❌ **直播流**：实时 m3u8/HLS 需要单独处理
- ❌ **DRM 保护**：所有平台都不支持
- ⚠️ **私密笔记**（小红书）：即便有 Cookie 也可能被风控
- ⚠️ **批量整页爬取**：当前只支持单链接

---

*最后更新：2026-08-10 by 小云（Hermes agent）*