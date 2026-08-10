"""Storage backend abstraction layer.

Provides a pluggable interface for persisting processed notes to various
destinations (Feishu, Obsidian, Notion, Yuque, SQLite, ...).

This module is intentionally framework-only: it defines contracts and
delivers a default registry. Concrete implementations live in
``vidknot.core.backend.<name>``. User credentials, account identifiers,
and concrete data sources must never be embedded in this layer — each
backend reads its own configuration from environment variables or from
a user-supplied config object at runtime.
"""

from .base import BackendRegistry, BackendStorage, NotePayload, StorageResult
from .factory import build_default_registry

__all__ = [
    "BackendStorage",
    "BackendRegistry",
    "NotePayload",
    "StorageResult",
    "build_default_registry",
]
