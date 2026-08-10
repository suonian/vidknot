"""Generic periodic scheduler for monitor tasks.

The scheduler is intentionally minimal:

* Tasks implement :class:`MonitorTask` with an async ``run`` method.
* Tasks are registered in a :class:`TaskRegistry`.
* :class:`MonitorScheduler` runs all registered tasks in sequence on
  every tick; ``interval_seconds`` controls the tick frequency.
* ``run_once`` is provided for tests and CLI use; it runs every task
  exactly once and returns the aggregated results.

The framework never imports platform-specific code. It is the user's
responsibility to register concrete tasks that subclass
:class:`MonitorTask`.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Iterable, Mapping


class MonitorTask(ABC):
    """Abstract periodic task.

    Subclasses must implement :meth:`run`, which performs one monitoring
    cycle and returns a result mapping. Errors raised in :meth:`run`
    are captured by the scheduler and recorded in :class:`ScheduledRun`.
    """

    name: str = "abstract"

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._config: Mapping[str, Any] = dict(config or {})

    @property
    def config(self) -> Mapping[str, Any]:
        return self._config

    @abstractmethod
    async def run(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ScheduledRun:
    """Result of a single scheduled tick."""

    started_at: str
    finished_at: str
    duration_seconds: float
    task_results: tuple[tuple[str, dict[str, Any] | str], ...] = ()

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "task_results": [
                {"task": name, "result": result}
                for name, result in self.task_results
            ],
        }


class TaskRegistry:
    """Holds task factories keyed by name."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], MonitorTask]] = {}

    def register(self, name: str, factory: Callable[[], MonitorTask]) -> None:
        if not name:
            raise ValueError("Task name must be non-empty")
        if name in self._factories:
            raise ValueError(f"Task {name!r} already registered")
        self._factories[name] = factory

    def names(self) -> list[str]:
        return sorted(self._factories)

    def build(self, name: str) -> MonitorTask:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise KeyError(f"Unknown task: {name!r}. Known: {self.names()}") from exc
        return factory()


@dataclass
class MonitorScheduler:
    """Sequential in-process scheduler."""

    registry: TaskRegistry
    interval_seconds: float = 60.0
    max_ticks: int | None = None  # None = infinite
    _tick_count: int = field(default=0, init=False)

    async def _run_task(self, task: MonitorTask) -> tuple[str, dict[str, Any] | str]:
        try:
            result = await task.run()
            return task.name, result
        except Exception as exc:  # noqa: BLE001 — task errors are reported, not raised
            return task.name, f"error: {exc!r}"

    async def run_once(self) -> ScheduledRun:
        start = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        results: list[tuple[str, dict[str, Any] | str]] = []
        for name in self.registry.names():
            task = self.registry.build(name)
            results.append(await self._run_task(task))
        finished_at = datetime.now(timezone.utc).isoformat()
        return ScheduledRun(
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=time.monotonic() - start,
            task_results=tuple(results),
        )

    async def run_forever(self) -> "AsyncIterator[ScheduledRun]":
        """Yield :class:`ScheduledRun` results until ``max_ticks`` is hit.

        Yields rather than returning a list, so callers can stream logs
        and react to errors as soon as they happen.
        """
        while True:
            self._tick_count += 1
            yield await self.run_once()
            if self.max_ticks is not None and self._tick_count >= self.max_ticks:
                return
            await asyncio.sleep(self.interval_seconds)