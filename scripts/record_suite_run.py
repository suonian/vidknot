"""Record one executed suite run as a machine-readable receipt.

The README badge states a number of tests, and until now the only thing
that verified that number was a collection-only run: a count of the tests
that exist, not a count of the tests that passed. Those two counts come
apart the moment something fails, so a badge whose label says "passed"
while its guard proves only "collected" states more than the evidence
behind it.

This script produces the missing evidence. It runs the suite, reads the
counters out of the run's own summary line, and prints them as one JSON
object: collected, passed, failed, skipped, plus the commit and a digest
of the product tree the run was taken on.

The parser lives here rather than inside a test because a parser is where
this kind of receipt usually goes wrong. A summary line that says nothing
about failures reads exactly like a summary line from a run where nothing
failed, unless the reader can be shown to notice the difference. The
assertions in tests/test_suite_run_receipt.py run a scratch suite in which
one test does fail and one test does skip, so a counter that cannot move
is caught by the check that depends on it.

Run it with:  python3 scripts/record_suite_run.py
It prints one JSON object and writes nothing.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COLLECTED_RE = re.compile(r"(\d+) tests collected")
PASSED_RE = re.compile(r"(\d+) passed")
FAILED_RE = re.compile(r"(\d+) failed")
SKIPPED_RE = re.compile(r"(\d+) skipped")
ERROR_RE = re.compile(r"(\d+) errors?")
DESELECTED_RE = re.compile(r"(\d+) deselected")

# The one test that reads the receipt cannot be part of the run the
# receipt describes: its result is not knowable before the receipt
# exists, which is the same shape as a test that judges its own output.
# It is deselected rather than skipped, so the receipt still accounts
# for every collected item.
RECEIPT_TEST = "tests/test_repo_readme_badge.py::test_the_badge_word_passed_is_backed_by_a_run_of_this_tree"


def parse_collected(output: str) -> int | None:
    """The number of test items a collection-only run reported."""
    match = COLLECTED_RE.search(output)
    return int(match.group(1)) if match else None


def _summary_line(output: str) -> str:
    """The last line of the output that carries the run's counters.

    The counters are only trustworthy on pytest's own summary line. A
    failure message earlier in the output can carry the same words, so
    the last matching line is the one that belongs to the run.
    """
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if "passed" in stripped or "no tests ran" in stripped or "deselected" in stripped:
            return stripped
    return ""


def parse_summary(output: str) -> dict[str, int]:
    """The counters out of a pytest run's summary line.

    A counter the summary line does not mention is zero, but only because
    the reader knows how to read it: the scratch-run assertions in
    tests/test_suite_run_receipt.py feed this parser a run where a test
    failed and a test skipped, so a parser that always answered zero would
    be caught there.

    Only the run's own summary line is read. A failure message can
    contain the same words ("2 failed tests", "1 skipped tests"), and a
    reader that took the first match would report a count that never
    happened.
    """
    line = _summary_line(output)
    if not line or "no tests ran" in line:
        return {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "deselected": 0}

    counters = {
        "passed": PASSED_RE.search(line),
        "failed": FAILED_RE.search(line),
        "skipped": SKIPPED_RE.search(line),
        "errors": ERROR_RE.search(line),
        "deselected": DESELECTED_RE.search(line),
    }
    return {name: int(match.group(1)) if match else 0 for name, match in counters.items()}


def product_tree_digest(root: Path) -> str:
    """A digest over the tree the run measured, so a receipt names it.

    The product tree is what the numbers are about: src/ and scripts/.
    The suite's own python files are in it too, because a run measures
    the tests as well as the code, and editing a test after the run
    invalidates the run just as editing the code does.

    The receipt itself is not in it: it is a json file, and a receipt
    that contained its own digest could never be written.
    """
    digest = hashlib.sha256()
    for base in ("src", "scripts"):
        directory = root / base
        if not directory.is_dir():
            continue
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    tests = root / "tests"
    if tests.is_dir():
        for path in sorted(p for p in tests.rglob("*.py") if p.is_file()):
            if "__pycache__" in path.parts:
                continue
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


_tree_digest = product_tree_digest


def _git_commit(root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    commit = proc.stdout.strip()
    return commit if proc.returncode == 0 and commit else None


def collect_count(root: Path = ROOT) -> int | None:
    """How many test items the suite collects, without running any of them."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    return parse_collected(proc.stdout + proc.stderr)


def run_suite(root: Path = ROOT) -> tuple[int, str]:
    """Run the suite and return its exit code and its combined output.

    The one test that reads the receipt is deselected: its verdict is
    not knowable before the receipt exists, and a test that judges its
    own run is the same shape as a detector with no negative control. It
    is deselected rather than skipped, so the run still accounts for
    every collected item.
    """
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
            "--deselect",
            RECEIPT_TEST,
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def receipt(root: Path = ROOT) -> dict:
    """One receipt: what the suite collected, and what actually happened."""
    returncode, output = run_suite(root)
    counters = parse_summary(output)
    return {
        "collected": collect_count(root),
        "passed": counters["passed"],
        "failed": counters["failed"],
        "skipped": counters["skipped"],
        "errors": counters["errors"],
        "deselected": counters["deselected"],
        "returncode": returncode,
        "commit": _git_commit(root),
        "product_tree_digest": product_tree_digest(root),
    }


def write_receipt(root: Path = ROOT) -> dict:
    """Run the suite and record the receipt next to the suite's own files.

    The receipt is written after the run, so it can only ever describe a
    run that actually happened. A run that failed still gets written:
    the point of the receipt is to carry what happened, and a failed run
    is exactly what the badge must not be allowed to claim.
    """
    data = receipt(root)
    path = root / "tests" / "suite_run_receipt.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def main() -> int:
    if "--write" in sys.argv[1:]:
        data = write_receipt()
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0 if data["returncode"] == 0 and data["failed"] == 0 else 1
    data = receipt()
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0 if data["returncode"] == 0 and data["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
