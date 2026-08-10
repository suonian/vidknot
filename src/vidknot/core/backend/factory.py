"""Backend registry factory.

The factory wires built-in backends into a fresh
:class:`~vidknot.core.backend.base.BackendRegistry`. Built-ins are
imported lazily so that importing this module does not pull in every
backend's transitive dependencies (for example, the SQLite backend
should not force a hard dependency on a database driver).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BackendRegistry

if TYPE_CHECKING:
    pass


def build_default_registry() -> BackendRegistry:
    """Return a registry pre-populated with the built-in backends."""
    registry = BackendRegistry()

    # Import lazily so backends with heavy deps are optional.
    try:
        from .sqlite import SqliteBackend
        registry.register(SqliteBackend)
    except ImportError:  # pragma: no cover - optional backend
        pass

    return registry
