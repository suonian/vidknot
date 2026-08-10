"""Subscription source schema and loaders.

Defines the YAML/JSON schema for user-supplied subscription lists and
the validation rules that enforce:

* no embedded credentials (cookies, API keys, tokens),
* normalized URL fields,
* consistent ``platform`` identifiers.

The loader never reads from the user's home directory automatically —
callers must pass an explicit path. This keeps the framework free of
user-specific data.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

import yaml


class SourceKind(str, Enum):
    """What kind of source this entry represents."""

    VIDEO_URL = "video_url"
    CHANNEL = "channel"
    HASHTAG = "hashtag"
    PLAYLIST = "playlist"


# Patterns that strongly suggest a credential was accidentally pasted
# into a sources file. We refuse to load such entries.
_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sessionid\s*=", re.IGNORECASE),
    re.compile(r"ttwid\s*=", re.IGNORECASE),
    re.compile(r"odin_ttid\s*=", re.IGNORECASE),
    re.compile(r"fpk[12]\s*=", re.IGNORECASE),
    re.compile(r"web_session\s*=", re.IGNORECASE),
    re.compile(r"SK-[A-Za-z0-9]{16,}"),  # OpenAI-style API key
    re.compile(r"sk-[a-z0-9]{16,}"),  # OpenAI / siliconflow / zhipu
    re.compile(r"AI_PASS\s*="),  # legacy internal var
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}"),
)


class SourceValidationError(ValueError):
    """Raised when a source entry is invalid or contains credentials."""


def _looks_like_credential(value: str) -> bool:
    return any(p.search(value) for p in _FORBIDDEN_PATTERNS)


@dataclass(frozen=True)
class SourceConfig:
    """A single subscription source entry."""

    name: str
    platform: str
    kind: SourceKind = SourceKind.VIDEO_URL
    url: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    schedule: str | None = None  # e.g. cron expression
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourcesFile:
    """A parsed subscription file."""

    sources: tuple[SourceConfig, ...] = ()
    path: Path | None = None

    def by_platform(self, platform: str) -> list[SourceConfig]:
        return [s for s in self.sources if s.platform == platform]


def validate_source(raw: Mapping[str, Any]) -> SourceConfig:
    """Validate and normalize a raw source entry.

    Raises:
        SourceValidationError: if the entry is missing required fields
            or appears to contain a credential.
    """
    if not isinstance(raw, Mapping):
        raise SourceValidationError(f"Source entry must be a mapping, got {type(raw).__name__}")

    name = str(raw.get("name", "")).strip()
    if not name:
        raise SourceValidationError("Source entry is missing required 'name' field.")

    platform = str(raw.get("platform", "")).strip()
    if not platform:
        raise SourceValidationError(f"Source {name!r} is missing 'platform' field.")

    kind_raw = str(raw.get("kind", SourceKind.VIDEO_URL.value)).strip()
    try:
        kind = SourceKind(kind_raw)
    except ValueError as exc:
        valid = ", ".join(k.value for k in SourceKind)
        raise SourceValidationError(
            f"Source {name!r} has invalid kind {kind_raw!r}; valid: {valid}"
        ) from exc

    url = raw.get("url")
    if url is not None:
        url = str(url).strip()
        if not url:
            url = None
        else:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                raise SourceValidationError(
                    f"Source {name!r} has invalid url scheme: {parsed.scheme!r}"
                )

    tags_raw = raw.get("tags", []) or []
    if isinstance(tags_raw, str):
        tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
    tags = tuple(str(t).strip() for t in tags_raw if str(t).strip())

    schedule = raw.get("schedule")
    if schedule is not None:
        schedule = str(schedule).strip() or None

    # Credential scan across all string fields.
    candidates = (name, platform, url or "", schedule or "", *tags, json.dumps(raw, default=str))
    for value in candidates:
        if value and _looks_like_credential(value):
            raise SourceValidationError(
                f"Source {name!r} contains what looks like a credential. "
                "Move credentials to environment variables or a separate, "
                "git-ignored secrets store."
            )

    extra_raw = raw.get("extra", {}) or {}
    if not isinstance(extra_raw, Mapping):
        raise SourceValidationError(f"Source {name!r} field 'extra' must be a mapping.")

    extra_serialized = json.dumps(extra_raw, default=str)
    if _looks_like_credential(extra_serialized):
        raise SourceValidationError(
            f"Source {name!r} field 'extra' contains what looks like a credential."
        )

    return SourceConfig(
        name=name,
        platform=platform,
        kind=kind,
        url=url,
        tags=tags,
        schedule=schedule,
        extra=dict(extra_raw),
    )


def load_sources_file(path: str | os.PathLike[str]) -> SourcesFile:
    """Load and validate a YAML or JSON subscription file.

    Args:
        path: Explicit filesystem path. Callers must provide this — the
            framework never searches the user's home directory.

    Returns:
        A :class:`SourcesFile` with validated entries.

    Raises:
        SourceValidationError: on schema errors or credential leaks.
        FileNotFoundError: if the path does not exist.
    """
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Sources file not found: {p}")

    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text) if text.strip() else {}

    if not isinstance(data, Mapping):
        raise SourceValidationError(
            f"Sources file root must be a mapping; got {type(data).__name__}"
        )

    raw_sources = data.get("sources", []) or []
    if not isinstance(raw_sources, Sequence):
        raise SourceValidationError("'sources' must be a list.")

    sources = tuple(validate_source(s) for s in raw_sources)
    return SourcesFile(sources=sources, path=p)


def expand_glob(urls: Iterable[str]) -> list[str]:
    """Expand glob-style URL lists. Conservative: only literal lists pass."""
    out: list[str] = []
    for url in urls:
        if not url:
            continue
        out.append(url.strip())
    return out