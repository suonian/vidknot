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
| `VIDKNOT_CORRECTION_BACKEND`   | `settings.correction_backend`                |
| `VIDKNOT_SEARCH_BACKEND`       | `settings.search_backend`                    |
| `VIDKNOT_CORRECTION_MODEL`     | `settings.correction_model`                  |
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

## Correction and search backends (no vendor lock-in)

These three settings decide **which backend** performs dual-ASR correction
and web evidence lookup. None of them binds you to a specific vendor.

| Setting | Values | Meaning |
| ------- | ------ | ------- |
| `settings.correction_backend` | `auto` (default) / `provider` / `mmx` / `none` | `auto` picks the first available of **provider → mmx → skip**. `provider` reuses the OpenAI-compatible endpoint under `providers.default_provider` (DeepSeek / Doubao / Qwen / local Ollama all work) and shares the same model as note generation. `mmx` forces the MiniMax `mmx` CLI. `none` disables correction. |
| `settings.search_backend` | `mmx` (default) / `none` | Whether correction may look things up on the web. `mmx` uses the `mmx` CLI's search; if `mmx` is not installed, lookup is skipped instead of failing. `none` disables lookup. |
| `settings.correction_model` | model ID (default empty) | Only used by the `mmx` backend. Empty means "use the `mmx` CLI's own default model". |

> **Two-stage agent contract:** when you use `video_material` / `--material`,
> VidkNot performs **no** correction and **no** search — the material bundle
> is handed to your agent, which does the searching and drafting with its own
> tools. These settings then have no effect.

## ASR (speech) model and endpoint

The **speech** model and the **text-LLM** model are two different things and are
configured separately since v0.6.14.

| Setting | Meaning |
| ------- | ------- |
| `siliconflow_asr.model` | Dedicated speech-model key. Leave it unset to fall through. |
| `siliconflow.model` | The speech model actually sent to SiliconFlow (e.g. `FunAudioLLM/SenseVoiceSmall`). This is the key `config.yaml` uses. |
| `providers.siliconflow.model` | Semantics: the model to use **when SiliconFlow acts as a text-LLM provider**. It is **not** a speech model and is no longer consulted first for ASR. Defaults to unset. |
| `providers.siliconflow.api_key` | SiliconFlow key — shared by the ASR and text paths. |
| `providers.siliconflow.base_url` | Overrides the SiliconFlow API base URL. |

Resolution order for the speech model:

1. the `model=` constructor argument
2. `siliconflow_asr.model`
3. `siliconflow.model`
4. `providers.siliconflow.model` (only when you set it explicitly)
5. `FunAudioLLM/SenseVoiceSmall`

> Before v0.6.14 the built-in default for `providers.siliconflow.model` was the
> **text** model `deepseek-ai/DeepSeek-V3` and it sat first in this order, so an
> empty config asked a text model to transcribe audio. The two roles are now
> separate.

## Material bundle cross-check status

The material bundle returned by `video_material` / `--material` carries the
cross-check state explicitly:

| Field | Values | Meaning |
| ----- | ------ | ------- |
| `diff_status` | `ok` / `failed` / `skipped` | `ok` = the faster-whisper cross-check ran; `failed` = it was attempted but failed (so differences could **not** be determined); `skipped` = it was not requested. |
| `diff_reason` | free text | Why, in one line. Empty only when `diff_status` is `ok` and no difference was found. |
| `diff_count` | int | Number of differences. `diff_count == 0` only means "the transcripts agree" **when** `diff_status == "ok"`. |

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

## Network and cache (`network:` / `cache:`)

Timeouts, retries, and cache expiry are centralized in two config
sections (defaults shown):

```yaml
network:
  http_timeout: 30        # platform parsing HTTP requests (seconds)
  download_timeout: 600   # yt-dlp / FFmpeg download & transcode subprocesses
  api_timeout: 20         # third-party parsing APIs
  max_retries: 2          # retries for transient failures (total = +1)
  backoff_base: 1.0       # exponential backoff base (1s / 2s / 4s ..., cap 30s)

cache:
  max_age_days: 30        # local result cache TTL; expired entries are
                          # cleaned up lazily on read
```

Notes:

- Permanent errors (HTTP 401/403/404) are never retried — they short-circuit
  immediately (see `vidknot.utils.retry.retry_with_backoff`).
- Raise `download_timeout` for long-form videos (>1h) on slow links.
- Set `cache.max_age_days` higher to keep results longer; the cache is a
  content cache keyed by URL + mode, not a credentials store.

## See also

* `docs/BACKENDS.md` — backend storage configuration
* `docs/PRIVACY.md` — privacy guarantees and credential scanning
* `examples/sources.yaml.example` — sources file template
* `INSTALL.md` — installation and environment check
* `API_GUIDE.md` — third-party API configuration