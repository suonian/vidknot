# VidkNot Douyin Fallback Strategy (实战指南)

VidkNot 在抓取抖音视频时使用**四层 fallback**。每层都是**免费/低成本优先**的，最后一层（TikHub）才是**付费兜底**。

> **实战结论（2026-08-10 Codex 任务）**：
> 实测 7 篇视频 + 1 篇已有素材 = 8 篇全部走 Layer 1 `f2 dy --mode one` 成功。
> Layer 0/2/3 **未触发**，但框架完整保留。

---

## 四层 Fallback 链

```
Layer 0: f2 XBogus 签名（结构就绪，⚠️ 算法已过期）
   ↓ 失败
Layer 1: f2 dy --mode one（推荐路径，iesdouyin + Cookie）  ✅ 实战验证
   ↓ 失败
Layer 2: yt-dlp + Cookie（broken 兜底）
   ↓ 失败
Layer 3 (opt-in): 第三方 API 兜底（**收费**）  💰
```

---

## Layer 0：f2 XBogus 签名

**状态**：⚠️ **结构就绪，签名算法已过期**

`scripts/f2_helper.py` 已存在，调用 f2 库的 `XBogusManager.str_2_endpoint` 自动签名 POST_DETAIL URL，通过 `.venv-f2` 隔离依赖。

**问题**：f2 0.0.1.7 的 XBOGUS 算法已被抖音更新，签名后 API 返回空 body。需要等 f2 项目复活，或迁移到 Evil0ctal 自部署。

**实战选择**：**默认关闭**（`enable_f2: false`），节省 200ms 启动时间。

---

## Layer 1：`f2 dy --mode one`（推荐路径）✅

**状态**：✅ **实战验证成功**（2026-08-10）

### 工作原理

f2 CLI 的 `--mode one` 子命令：
1. 解析 `https://www.iesdouyin.com/share/video/<aweme_id>/` 分享页
2. 用 Cookie + 移动端 UA 获取无水印视频直链
3. 下载到 `<output_dir>/douyin/one/<author>/<date>_<title>_video.mp4`

### 调用方式（封装在 `scripts/f2_helper_cli.py`）

```python
from scripts.f2_helper_cli import download_one

result = download_one(
    aweme_id="7636872072064470298",
    cookie_file="/home/ubuntu/vidknot/cookies/douyin.txt",
    output_dir="/tmp/downloads",
)
# → F2DownloadResult(video_path=Path(...), aweme_id='...', title='...', author='...')
```

### 直接 CLI 调用（备选）

```bash
COOKIE=$(python3 -c "
with open('/home/ubuntu/vidknot/cookies/douyin.txt') as f:
    parts = []
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'): continue
        fields = line.split('\t')
        if len(fields) >= 7:
            parts.append(fields[5] + '=' + fields[6])
    print('; '.join(parts))
")

/home/ubuntu/f2env/bin/f2 dy \
    --url "https://www.iesdouyin.com/share/video/<aweme_id>/" \
    --mode one \
    -p /tmp/downloads \
    -k "$COOKIE"
```

### 注意事项

- **Bark 通知可能报 405**（无配置 key 导致），不影响下载
- **f2env 必须存在**（`/home/ubuntu/f2env/bin/f2`），否则 `F2DownloadError`
- **下载路径格式**：`<path>/douyin/one/<作者昵称>/<日期_标题_video.mp4>`

---

## Layer 2：yt-dlp + Cookie

**状态**：⚠️ **broken，作为兜底保留**

yt-dlp 的 Douyin 提取器在 2026-03 版本后报错：
```
ERROR: [Douyin] <aweme_id>: Fresh cookies (not necessarily logged in) are needed
```

即使提供有效 Netscape cookie 文件、自定义 User-Agent、禁用代理均无法解决。

**根因**：抖音网页版对服务器端请求返回验证码中间页（HTML 含 `sec_sdk_build/captcha/index.js`）。

**实战选择**：**不推荐**——除非 Layer 1 完全失败。

---

## Layer 3：第三方 API 兜底（**付费**）💰

**状态**：⚠️ **付费服务，仅作兜底**

### TikHub（推荐第三方）

| 项 | 值 |
|---|---|
| **大陆端点（推荐）** | **`https://api.tikhub.dev`** ✅ 直连无需代理 |
| **国际端点（旧版）** | `https://api.tikhub.io` 需 mihomo proxy |
| 用途 | 抖音 / B站 / 小红书 / YouTube / 微博 / 快手 / TikTok 视频元数据 + 下载 |
| 计费 | 按 API 调用次数付费（具体见 tikhub.dev 定价） |
| 环境变量 | `TIKHUB_API_KEY` |

**启用方式**：
```yaml
douyin:
  enable_third_party: true
  third_party_provider: tikhub
```

**实战原则**：
- ❌ **不要**作为默认首选
- ❌ **不要**在批量任务里无脑开
- ✅ **仅当** Layer 0/1/2 全部失败时启用
- ✅ **仅当** 单次小批量（如 1-3 篇关键样本）时使用

### 其他第三方（不推荐）

- **apibyte / canxiang / alapi**：功能分散，文档参差，维护不稳
- **Evil0ctal/Douyin_TikTok_Download_API**：自部署版本，需自行运维（默认地址 `http://localhost:80`）

---

## Cookie 健康度管理

Cookie 通常 **2-4 周失效**。失效后 Layer 1/2 全部失败，必须重新导出。

**自动化方案**（`src/vidknot/utils/cookie_health_check.py`）：

```python
from vidknot.utils.cookie_health_check import check_cookie_health, write_health_flag

# 周一早上 08:30 cron
report = check_cookie_health("/home/ubuntu/vidknot/cookies/douyin.txt")
write_health_flag("/tmp/cookie_flags", report)

if report.status.value == "expired":
    notify_operator("Douyin cookie 已失效，请重新导出")
```

**判断标准**：
- `200` → `healthy`
- `403` / `404` / 网络超时 → `expired`
- `5xx` → `warning`（临时网络问题）
- Cookie 文件不存在 → `expired`

---

## ASR 网络问题

### mp4 格式陷阱

**SiliconFlow API 不接受 mp4 格式**（SUPPORTED_FORMATS 无 .mp4）。下载后必须 ffmpeg 转 mp3：

```bash
ffmpeg -y -i video.mp4 -vn -acodec libmp3lame -q:a 5 \
    -f segment -segment_time 60 chunk_%03d.mp3
```

按 60 秒切分，每段 < 2 MB，ASR 上传稳定。

### OpenAI 国际 API 完全不可达

`api.openai.com` 在国内**网络不可达**（Network unreachable） + `.env` 无 `OPENAI_API_KEY`。

**fallback_provider 默认 `openai_whisper` 在 config.yaml 是误导**——永远不会成功。

**实战建议**：改用 `faster_whisper` 本地或保持 `subtitle_first` 策略。

---

## 实战时间预算（参考）

**8 篇视频笔记（Codex 任务）实测时间**：

| 步骤 | 时间 |
|---|---|
| 弹药库选样本 | < 1 分钟 |
| f2 dy --mode one 下载（7 篇）| 约 2-3 分钟 |
| ffmpeg 转码切分（每篇）| 10-15 秒 |
| SiliconFlow ASR（每篇前 20 段）| 30-60 秒 |
| 飞书文档创建（每篇）| 2-3 秒 |
| 飞书内容写入 + 权限（每篇）| 3-5 秒 |
| **总计** | **约 15-20 分钟** |

---

## 下一步优化方向

1. **mp4 → mp3 自动转码**集成到 download_manager
2. **官方字幕优先**（小红书/B站/YouTube）
3. **跨平台凭证隔离 v2**（process_only 完整版）
4. **Cookie 健康度自动通知**（飞书群消息）

---

*最后更新：2026-08-10 by 小云（Hermes agent）*
*实战基于 Codex `write-ai-spoken-scripts` skill 测试任务*