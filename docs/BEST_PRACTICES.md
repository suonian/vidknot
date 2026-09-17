# VidkNot 最佳实践

本文档覆盖常见使用场景的优化建议，帮助你从「能用」到「好用」。
先从[快速开始](../SKILL.md#快速开始一分钟)入门后再看本文。

## 长视频分段策略

超过 1 小时的视频直接处理容易遇到下载超时或转录内存峰值。
推荐分段处理：

```bash
# 1. 无损切音频（只切音轨，不重编码）
ffmpeg -i long_video.mp4 -vn -acodec copy audio_full.m4a
ffmpeg -i audio_full.m4a -f segment -segment_time 1800 -c copy part_%02d.m4a

# 2. 按目录批处理（各段独立，逐段隔离）
vidknot --batch-dir ./parts/ -d obsidian

# 3. 笔记头部注明「本系列共 N 段」并用 Obsidian [[双链]] 串联
```

配合调整：

- `config.yaml` 中 `network.download_timeout` 调到 1200–1800 秒
- 启用本地 ASR（见下方[模型选择](#asr-模型选择与性能)），云端长音频一次性计费峰值高

## ASR 模型选择与性能

| 场景 | 引擎 | 模型 | 预期耗时（10 分钟音频） | 建议 |
| --- | --- | --- | --- | --- |
| 日常使用、普通话为主 | SiliconFlow SenseVoice | 免费模型 | ~30 秒 | 默认选择，国内直连 |
| 中英混合、专业术语多 | SiliconFlow + faster-whisper | siliconflow + small | ~3 分钟 | 双 ASR 校正（v4 保守策略） |
| 方言/噪音大/极高质量要求 | faster-whisper 单源 | medium 或 large-v3 | ~10–20 分钟 | `config.yaml` 切到 `large` + `device: cpu` + `compute_type: int8` |
| 完全离线环境 | faster-whisper 单源 | small | ~2 分钟 | `SILICONFLOW_API_KEY=""` 自动回退本地 |

> **性能提示**：首次使用 faster-whisper 会下载模型（small 约 500MB，large 约 3GB）。
> 国内用户建议 `export HF_ENDPOINT=https://hf-mirror.com` 走镜像加速下载。

## 批处理并发调优

批量处理几十个链接时的经验值：

```bash
# 少量（<10 个）：默认并发 3 即可
vidknot --batch urls.txt -d obsidian

# 中等（10–30 个）：适当提高到 4–5，注意平台风控
vidknot --batch urls.txt -d obsidian --max-workers 4

# 大量（>30 个）：保持默认 3，分批跑，两次之间间隔 5–10 分钟
```

批处理行为约定：

- **逐条隔离**：单条失败只记录错误不中断整批，结束后输出 `total/success/failed` 计数
- 失败条目可在输出 JSON 中按 `error` 字段定位，常见原因：Cookie 过期、短链失效、网络超时
- Python API 等价入口：`pipeline.run_batch(urls, max_workers=3)`，返回同样结构
- `urls.txt` 支持 `#` 注释与空行，方便按主题分组管理链接

## 网络与镜像

### 加速依赖下载

```bash
# pip 安装时指定清华镜像（覆盖 yt-dlp / faster-whisper 等海外包）
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
  "vidknot @ git+https://github.com/suonian/vidknot.git@v0.6.6"

# 或一键脚本（自动探测镜像）
bash scripts/install.sh
```

### 加速模型下载

```bash
# 本地 ASR 模型默认从 Hugging Face CDN 拉取，国内可走镜像：
export HF_ENDPOINT=https://hf-mirror.com
# 设置一次即可，后续运行会自动使用缓存
```

### 代理配置

各平台 API 通常直连，如需全局代理：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

GitHub 仓库克隆/安装也可用代理或镜像站（如 `ghproxy.com`）。

## Cookie 管理最佳实践

- **放在仓库外**：`~/credentials/douyin-cookies.txt`，避免误提交到 Git
- **按平台命名**：`cookies/douyin.txt`、`cookies/bilibili.txt`
- **定期更新**：抖音 Cookie 约 2–4 周失效，设日历提醒更新
- **健康检查**：

```bash
python -m vidknot --check-cookie cookies/douyin.txt
```

- **自动导出**：浏览器扩展（如 Get cookies.txt LOCALLY）一键导出 Netscape 格式
- **YouTube/Vimeo/通用链接无需 Cookie**；TikTok/Twitter/X/Instagram 直接复用 Chrome 已登录 Cookie（`--cookies-from-browser`）

## 排障工作流

遇到问题时按这个顺序自查，80% 的报错能定位：

1. **环境自检**：`python -m vidknot --check-env`（缺什么装什么）
2. **FFmpeg**：`ffmpeg -version`，没有就 `brew install ffmpeg` 或 `pip install 'vidknot[bundled-ffmpeg]'`
3. **API Key**：`.env` 里 `SILICONFLOW_API_KEY` 是否有效
4. **Cookie 健康**：`python -m vidknot --check-cookie` 看是否过期
5. **网络**：`curl -I https://api.siliconflow.cn` 确认可达；必要时配代理
6. **链接有效性**：用 `yt-dlp -F <URL>` 单独测试解析（不消耗转写额度）
7. **看错误提示**：VidkNot 的异常自带 `hint` 修正建议，CLI 也会直接打印
8. **查 FAQ**：[错误速查表](FAQ.md#错误速查表) 区了分临时故障/配置错误/能力边界，按类型处理

### 典型场景排查

**「下载失败 / 403」**
- 确认不是付费/会员/仅粉丝可见内容（判断标准见 [PLATFORMS.md](PLATFORMS.md)）
- Cookie 是否过期（抖音 2–4 周必换）
- 网络是否可达：`curl -I <视频平台域名>`

**「笔记生成失败」**
- LLM API Key 是否配置：`.env` 中 `LLM_API_KEY` 与 `LLM_BASE_URL`
- 余额是否充足
- 切换 provider：`config.yaml` 中 `processors.llm_provider` 改模型

**「转写不准」**
- 尝试双 ASR 校正：`config.yaml` `enable_correction: true`
- 切到 `faster-whisper large` 模型（需下载 ~3GB）
- 确认视频语言参数：`-l zh` 或 `-l en`

## 多 Agent 共享仓库

如果多个智能体共用 VidkNot 项目仓库（如一个负责修 Bug、一个负责发版），建议：

1. **使用独立分支**：每人推自己的 `fix/*` 分支，通过 PR 合并
2. **避免同时操作 main**：合并前 PR 必须 CI 全绿
3. **Token 隔离**：不同智能体用各自的 GitHub PAT（最少权限原则）
4. **版本发布串行**：发版前 `gh pr list` 确认没有未合并的修复分支