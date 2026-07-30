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
