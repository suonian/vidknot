# Cookie 使用说明

Cookie 用于处理需要登录态或被平台风控的视频链接。Cookie 等同于登录凭证，不要提交到 Git，也不要分享给他人。

## 什么时候需要 Cookie

| 平台 | 常见情况 |
| --- | --- |
| 抖音 | 短链解析失败、登录态内容、请求被风控 |
| YouTube | 年龄限制、会员内容、地区限制 |
| Bilibili | 大会员内容、登录可见内容 |
| TikTok / X / Instagram | 多数登录态内容 |

公开视频不一定需要 Cookie。只有在下载或解析失败时再配置。

## 推荐格式

推荐使用 Netscape `cookies.txt` 格式，这是 yt-dlp 和 VidkNot 最通用的格式。

示例：

```text
# Netscape HTTP Cookie File
.douyin.com	TRUE	/	TRUE	1735689600	sessionid	xxxxxxxxxx
```

## 获取方式

推荐用 Chrome 扩展导出：

1. 在浏览器中登录目标平台
2. 安装能导出 Netscape `cookies.txt` 的 Cookie 扩展
3. 打开目标平台页面
4. 导出 Cookie 文件
5. 保存到本地非仓库目录，或保存到仓库中已忽略的 `cookies/` 目录

示例目录：

```text
cookies/
├── douyin.txt
├── youtube.txt
└── bilibili.txt
```

## 配置 VidkNot

抖音 Cookie 文件：

```bash
VIDKNOT_DOUYIN_COOKIE_FILE=/absolute/path/to/douyin.txt
```

通用 yt-dlp 场景可直接在浏览器导出后交给下载器使用；如果后续增加平台专用变量，应以 `.env.example` 和 `config.yaml` 为准。

## 验证

先用 `--destination none` 验证解析和转写，不写入任何知识库：

```bash
python -m vidknot "https://v.douyin.com/example/" --destination none --no-cache
```

## 安全

- `.gitignore` 已排除 `.env`、`cookies/` 和运行缓存
- Cookie 过期后重新导出
- 发现异常登录或泄露风险时，退出平台登录并重新生成 Cookie
- 不要把 Cookie 粘贴到公开 issue、聊天记录或文档中

---

## VidkNot 当前能力地图

> 记录时间：2026-08-10｜对应版本：v0.3.2 + 本次修复

### ✅ 已实现（可直接使用）

#### 视频下载平台

| 平台 | 下载方式 | 实测状态 | 备注 |
| --- | --- | --- | --- |
| YouTube | yt-dlp | ✅ 稳定 | 最成熟，字幕/视频/播放列表均支持 |
| B 站 (bilibili) | yt-dlp + 平台增强 | ✅ 稳定 | 支持弹幕/字幕/分P |
| 抖音 (douyin) | Layer 1 iesdouyin 直采 + Cookie | ✅ 可用 | Layer 1/2/3 兜底链已加固 |
| TikTok | yt-dlp | ✅ 可用 | 国际版，X-Bogus 不强制 |
| Twitter / X | yt-dlp | ✅ 可用 | 视频/GIF |
| Instagram | yt-dlp | ✅ 可用 | Reels/帖子视频，需登录Cookie |
| Vimeo | yt-dlp | ✅ 可用 | |
| 微信视频号 | 平台实现 | ✅ 可用 | |

#### 笔记型平台（图片/混合）

| 平台 | 类型 | 实测状态 |
| --- | --- | --- |
| 小红书 | 图片笔记（图集） | ✅ 4 个 Bug 已修复，涠洲岛 12 张 / AI+Obsidian 1 张 端到端验证通过 |
| 小红书 | 视频笔记 | ⚠️ 部分可用，依赖 `__INITIAL_STATE__.note.video` 解析 + Cookie，yt-dlp 兜底可能失败 |

#### 其他已注册平台

| 平台 | 实测状态 |
| --- | --- |
| 快手 (kuaishou) | ⚠️ 框架已注册，依赖 yt-dlp 对快手的支持度 |
| 微博 (weibo) | ⚠️ 框架已注册，依赖 yt-dlp 对微博的支持度 |

#### 通用兜底

- **GenericPlatform**：未匹配平台时用 yt-dlp 兜底，能下就下

### ❌ 不能实现 / 受限

#### 抖音

- ❌ **Layer 0 (f2 XBogus 自动签名)**：f2 0.0.1.7 的 X-Bogus 算法已被抖音更新，签名后 API 返回空 body。需要等 f2 项目复活，或迁移到 Evil0ctal/Douyin_TikTok_Download_API 自部署实例
- ❌ **零依赖纯开源签名**：当前不存在持续维护的开源 X-Bogus 实现
- ⚠️ **风控后无 Cookie**：请求被风控又无 Cookie 时只能失败，需准备 `VIDKNOT_DOUYIN_COOKIE_FILE`

#### 小红书

- ❌ **视频笔记**（当前最大缺口）：`__INITIAL_STATE__.note.video` 字段需要登录 Cookie + xsec_token 才能稳定获取；yt-dlp fallback 常因 X-Bogus 失败。下一阶段重点处理
- ❌ **私密笔记**：即便有 Cookie 也可能被风控拦截
- ❌ **批量下载 / 整页爬取**：当前架构只支持单链接

#### 全局限制

- ❌ **付费 / 会员内容**：所有平台都无法下载
- ❌ **直播流**：当前架构不支持（实时流需要 m3u8/HLS 单独处理）
- ❌ **DRM 保护内容**：所有平台均不支持

### 抖音四层 Fallback 当前状态

```
Layer 0: f2 XBogus 签名（scripts/f2_helper.py） ──────── ⚠️ 结构就绪，签名算法已过期
        ↓ 失败
Layer 1: iesdouyin 直采 + Cookie（douyin_parser）  ────── ✅ 工作
        ↓ 失败
Layer 2: yt-dlp + Cookie ─────────────────────────────── ✅ 工作
        ↓ 失败
Layer 3 (opt-in): 第三方 API ────────────────────────── ✅ 端点已切换 api.tikhub.dev 大陆直连
                  (apibyte / canxiang / alapi / tikhub)   默认关闭，按需开启
```

### 一句话总结

> 视频类平台全部可用（yt-dlp 成熟路线）；小红书图片已修好；抖音依赖 Cookie 但已加固；小红书视频 / 抖音 X-Bogus 纯开源签名 这两项是行业级未解难题，需要 Cookie 或第三方 API 辅助。
