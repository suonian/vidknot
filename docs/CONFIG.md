# Configuration Reference

VidkNot reads configuration from three sources, in priority order:

1. **Process environment** (`VIDKNOT_*` and other variables)
2. **User config file** — explicit path passed via `--config`
3. **Built-in defaults** shipped in `config.yaml`

The framework never searches `~/.config/`, `~/Library/`, or any other
implicit location. All paths are explicit.

## Loading order

```python
from vidknot.utils.config_manager import ConfigManager

cm = ConfigManager()                              # uses config.yaml in CWD
cm = ConfigManager(config_path="/etc/vidknot.yaml")  # explicit override
```

Configuration is merged via deep merge; process env always wins.

## Environment variables

| Variable                       | Config path                                  |
| ------------------------------ | -------------------------------------------- |
| `VIDKNOT_LANGUAGE`             | `settings.language`                          |
| `VIDKNOT_DEFAULT_DESTINATION`  | `settings.default_destination`               |
| `VIDKNOT_ENABLE_CORRECTION`    | `settings.enable_correction`                 |
| `VIDKNOT_CORRECTION_VERSION`   | `settings.correction_version`                |
| `VIDKNOT_DOUYIN_COOKIE_FILE`   | `douyin.cookie_file`                         |
| `VIDKNOT_DOUYIN_ENABLE_THIRD_PARTY` | `douyin.enable_third_party`              |
| `TIKHUB_API_KEY`               | `douyin.tikhub.api_key`                      |
| `VIDKNOT_SQLITE_PATH`          | (consumed by `SqliteBackend`)                |
| `VIDKNOT_SOURCES_FILE`         | (consumed by `vidknot batch --sources`)     |
| `VIDKNOT_OBSIDIAN_VAULT_PATH`  | `obsidian.vault_path`                        |
| `VIDKNOT_FEISHU_APP_ID`        | `feishu.app_id`                              |
| `VIDKNOT_FEISHU_APP_SECRET`    | `feishu.app_secret`                          |
| `VIDKNOT_FEISHU_FOLDER_TOKEN`  | `feishu.folder_token`                        |
| `VIDKNOT_NOTION_TOKEN`         | `notion.token`                               |
| `VIDKNOT_NOTION_PAGE_ID`       | `notion.page_id`                             |
| `VIDKNOT_YUQUE_TOKEN`          | `yuque.token`                                |
| `VIDKNOT_YUQUE_LOGIN`          | `yuque.login`                                |
| `VIDKNOT_LLM_MODEL`            | `providers.openai-compatible.model`          |
| `LLM_BASE_URL`                 | `providers.openai-compatible.base_url`       |
| `LLM_API_KEY`                  | `providers.openai-compatible.api_key`        |
| `SILICONFLOW_API_KEY`          | `providers.siliconflow.api_key`              |

> Variables with the `VIDKNOT_*` prefix are reserved for the framework.
> Other variables follow OpenAI-compatible conventions (e.g. `LLM_*`).

## Secret isolation

The framework deliberately treats certain variables as
**process-only** — they are NOT loaded from a project-local `.env`
or a shared `.env` such as `~/.hermes/.env`:

* `OPENAI_API_KEY`
* `OPENAI_BASE_URL`

This avoids accidental key leakage between the host agent and the
vidknot process. See `docs/PRIVACY.md` for the rationale.

## Sources file

The sources file is loaded via:

```bash
vidknot batch --sources /path/to/my-sources.yaml
```

The framework ships `examples/sources.yaml.example` as a starting
template. **Do not commit your own sources file** — it almost
certainly contains URLs that you do not want public.

## Validation example

```python
from vidknot.core.source import load_sources_file

bundle = load_sources_file("~/.config/vidknot/sources.yaml")
for source in bundle.by_platform("youtube"):
    print(source.name, source.url)
```

## See also

* `docs/BACKENDS.md` — backend storage configuration
* `docs/PRIVACY.md` — privacy guarantees and credential scanning
* `examples/sources.yaml.example` — sources file template
* `INSTALL.md` — installation and environment check
* `API_GUIDE.md` — third-party API configuration