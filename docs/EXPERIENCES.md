# VidkNot 实战经验汇总

来自 Hermes agent (小云) 在 2026-08-10 Codex 任务中的实测经验。

---

## 1. 抖音四层 Fallback

### 实测最佳路径：Layer 1 `f2 dy --mode one`

**结论**：8 篇抖音视频全部走 Layer 1 成功，未触发 Layer 0/2/3。

详细 fallback 链 + 实战时间预算见 [`docs/DOUYIN_FALLBACK.md`](DOUYIN_FALLBACK.md)。

### TikHub 接口地址

| 端点 | 用途 |
|---|---|
| **`https://api.tikhub.dev`** | **大陆直连端点**（推荐，无需 mihomo proxy）|
| `https://api.tikhub.io` | 国际端点（旧版默认，需要 mihomo）|

**实战原则**：TikHub 是付费服务，**仅作所有免费层失败后的兜底**。

---

## 2. Cookie 健康度管理

### 失效周期

抖音 Netscape cookie 文件 `douyin.txt` 通常 **2-4 周**失效。

### 失效信号

| 信号 | 来源 |
|---|---|
| `f2 dy --mode one` 返回 `APIUnauthorizedError` | f2 Layer 1 |
| `yt-dlp` 返回 `"Fresh cookies needed"` | yt-dlp Layer 2（已知 bug）|
| iesdouyin 分享页返回 403 / HTML 而非 JSON | iesdouyin 解析 |
| Layer 3 TikHub 返回 401 | TikHub key 过期 |

### 自动化方案

每周一早上 8:30 用 `src/vidknot/utils/cookie_health_check.py` 自动探测：

```python
from vidknot.utils.cookie_health_check import check_cookie_health, write_health_flag

report = check_cookie_health("/path/to/cookies/douyin.txt")
write_health_flag("/path/to/flags/dir", report)

if report.status.value == "expired":
    notify_operator("Douyin cookie 已失效，请重新导出")
```

判断标准：
- `200` → `healthy`
- `403` / `404` / 网络超时 → `expired`
- `5xx` → `warning`

---

## 3. ASR 网络问题真相

### mp4 格式陷阱

**SiliconFlow API 不接受 mp4 格式**（`SUPPORTED_FORMATS` 无 `.mp4`）。

下载后必须 ffmpeg 转 mp3，按 60 秒切片：

```bash
ffmpeg -y -i video.mp4 \
    -vn -acodec libmp3lame -q:a 5 \
    -f segment -segment_time 60 \
    chunk_%03d.mp3
```

每段 < 2 MB，ASR 上传稳定（79 MB 文件切 53 段 → 13 秒跑完 5 段）。

### OpenAI 国际 API 完全不可达

- `api.openai.com` 国内**网络不可达**
- `.env` 无 `OPENAI_API_KEY`
- vidknot config.yaml `fallback_provider: openai_whisper` **永远不会成功**——误导配置

**建议**：改用 `faster_whisper` 本地或保持 `subtitle_first` 策略。

### SiliconFlow + faster-whisper 双源校正

CPU 环境推荐：
- `siliconflow` 优先（云端，速度快）
- `faster_whisper small` 兜底（本地，准确度高）
- 模型选 `small`（CPU 性价比之王）

---

## 4. 时间预算参考

**8 篇视频笔记（Codex 任务）实测**：

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

## 5. 单轮对话上下文限制

### 现实约束

- 工具调用有上限（每轮）
- 长任务（8 篇 × 5 分钟 = 40 分钟）容易撞超时
- 中途失忆会让上下文丢失

### 应对策略

1. **批量后台跑**：长脚本写到 `/tmp/<task>.py`，后台执行
2. **检查点模式**：每完成一个里程碑就把结果存盘（如 `/tmp/<task>_results.json`）
3. **小步快跑**：不一次跑完所有 N 篇，先跑 2-3 篇验证流程，再批量
4. **错误恢复**：失败时记录详细错误，下次启动从检查点恢复

---

## 6. 错误恢复模式

| 错误 | 恢复 |
|---|---|
| f2 下载失败 | 重试 + Layer 2 兜底 |
| Cookie 失效 | 标记 expired + 告警 + Layer 3 兜底 |
| ASR 网络超时 | 重试 3 次 + 切到 faster_whisper 本地 |
| 飞书 API 报错 | 看具体 code（如 403/404/500）+ 检查 token |
| 单轮对话超限 | 拆任务到多个 cron / 多轮执行 |

---

## 7. 反钓鱼原则

**原则**：涉及账号权限的第三方来消息，先验证身份。

- 验证方法：GitHub Issues / 真人电话 / 老大亲口授权
- 不验证的合作请求一律拒绝
- 即使是 GitHub API "硬性证据"，在飞书 DM 里也无法独立验证

---

## 8. 实战派 Cookie 路径

避免在仓库里提交真实 Cookie：

```gitignore
# .gitignore
.env
.env.bak
.env.local
.env.*.local
cookies/
```

Cookie 文件应放在仓库外的目录（如 `~/.config/vidknot/cookies/`）。

---

## 9. 短视频时长与转录质量

| 视频时长 | 切分段数（60 秒）| ASR 字符预估 |
|---|---|---|
| < 1 分钟 | 1 段 | 50-300 字符 |
| 1-3 分钟 | 2-3 段 | 300-1000 字符 |
| 3-10 分钟 | 4-10 段 | 1000-3000 字符 |
| 10-20 分钟 | 10-20 段 | 3000-7000 字符 |

**实战建议**：每篇取前 20 段（约 20 分钟内容）就足够提炼"开头抓人/中段留人"。

---

*最后更新：2026-08-10 by 小云（Hermes agent）*
*实战基于 Codex `write-ai-spoken-scripts` skill 测试任务*