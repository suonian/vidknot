# VidkNot Privacy Statement

VidkNot is an **information retrieval and research framework**. The
project deliberately keeps zero user data on disk in this repository
and ships no embedded credentials, account lists, or private
destinations.

## What is NOT in this repo

* No cookies, tokens, or API keys for any platform
* No user account lists, channel lists, or "KOL" identifiers
* No private folder / document / chat identifiers (Feishu, Notion, Yuque, ...)
* No local caches, downloads, or runtime artifacts

The repository ships only **schema templates** and **example files**
that the user is expected to copy and fill in with their own values.

## What the framework DOES load

At runtime, VidkNot reads configuration from:

1. **Environment variables** — `VIDKNOT_*` prefix is recommended.
   Example: `VIDKNOT_SQLITE_PATH`, `VIDKNOT_FEISHU_APP_ID`, ...
2. **A user-supplied YAML/JSON config file** — paths are explicitly
   passed by the user via CLI flags. The framework never searches
   `~/.config/`, `~/Library/`, or any other implicit location.
3. **A user-supplied sources file** — declared via `--sources` /
   `VIDKNOT_SOURCES_FILE`. See `examples/sources.yaml.example` for the
   schema.

These files live outside the repository by default. Add your own
`.env`, `config.local.yaml`, `sources.yaml` to your `.gitignore`.

## What the framework REFUSES to load

The source loader actively scans for patterns that look like leaked
credentials and refuses to import them:

* `sessionid=`, `ttwid=`, `odin_ttid=`, `fpk1=`, `fpk2=`,
  `web_session=`
* `AI_PASS=` (legacy internal var)
* `Bearer <long-token>`
* OpenAI-style keys (`sk-...`, `SK-...`)

If your sources file accidentally contains any of these, the loader
raises `SourceValidationError` instead of silently embedding them.

## Reporting accidental leaks

If you discover that a credential has been committed to this
repository, please open a private issue or contact the maintainer
directly. Rotating the exposed credential is more important than
cleaning the commit history.

## What this statement does NOT cover

* Local runtime caches and downloads created by `vidknot run` — those
    are written to your filesystem, not the repository.
* Cloud destinations you configure (Feishu folder, Notion page, ...)
    — those credentials never touch this codebase.
* Cookies you export with your browser extension for use with
    `--cookies` flags — same: stay on your disk, never enter Git.