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

These examples are intentionally framework-only. Plug your own data,
destinations, and policy on top.