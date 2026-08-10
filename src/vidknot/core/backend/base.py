"""Backend storage contracts.

These dataclasses and protocols are framework-only. They define the
minimum surface a backend must implement to interoperate with the
research platform, but they do not encode any user-specific data,
accounts, or destination identifiers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NotePayload:
    """A normalized note ready to be persisted.

    Attributes are deliberately generic. Concrete backends decide how to
    render this payload (Markdown body, JSON document, SQL row, ...).
    """

    title: str
    markdown: str
    source_url: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    tags: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class StorageResult:
    """Outcome of a backend save operation."""

    backend_name: str
    location: str
    ok: bool
    error: str | None = None


class BackendStorage(ABC):
    """Abstract storage backend.

    Implementations are expected to:

    * read their own configuration from environment variables or a
      user-supplied ``config`` mapping at ``__init__`` time,
    * never embed credentials or account identifiers in source code,
    * raise :classclass:`BackendError` for any operational failure so the
      caller can decide whether to retry, fall back, or surface the
      error to the user.
    """

    name: str = "abstract"

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._config: Mapping[str, Any] = dict(config or {})

    @abstractmethod
    def save(self, payload: NotePayload) -> StorageResult: ...

    def save_many(self, payloads: Iterable[NotePayload]) -> list[StorageResult]:
        """Default sequential saver; backends may override for batching."""
        return [self.save(p) for p in payloads]


class BackendError(RuntimeError):
    """Raised by backends when persistence fails."""


class BackendRegistry:
    """In-process registry mapping backend names to implementations."""

    def __init__(self) -> None:
        self._backends: dict[str, type[BackendStorage]] = {}

    def register(self, cls: type[BackendStorage]) -> type[BackendStorage]:
        if not cls.name or cls.name == "abstract":
            raise ValueError("Backend must set a non-empty 'name' class attribute.")
        self._backends[cls.name] = cls
        return cls

    def names(self) -> list[str]:
        return sorted(self._backends)

    def build(self, name: str, config: Mapping[str, Any] | None = None) -> BackendStorage:
        try:
            cls = self._backends[name]
        except KeyError as exc:
            raise BackendError(f"Unknown backend: {name!r}. Known: {self.names()}") from exc
        return cls(config)

    def has(self, name: str) -> bool:
        return name in self._backends
