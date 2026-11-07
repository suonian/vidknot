"""The repo README's test-count badges must be re-derivable.

A badge is a picture of a number, and a picture of a number is read by
nobody. The root README advertised "tests-431 passed" while the suite
collected 528 tests, and no check compared the badge with the suite,
because the badge is a URL and a URL is not a claim anything reads. The
number went stale the way a prose-only number goes stale: silently, and
without turning anything red.

The English README carried the same badge with the same stale value, and
that one had no guard at all. A guard that covers one copy of a claim is
not a guard on the claim: the second copy stays a declaration forever, and
a reader who opens the English README sees a number that the suite has
not produced for a long time. So both copies are read here, and both are
compared against the same measured count.

The suite is collected with a collection-only pytest run, the count is read
out of that run's own summary line, and the number each badge states is
compared against it.

The badge says "passed", and for a long time only the collected count was
verified. A collection run cannot tell a passing suite from a failing
one: three items collected, one passed and two failed, and the collected
count still matches the badge while the word "passed" does not hold. So
the word is now backed by a receipt from an actual run of this tree, and
the receipt is bound to the tree it was taken on, so it cannot be carried
over to a changed one.

The README text is read through a pure function, so the check can be
proven to go red on a wrong document instead of only ever confirming a
right one.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "README.md"
README_EN_PATH = ROOT / "README.en.md"
PR_TEMPLATE_PATH = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
RECEIPT_PATH = ROOT / "tests" / "suite_run_receipt.json"

sys.path.insert(0, str(ROOT / "scripts"))

from record_suite_run import product_tree_digest  # noqa: E402

# The badge is a shields.io URL. The count lives in the path segment
# between "badge/" and the closing parenthesis, so the segment is
# captured whole and the number is read out of it afterwards.
BADGE_RE = re.compile(r"(https://img\.shields\.io/badge/)(tests-[^)\s]+)")
BADGE_NUMBER_RE = re.compile(r"^tests-(\d+)(?:%20|\+|\s)passed")

# The summary line of a collection-only run ends with
# "535 tests collected in 1.05s", padded with "=" under -v.
COLLECTED_RE = re.compile(r"(\d+) tests collected")

# The pull request template states the count in prose: "(242 tests)".
PR_TEMPLATE_COUNT_RE = re.compile(r"\((\d+) tests\)")


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


def receipt_violations(receipt: dict, collected_count: int, tree_digest: str) -> list[str]:
    """Every way the recorded run can fail to back the badge's word.

    The badge claims a number of tests that passed. A collection run
    cannot establish that, so the claim rests on a receipt from a real
    run of this tree. This function is where that receipt is checked, and
    it is a pure function so the check can be proven to go red on a wrong
    receipt rather than only ever confirming a right one.

    Returns an empty list when the receipt backs the claim, and one
    message per defect otherwise.
    """
    violations: list[str] = []

    for key in ("collected", "passed", "failed", "skipped", "errors", "deselected"):
        if not isinstance(receipt.get(key), int):
            violations.append("the receipt records no integer %s count" % key)

    if violations:
        return violations

    accounted = (
        receipt["passed"]
        + receipt["failed"]
        + receipt["skipped"]
        + receipt["errors"]
        + receipt["deselected"]
    )
    if accounted != receipt["collected"]:
        violations.append(
            "the receipt accounts for %d tests but collected %d"
            % (accounted, receipt["collected"])
        )

    if receipt["collected"] != collected_count:
        violations.append(
            "the receipt was taken on a tree that collected %d tests, this tree collects %d"
            % (receipt["collected"], collected_count)
        )

    if receipt["failed"] != 0:
        violations.append("the receipt records %d failed tests" % receipt["failed"])

    if receipt["skipped"] != 0:
        violations.append("the receipt records %d skipped tests" % receipt["skipped"])

    if receipt.get("product_tree_digest") != tree_digest:
        violations.append(
            "the receipt was taken on a different tree, so it cannot back a count on this one"
        )

    if not receipt.get("commit"):
        violations.append("the receipt names no commit")

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


def _receipt() -> dict:
    """The recorded run of this tree, or an empty dict when there is none."""
    if not RECEIPT_PATH.exists():
        return {}
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def _pr_template_count(text: str) -> int | None:
    """The count the pull request template states, or None when it states none."""
    match = PR_TEMPLATE_COUNT_RE.search(text)
    return int(match.group(1)) if match else None


def pr_template_violations(text: str, collected_count: int) -> list[str]:
    """Every way the pull request template's test count can fail to hold up.

    The template is the third copy of the same claim: the two READMEs
    state it as a badge, and the template states it in prose. A guard
    that covers the badges and not the template leaves the template a
    declaration, and a declaration nobody reads is exactly how the
    badges went stale in the first place.
    """
    violations: list[str] = []

    number = _pr_template_count(text)
    if number is None:
        violations.append("the pull request template states no test count")
        return violations

    if number != collected_count:
        violations.append(
            "the pull request template states %d tests, %d were collected"
            % (number, collected_count)
        )

    return violations


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


def test_the_english_readme_badge_matches_the_collected_count() -> None:
    """The English README states the same claim, so it must be checked too.

    A guard that reads one copy of a claim leaves the other copy as a
    declaration. The English badge was the unguarded copy: it kept the
    stale value while the root badge was repaired and bound.
    """
    text = README_EN_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    assert count > 0, "the collection run reported no tests at all"
    violations = badge_violations(text, count)
    assert not violations, (
        "the English README badge does not hold up:\n" + "\n".join(violations)
    )


def test_a_wrong_english_readme_badge_number_is_caught() -> None:
    """Mutation proof: only the English badge drifts, and it must go red.

    The mutation moves the English badge's number down by a hundred-odd
    while the root badge is left alone, so the check has to notice the
    second copy on its own. A guard that read only the root badge would
    stay green here.
    """
    text = README_EN_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    assert not badge_violations(text, count), "the unmutated document must be clean to start from"

    segment = _badge_segment(text)
    assert segment is not None, "the English README states no badge to mutate"
    number = _badge_number(segment)
    assert number is not None, "the English README's badge states no number to mutate"

    mutated = _mutate_badge_segment(text, "tests-%d%%20passed-brightgreen" % (number - 102))
    assert mutated != text, "the English README's badge was not found, so the mutation did nothing"
    violations = badge_violations(mutated, count)
    assert any("were collected" in v for v in violations), (
        "changing only the English README badge did not turn the check red; "
        "violations were: %s" % violations
    )


def test_the_pull_request_template_count_matches_the_collected_count() -> None:
    """The template states the same count in prose, so it must be checked too.

    It was the third copy of the claim and the one nobody reads back: it
    said 242 while the suite collected 542. A guard that covers the two
    badges and not the template leaves the template a declaration, and
    that is how the badges went stale in the first place.
    """
    text = PR_TEMPLATE_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    violations = pr_template_violations(text, count)
    assert not violations, (
        "the pull request template's test count does not hold up:\n" + "\n".join(violations)
    )


def test_a_wrong_pull_request_template_count_is_caught() -> None:
    """Mutation proof: a stale template count must turn the check red."""
    text = PR_TEMPLATE_PATH.read_text(encoding="utf-8")
    count = _collected_count()
    assert not pr_template_violations(text, count), (
        "the unmutated template must be clean to start from"
    )

    mutated = PR_TEMPLATE_COUNT_RE.sub("(%d tests)" % (count - 300), text, count=1)
    assert mutated != text, "the template's count was not found, so the mutation did nothing"
    violations = pr_template_violations(mutated, count)
    assert any("were collected" in v for v in violations), (
        "changing only the template count did not turn the check red; violations were: %s" % violations
    )


def test_the_badge_word_passed_is_backed_by_a_run_of_this_tree() -> None:
    """The badge claims a number of tests that passed, so a run must back it.

    A collection-only run cannot tell a passing suite from a failing
    one. The receipt is that run: it is bound to the tree it was taken
    on, and it records the failure and skip counts too, so a run that was
    not clean cannot back the word "passed".
    """
    receipt = _receipt()
    assert receipt, (
        "no run receipt is recorded, so the badge's word \"passed\" is an unbacked claim; "
        "record one with scripts/record_suite_run.py"
    )
    count = _collected_count()
    violations = receipt_violations(receipt, count, product_tree_digest(ROOT))
    assert not violations, "the recorded run does not back the badge:\n" + "\n".join(violations)


def _clean_receipt(count: int, digest: str) -> dict:
    """A receipt that satisfies every rule, built here rather than read.

    The mutation proofs need a receipt that is clean to start from. The
    recorded receipt cannot serve: it is written by a run of this tree,
    and that run has to happen before the recorded receipt exists, so
    demanding that the recorded one be clean would make the proofs
    depend on a file that only exists because they already passed.

    So the clean baseline is built from the measured count and the
    measured digest, and the proofs mutate that.
    """
    return {
        "collected": count,
        "passed": count,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "deselected": 0,
        "commit": "0" * 40,
        "product_tree_digest": digest,
    }


def test_a_receipt_from_a_failing_run_does_not_back_the_badge() -> None:
    """Mutation proof: a receipt with a failure in it must turn the check red.

    This is the case the collection-only guard could never see: the
    collected count is unchanged by a failure, so the badge's number
    still matches while the word "passed" no longer holds.
    """
    count = _collected_count()
    digest = product_tree_digest(ROOT)
    receipt = _clean_receipt(count, digest)
    assert not receipt_violations(receipt, count, digest), (
        "the clean baseline must be clean to start from"
    )

    failed_run = dict(receipt)
    failed_run["failed"] = 2
    failed_run["passed"] = receipt["passed"] - 2
    violations = receipt_violations(failed_run, count, digest)
    assert any("records 2 failed tests" in v for v in violations), (
        "a receipt from a failing run did not turn the check red; violations were: %s" % violations
    )


def test_a_receipt_with_a_skip_does_not_back_the_badge() -> None:
    """Mutation proof: a skipped test must turn the check red too.

    A skip and a pass look the same in a summary line that only mentions
    what passed, and a suite that skips everything still reports a
    collected count. So a skipped count is recorded and checked.
    """
    count = _collected_count()
    digest = product_tree_digest(ROOT)
    receipt = _clean_receipt(count, digest)
    assert not receipt_violations(receipt, count, digest), (
        "the clean baseline must be clean to start from"
    )

    skipped_run = dict(receipt)
    skipped_run["skipped"] = 1
    skipped_run["passed"] = receipt["passed"] - 1
    violations = receipt_violations(skipped_run, count, digest)
    assert any("records 1 skipped tests" in v for v in violations), (
        "a receipt with a skipped test did not turn the check red; violations were: %s" % violations
    )


def test_a_receipt_from_another_tree_does_not_back_the_badge() -> None:
    """Mutation proof: a receipt carried over to a changed tree must go red.

    The receipt names the tree it was taken on, so a tree that changed
    after the run cannot keep borrowing the old run's word "passed".
    """
    count = _collected_count()
    digest = product_tree_digest(ROOT)
    receipt = _clean_receipt(count, digest)
    assert not receipt_violations(receipt, count, digest), (
        "the clean baseline must be clean to start from"
    )

    other_tree = dict(receipt)
    other_tree["product_tree_digest"] = "0" * 64
    violations = receipt_violations(other_tree, count, digest)
    assert any("different tree" in v for v in violations), (
        "a receipt from another tree did not turn the check red; violations were: %s" % violations
    )


def test_a_receipt_whose_counts_do_not_add_up_does_not_back_the_badge() -> None:
    """Mutation proof: a receipt that does not account for every test goes red.

    A receipt whose numbers do not sum to the collected count is missing
    a test it never mentions. Counting only what passed would hide it,
    because the missing test is missing.
    """
    count = _collected_count()
    digest = product_tree_digest(ROOT)
    receipt = _clean_receipt(count, digest)
    assert not receipt_violations(receipt, count, digest), (
        "the clean baseline must be clean to start from"
    )

    unaccounted = dict(receipt)
    unaccounted["passed"] = receipt["passed"] - 1
    violations = receipt_violations(unaccounted, count, digest)
    assert any("accounts for" in v for v in violations), (
        "a receipt that does not account for every test did not turn the check red; "
        "violations were: %s" % violations
    )
