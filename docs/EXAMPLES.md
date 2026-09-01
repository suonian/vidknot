# VidkNot Research Platform — Examples

These examples illustrate how to plug user code into VidkNot's
framework modules. They contain **no real accounts or destinations**.

## 1. Custom backend

```python
# examples/custom_backend.py
from vidknot.core.backend import BackendStorage, NotePayload, StorageResult

class MarkdownDirBackend(BackendStorage):
    name = "markdown-dir"

    def __init__(self, config=None):
        super().__init__(config)
        self._dir = Path(self._config["directory"]).expanduser()

    def save(self, payload: NotePayload) -> StorageResult:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{payload.title}.md"
        path.write_text(payload.markdown, encoding="utf-8")
        return StorageResult(backend_name=self.name, location=str(path), ok=True)
```

## 2. Custom monitor task

```python
# examples/custom_task.py
from vidknot.core.monitor import MonitorTask

class MyDailyTask(MonitorTask):
    name = "my-daily-task"

    async def run(self) -> dict:
        # your fetch + classify logic here
        return {"items_seen": 0, "items_saved": 0}

# Register and run
from vidknot.core.monitor import TaskRegistry, MonitorScheduler

reg = TaskRegistry()
reg.register("my-daily-task", MyDailyTask)
scheduler = MonitorScheduler(registry=reg, interval_seconds=3600)
asyncio.run(scheduler.run_once())
```

## 3. Batch mode

```bash
# From a file (one URL per line)
vidknot batch --file urls.txt --destination sqlite

# From a sources file
vidknot batch --sources ~/.config/vidknot/sources.yaml
```

## 4. Sources file template

See `examples/sources.yaml.example` for a copy-able template.

## 5. Custom source validation

If your organization requires a stricter validation rule (e.g.
"all Douyin sources must include a `user_id` field"), subclass
`SourceConfig` and add a `validate` hook, or pre-process the loaded
bundle:

```python
from vidknot.core.source import load_sources_file, SourceConfig, SourceValidationError

bundle = load_sources_file("sources.yaml")
for s in bundle.sources:
    if s.platform == "douyin" and "user_id" not in s.extra:
        raise SourceValidationError(f"{s.name}: missing required 'user_id' for douyin")
```

## 6. 批量处理完整案例

**场景**：收集了 5 个视频链接，想一次性转成笔记存进 Obsidian，
个别失效链接不能拖垮整批任务。

第一步，准备 `urls.txt`（每行一个链接，支持空行和 `#` 注释）：

```text
# 2026-09 课程清单
https://www.youtube.com/watch?v=aaaa1111
https://www.bilibili.com/video/BV1xx411c7mD

# 抖音链接需要 cookies/douyin.txt 已配置
https://v.douyin.com/abc123/
https://www.xiaohongshu.com/explore/def456?xsec_token=xxx
https://weibo.com/tv/show/ghi789   # 未验证平台，可能失败
```

第二步，运行批处理：

```bash
vidknot --batch urls.txt -d obsidian --max-workers 3
```

行为约定：

- **逐条隔离**：单条失败只记录错误，不中断整批；结束后汇总
  `total / success / failed` 计数
- 并发数 1–8，默认 3；批量过大时建议保持默认以免触发平台风控
- Python API / MCP 等价入口：`pipeline.run_batch(urls, max_workers=3)`
  与 `batch_process(urls, ...)`，返回 JSON
  `{"total": 5, "success": 4, "results": [{url, success, title, error}, ...]}`

失败条目可在 `results` 里按 `error` 字段定位，常见是 Cookie 过期
或短链失效，单独修复后重跑该条即可。

## 7. 超长视频（>1 小时）分段处理完整案例

**场景**：一场 2 小时的访谈，直接处理容易下载超时、转写内存峰值高。

第一步，按内容章节把音频切成若干段（每段 ≤30 分钟为宜）：

```bash
# 用 ffmpeg 无损切段（只切音轨，不重编码画面）
ffmpeg -i interview.mp4 -vn -acodec copy audio_full.m4a
ffmpeg -i audio_full.m4a -f segment -segment_time 1800 -c copy part_%02d.m4a
```

第二步，把切片目录当本地批处理：

```bash
vidknot --batch-dir ./parts/ -d obsidian
```

配套调整：

- `config.yaml` 中 `network.download_timeout` 调大到 1200–1800 秒
  （原片若仍需整段下载时生效）
- 转写引擎切到本地 `faster-whisper` + `large` 模型，避免云端长音频
  一次性计费峰值
- 各段笔记生成后，用 Obsidian 的 `[[双链]]` 或在笔记头部注明
  「本系列共 N 段」串起整体脉络

这些例子是框架性的。把你自己的链接、目标库和策略叠加上去即可。