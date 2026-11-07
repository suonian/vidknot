"""A run's counters must be able to move, and the reader must notice.

A receipt that says "zero failures" is only evidence if the reader would
have said "one failure" when there was one. A parser that always answers
zero produces the same receipt for a broken run and for a healthy one, so
the receipt reads as authoritative while measuring nothing.

So the counters are exercised on scratch runs where the answer is known:
one test fails, one test skips, and the reader has to report both. The
same scratch tree is then run without the skip, and the skipped count has
to fall back to zero. A counter that cannot move fails here, and every
receipt built on it loses its meaning.

The parser under test is the one the repository's own receipt script uses,
so this module and the script cannot drift apart.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from record_suite_run import parse_collected, parse_summary  # noqa: E402

FAILING_TEST = """
def test_fails():
    assert 1 == 2
"""

SKIPPING_TEST = """
import pytest


def test_skips():
    pytest.skip("deliberately skipped")
"""

PASSING_TEST = """
def test_passes():
    assert True
"""


def _run_scratch(tmp_path: Path, files: dict[str, str]) -> str:
    """Run a throwaway suite in a scratch tree and return its output."""
    root = tmp_path / "scratch"
    (root / "tests").mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (root / name).write_text(body, encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "tests",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def test_the_reader_takes_each_counter_from_the_summary_line() -> None:
    """Every counter is read from the line, and a duration is not a count."""
    counters = parse_summary("1 failed, 2 passed, 3 skipped in 1.23s")
    assert counters["failed"] == 1, counters
    assert counters["passed"] == 2, counters
    assert counters["skipped"] == 3, counters

    clean = parse_summary("2 passed in 0.45s")
    assert clean["failed"] == 0, clean
    assert clean["skipped"] == 0, clean
    assert clean["passed"] == 2, clean


def test_the_reader_ignores_counters_printed_inside_a_failure_message() -> None:
    """Only the run's own summary line carries the run's counters.

    A failure message can contain the same words. A reader that took the
    first match would report a count that never happened: it would read
    the number in the message and call it the run's result.
    """
    output = (
        "assert 2 failed tests in the receipt\n"
        "the README badge states 1 passed\n"
        "3 failed, 4 passed, 5 skipped in 1.23s\n"
    )
    counters = parse_summary(output)
    assert counters["failed"] == 3, counters
    assert counters["passed"] == 4, counters
    assert counters["skipped"] == 5, counters


def test_a_run_that_collected_nothing_reports_no_counters() -> None:
    """A run with no tests is not a run that passed zero tests."""
    counters = parse_summary("no tests ran in 0.01s")
    assert counters["passed"] == 0, counters
    assert counters["failed"] == 0, counters
    assert counters["skipped"] == 0, counters


def test_a_failing_and_a_skipping_run_moves_both_counters(tmp_path: Path) -> None:
    """The counters must reach non-zero when the run really has them."""
    output = _run_scratch(
        tmp_path,
        {
            "tests/test_failing.py": FAILING_TEST,
            "tests/test_skipping.py": SKIPPING_TEST,
            "tests/test_passing.py": PASSING_TEST,
        },
    )
    counters = parse_summary(output)
    assert counters["failed"] == 1, output
    assert counters["skipped"] == 1, output
    assert counters["passed"] == 1, output


def test_a_clean_run_reports_no_failures_and_no_skips(tmp_path: Path) -> None:
    """The same reader must fall back to zero when there is nothing to report."""
    output = _run_scratch(
        tmp_path,
        {
            "tests/test_passing.py": PASSING_TEST,
            "tests/test_also_passing.py": PASSING_TEST,
        },
    )
    counters = parse_summary(output)
    assert counters["failed"] == 0, output
    assert counters["skipped"] == 0, output
    assert counters["passed"] == 2, output


def test_the_collected_count_is_read_from_a_collection_run(tmp_path: Path) -> None:
    """The collected count is its own counter, and it counts items."""
    root = tmp_path / "collect"
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "tests/test_passing.py").write_text(PASSING_TEST, encoding="utf-8")
    (root / "tests/test_also_passing.py").write_text(PASSING_TEST, encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "tests",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert parse_collected(proc.stdout + proc.stderr) == 2, proc.stdout + proc.stderr
