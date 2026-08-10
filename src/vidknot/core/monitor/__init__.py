"""Monitor / scheduler framework.

Defines a generic periodic task interface that user code can implement.
The framework owns:

* a small in-process scheduler that runs registered tasks at fixed
  intervals (no external ``cron`` dependency, no user-defined cron
  strings embedded in the framework),
* a registry mapping task names to implementations,
* a "run-once" entry point useful for tests and ad-hoc CLI use.

Concrete monitoring policies (which platforms, which accounts, which
keywords, what counts as "interesting") live in user-supplied task
implementations — never in the framework.
"""

from .scheduler import MonitorScheduler, MonitorTask, ScheduledRun, TaskRegistry

__all__ = [
    "MonitorScheduler",
    "MonitorTask",
    "ScheduledRun",
    "TaskRegistry",
]
