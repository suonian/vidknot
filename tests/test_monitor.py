"""Tests for the monitor scheduler framework."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from vidknot.core.monitor import (
    MonitorScheduler,
    MonitorTask,
    ScheduledRun,
    TaskRegistry,
)


class _CounterTask(MonitorTask):
    name = "counter"

    def __init__(self, config=None):
        super().__init__(config)
        self.calls = 0

    async def run(self) -> dict[str, Any]:
        self.calls += 1
        return {"call": self.calls}


class _FailingTask(MonitorTask):
    name = "failing"

    async def run(self) -> dict[str, Any]:
        raise RuntimeError("boom")


class _SleepTask(MonitorTask):
    name = "sleep"

    def __init__(self, config=None):
        super().__init__(config)
        self.delay = float((config or {}).get("delay", 0))

    async def run(self) -> dict[str, Any]:
        await asyncio.sleep(self.delay)
        return {"slept": self.delay}


def _make_registry() -> TaskRegistry:
    reg = TaskRegistry()
    reg.register("counter", _CounterTask)
    return reg


def test_registry_rejects_empty_name():
    reg = TaskRegistry()
    with pytest.raises(ValueError):
        reg.register("", _CounterTask)


def test_registry_rejects_duplicate():
    reg = TaskRegistry()
    reg.register("a", _CounterTask)
    with pytest.raises(ValueError):
        reg.register("a", _CounterTask)


def test_registry_names_sorted():
    reg = TaskRegistry()
    reg.register("zeta", _CounterTask)
    reg.register("alpha", _CounterTask)
    assert reg.names() == ["alpha", "zeta"]


def test_registry_build_unknown_raises():
    reg = TaskRegistry()
    with pytest.raises(KeyError):
        reg.build("nope")


@pytest.mark.asyncio
async def test_run_once_aggregates_results():
    reg = TaskRegistry()
    reg.register("counter", _CounterTask)
    scheduler = MonitorScheduler(registry=reg, interval_seconds=0)
    run = await scheduler.run_once()
    assert isinstance(run, ScheduledRun)
    assert run.duration_seconds >= 0
    results = dict(run.task_results)
    assert "counter" in results
    assert results["counter"] == {"call": 1}


@pytest.mark.asyncio
async def test_run_once_captures_task_errors():
    reg = TaskRegistry()
    reg.register("failing", _FailingTask)
    scheduler = MonitorScheduler(registry=reg, interval_seconds=0)
    run = await scheduler.run_once()
    results = dict(run.task_results)
    assert isinstance(results["failing"], str)
    assert results["failing"].startswith("error:")


@pytest.mark.asyncio
async def test_run_once_runs_all_registered_tasks():
    reg = TaskRegistry()
    reg.register("counter", _CounterTask)
    reg.register("sleep", _SleepTask)
    scheduler = MonitorScheduler(registry=reg, interval_seconds=0)
    run = await scheduler.run_once()
    assert len(run.task_results) == 2


@pytest.mark.asyncio
async def test_run_forever_stops_after_max_ticks():
    reg = _make_registry()
    scheduler = MonitorScheduler(registry=reg, interval_seconds=0, max_ticks=3)
    collected = []
    async for run in scheduler.run_forever():
        collected.append(run)
    assert len(collected) == 3


@pytest.mark.asyncio
async def test_task_config_passed_through():
    reg = TaskRegistry()
    reg.register("sleep", _SleepTask)
    scheduler = MonitorScheduler(registry=reg, interval_seconds=0)
    run = await scheduler.run_once()
    result = dict(run.task_results)["sleep"]
    assert result == {"slept": 0.0}


def test_scheduled_run_to_dict():
    run = ScheduledRun(
        started_at="2026-08-10T00:00:00+00:00",
        finished_at="2026-08-10T00:00:01+00:00",
        duration_seconds=1.0,
        task_results=(("a", {"x": 1}), ("b", "error: x")),
    )
    out = run.to_dict()
    assert out["duration_seconds"] == 1.0
    assert out["task_results"] == [
        {"task": "a", "result": {"x": 1}},
        {"task": "b", "result": "error: x"},
    ]