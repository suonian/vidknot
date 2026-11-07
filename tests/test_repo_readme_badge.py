"""The repo README's test-count badge must be re-derivable.

A badge is a picture of a number, and a picture of a number is read by
nobody. The root README advertised "tests-431 passed" while the suite
collected 528 tests, and no check compared the badge with the suite,
because the badge is a URL and a URL is not a claim anything reads. The
number went stale the way a prose-only number goes stale: silently, and
without turning anything red.

So the badge is re-derived here rather than trusted. The whole repo is
collected with a collection-only pytest run, the count is read out of
that run's own summary line, and the number the badge states is compared
against it.

The README text is read through a pure function, so the check can be
proven to go red on a wrong document instead of only ever confirming a
right one.
"""

from __future__ import annotations

import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "README.md"

# The badge is a shields.io URL. The count lives in the path segment
# between "badge/" and the closing parenthesis, so the segment is
# captured whole and the number is read out of it afterwards.
BADGE_RE = re.compile(r"(https://img\.shields\.io/badge/)(tests-[^)\s]+)")
BADGE_NUMBER_RE = re.compile(r"^tests-(\d+)(?:%20|\+|\s)passed")

# The summary line of a collection-only run ends with
# "533 tests collected in 1.05s", padded with "=" under -v.
COLLECTED_RE = re.compile(r"(\d+) tests collected")


def _badge_segment(text: str) -> str | None:
    """The badge's path segment, or None when the README states no badge."""
    match = BADGE_RE.search(text)
    return match.group(2) if match else None


def _badge_number(segment: str) -> int | None:
    """The count the badge states, or None when it states none."""
    match = BADGE_NUMBER_RE.match(segment)
    return int(match.group(1)) if match else None


def badge_violations(readme_text: str, collected_count: int) -> list[str]:
    """Every way the README's tests badge can fail to hold up.

    Returns an empty list when the badge states the number of tests the
    repo actually collects, and one message per defect otherwise.
    """
    violations: list[str] = []

    segment = _badge_segment(readme_text)
    if segment is None:
        violations.append("the README states no tests badge")
        return violations

    number = _badge_number(segment)
    if number is None:
        violations.append("the README's tests badge states no test count")
        return violations

    if number != collected_count:
        violations.append(
            "the README badge states %d tests, %d were collected" % (number, collected_count)
        )

    return violations


@lru_cache(maxsize=1)
def _collected_count() -> int:
    """The number of test items the whole repo collects.

    The inner run only collects, it never executes, so it cannot recurse
    into this module's own subprocess call. Collecting the whole repo
    takes about a second, so the count is collected once and reused by
    the mutation proofs.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError("collection failed:\n%s\n%s" % (proc.stdout[-4000:], proc.stderr[-4000:]))
    counts = COLLECTED_RE.findall(proc.stdout)
    assert counts, "the collection run printed no collected count:\n%s" % proc.stdout[-4000:]
    return int(counts[-1])


def _mutate_badge_segment(text: str, segment: str) -> str:
    """The README with its badge path segment replaced."""
    return BADGE_RE.sub(lambda m: "%s%s" % (m.group(1), segment), text, count=1)


def _drop_badge_line(text: str) -> str:
    """The README with the line carrying the tests badge removed."""
    lines = text.splitlines()
    kept = [line for line in lines if "img.shields.io/badge/tests-" not in line]
    assert len(kept) == len(lines) - 1, "the badge line was not found, so the mutation did nothing"
    return "\n".join(kept) + "\n"


def test_the_badge_number_matches_the_collected_count() -> None:
    """The badge must state the number of tests the repo actually collects."""
    text = README_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    assert count > 0, "the collection run reported no tests at all"
    violations = badge_violations(text, count)
    assert not violations, "the README badge does not hold up:\n" + "\n".join(violations)


def test_a_wrong_badge_number_is_caught() -> None:
    """Mutation proof: the check must go red on a wrong badge number."""
    text = README_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    assert not badge_violations(text, count), "the unmutated document must be clean to start from"

    segment = _badge_segment(text)
    assert segment is not None, "the README states no badge to mutate"
    number = _badge_number(segment)
    assert number is not None, "the README's badge states no number to mutate"

    mutated = _mutate_badge_segment(text, "tests-%d%%20passed-brightgreen" % (number + 1))
    assert mutated != text, "the badge segment was not found, so the mutation did nothing"
    violations = badge_violations(mutated, count)
    assert any("were collected" in v for v in violations), (
        "changing only the badge number did not turn the check red; violations were: %s" % violations
    )


def test_a_badge_with_no_number_in_it_is_caught() -> None:
    """Mutation proof: a badge that states no count must not pass."""
    text = README_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    assert not badge_violations(text, count), "the unmutated document must be clean to start from"

    mutated = _mutate_badge_segment(text, "tests-%20passed-brightgreen")
    assert mutated != text, "the badge segment was not found, so the mutation did nothing"
    violations = badge_violations(mutated, count)
    assert any("states no test count" in v for v in violations), (
        "a badge with no number in it did not turn the check red; violations were: %s" % violations
    )


def test_a_badge_with_an_unparseable_number_is_caught() -> None:
    """Mutation proof: a badge that states a non-number must not pass."""
    text = README_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    assert not badge_violations(text, count), "the unmutated document must be clean to start from"

    mutated = _mutate_badge_segment(text, "tests-many%20passed-brightgreen")
    assert mutated != text, "the badge segment was not found, so the mutation did nothing"
    violations = badge_violations(mutated, count)
    assert any("states no test count" in v for v in violations), (
        "a badge with an unparseable number did not turn the check red; violations were: %s" % violations
    )


def test_a_missing_badge_is_caught() -> None:
    """Mutation proof: a README with no tests badge must not pass."""
    text = README_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    assert not badge_violations(text, count), "the unmutated document must be clean to start from"

    mutated = _drop_badge_line(text)
    violations = badge_violations(mutated, count)
    assert any("states no tests badge" in v for v in violations), (
        "dropping the badge line did not turn the check red; violations were: %s" % violations
    )
