# Backend Storage Configuration

VidkNot persists processed notes via a pluggable **backend** layer.
This document covers:

* how to choose a backend,
* how to configure each backend,
* how to register a custom backend.

## Default registry

The default backend registry ships with:

| Name      | Backend      | Notes                                      |
| --------- | ------------ | ------------------------------------------ |
| `sqlite`  | `SqliteBackend` | Local file. Default for development.    |
| `obsidian`| (existing)   | Markdown file under `OBSIDIAN_VAULT_PATH`. |
| `feishu`  | (existing)   | Feishu / Lark doc via app credentials.    |
| `notion`  | (existing)   | Notion database via integration token.     |
| `yuque`   | (existing)   | Yuque knowledge base via personal token.  |

The first three (`sqlite`, `obsidian`, `feishu`) are wired into the
default config. Add `notion` or `yuque` keys to your config to
activate them.

## Backend-agnostic configuration

```yaml
settings:
  default_backend: sqlite   # or obsidian / feishu / notion / yuque
  backends:
    sqlite:
      path: ~/notes/vidknot.db
    feishu:
      app_id: "${FEISHU_APP_ID}"
      app_secret: "${FEISHU_APP_SECRET}"
      folder_token: "${FEISHU_FOLDER_TOKEN}"
    obsidian:
      vault_path: ~/Documents/Obsidian/Vault
      default_folder: 视频笔记
```

## Backend-specific setup

### SQLite (built-in)

* Configure `path` (defaults to `./vidknot_notes.db`).
* Override via env: `VIDKNOT_SQLITE_PATH=/var/lib/vidknot/notes.db`.
* No external service, no credentials.

### Feishu / Lark (existing adapter)

To use Feishu you need an internal app with `docs:document:write`
permission. Step-by-step:

1. Go to <https://open.feishu.cn/app> and create an "Internal App".
2. On the app's "Permissions" page, request:
   * `docs:document:write` (create / edit documents)
   * `docs:document:read` (read existing documents)
   * `drive:drive` (upload to folders)
3. On "Security Settings", add the IP whitelist if you run on a
   static-IP server.
4. Copy **App ID** and **App Secret** into your environment:

   ```bash
   export FEISHU_APP_ID=cli_xxxxxxxx
   export FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx
   export FEISHU_FOLDER_TOKEN=bascnxxxxxxxxxxxx   # optional, defaults to your bot's home folder
   ```

5. Share the target folder with the bot user, granting
   `full_access` (Editor). See `docs/PRIVACY.md` for the rationale.

### Obsidian

`obsidian_writer` writes a Markdown file under
`OBSIDIAN_VAULT_PATH/<default_folder>/<title>.md`.

```bash
export OBSIDIAN_VAULT_PATH=/home/me/Documents/Obsidian/Main
export OBSIDIAN_DEFAULT_FOLDER=视频笔记
```

### Notion / Yuque

Configured similarly via `NOTION_TOKEN`, `NOTION_PAGE_ID`,
`YUQUE_TOKEN`, `YUQUE_LOGIN`. See `API_GUIDE.md` for the full list.

## Registering a custom backend

```python
from vidknot.core.backend import BackendRegistry, BackendStorage, NotePayload, StorageResult

class MyBackend(BackendStorage):
    name = "my-backend"

    def save(self, payload: NotePayload) -> StorageResult:
        ...

registry = BackendRegistry()
registry.register(MyBackend)
backend = registry.build("my-backend")
backend.save(NotePayload(title="t", markdown="m", source_url="s"))
```

See `tests/test_backend.py` for a worked example.

## Privacy

None of the configuration values above are user-specific. They are
generic keys whose values the user supplies at runtime. See
`docs/PRIVACY.md` for what the framework refuses to embed.