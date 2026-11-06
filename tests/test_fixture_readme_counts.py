"""The fixture README's module list and totals must be re-derivable.

A count-shaped conclusion that only exists as prose drifts. The fixture
README enumerates the self-check modules and their assertion counts, and
until now nothing read it: when the byte-stream comparability module was
added to that list, its nine assertions were never added to the total, so
the document listed seven modules while claiming six and forty-six. The
list actually sums to fifty-five.

So the numbers are re-derived here rather than trusted. The collected
assertion count of every listed module is compared against the count the
README prints, the printed total is compared against the sum of the
printed counts, the printed module count is compared against the number of
modules actually listed, and the listed set is compared against the
fixture set this file defines.

The README text is read through a pure function, so the check can be
proven to go red on a wrong document instead of only ever confirming a
right one.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README_PATH = ROOT / "tests" / "fixtures" / "agent_reliability" / "README.md"

# The self-check modules this fixture set is defined to contain. The
# assertion count of each one is not written down here: it is collected
# from the module itself.
FIXTURE_MODULES = (
    "tests/test_agent_reliability_fixtures.py",
    "tests/test_agent_reliability_pairing.py",
    "tests/test_agent_reliability_class_coverage.py",
    "tests/test_agent_reliability_arm_digests.py",
    "tests/test_agent_reliability_reason_binding.py",
    "tests/test_agent_reliability_uniqueness.py",
    "tests/test_byte_stream_comparability.py",
)

CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

FIRST_MODULE_RE = re.compile(r"python3 -m pytest (tests/\S+\.py)")
FIRST_COUNT_RE = re.compile(r"^(\d+) 条", re.MULTILINE)
LISTED_RE = re.compile(r"另有 `(tests/[^`]+\.py)`, (\d+) 条")
TOTAL_RE = re.compile(r"([一二三四五六七八九十]+)份合计 (\d+) 条")
NODE_ID_RE = re.compile(r"^(tests/\S+\.py)::")


def _cn_number(text: str) -> int | None:
    """Read a Chinese numeral up to twenty, or None if it is not one."""
    if text in CN_DIGITS:
        return CN_DIGITS[text]
    if text == "十":
        return 10
    if len(text) == 2 and text[0] == "十":
        return 10 + CN_DIGITS.get(text[1], 0)
    if len(text) == 3 and text[1] == "十":
        return CN_DIGITS.get(text[0], 0) * 10 + CN_DIGITS.get(text[2], 0)
    return None


def _self_check_section(text: str) -> str:
    """The 自检 section of the README, which owns the module list."""
    start = text.find("## 自检")
    if start < 0:
        return ""
    rest = text[start + len("## 自检"):]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


def _parse_readme(text: str) -> dict:
    """Read the module list, the per-module counts and the total."""
    section = _self_check_section(text)
    first_module = FIRST_MODULE_RE.search(section)
    first_count = FIRST_COUNT_RE.search(section)
    listed = {module: int(count) for module, count in LISTED_RE.findall(section)}
    total = TOTAL_RE.search(section)
    return {
        "first_module": first_module.group(1) if first_module else None,
        "first_count": int(first_count.group(1)) if first_count else None,
        "listed": listed,
        "stated_module_count": _cn_number(total.group(1)) if total else None,
        "stated_total": int(total.group(2)) if total else None,
    }


def readme_violations(text: str, actual_counts: dict[str, int]) -> list[str]:
    """Every way the README's own numbers can fail to hold up.

    Returns an empty list when the document agrees with itself and with
    the collected counts, and one message per defect otherwise.
    """
    parsed = _parse_readme(text)
    violations: list[str] = []

    stated = dict(parsed["listed"])
    if parsed["first_module"]:
        if parsed["first_count"] is None:
            violations.append("the first module is listed but its count is missing")
        else:
            stated[parsed["first_module"]] = parsed["first_count"]
    else:
        violations.append("the self-check section names no first module")

    expected = set(FIXTURE_MODULES)
    if set(stated) != expected:
        missing = sorted(expected - set(stated))
        extra = sorted(set(stated) - expected)
        if missing:
            violations.append("modules missing from the README list: %s" % ", ".join(missing))
        if extra:
            violations.append("modules listed that are not part of the fixture set: %s" % ", ".join(extra))

    for module in sorted(stated):
        actual = actual_counts.get(module)
        if actual is None:
            violations.append("%s was not collected, so its stated count is unverified" % module)
        elif actual != stated[module]:
            violations.append(
                "%s: README states %d assertions, %d were collected" % (module, stated[module], actual)
            )

    if parsed["stated_total"] is None:
        violations.append("the self-check section states no total")
    else:
        if stated and parsed["stated_total"] != sum(stated.values()):
            violations.append(
                "the README total is %d but its own listed counts sum to %d"
                % (parsed["stated_total"], sum(stated.values()))
            )
        if parsed["stated_module_count"] is not None and parsed["stated_module_count"] != len(stated):
            violations.append(
                "the README claims %d modules but lists %d"
                % (parsed["stated_module_count"], len(stated))
            )

    return violations


def _collect_assertion_counts() -> dict[str, int]:
    """Collect the assertion count of each fixture module.

    A module's count is the number of test items pytest collects for it,
    which is not the same as the number of test functions in the file: a
    parametrized function contributes one item per case.
    """
    # addopts is cleared because pytest.ini sets -v, and a verbose
    # collection prints a tree instead of one node id per line.
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", *FIXTURE_MODULES],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError("collection failed:\n%s\n%s" % (proc.stdout[-4000:], proc.stderr[-4000:]))
    counts: Counter[str] = Counter()
    for line in proc.stdout.splitlines():
        match = NODE_ID_RE.match(line.strip())
        if match:
            counts[match.group(1)] += 1
    return dict(counts)


def test_the_readme_module_list_and_totals_match_the_collected_counts() -> None:
    """The README's numbers must be re-derivable, not asserted."""
    text = README_PATH.read_text(encoding="utf-8")
    counts = _collect_assertion_counts()
    assert counts, "collection returned no test items at all"
    violations = readme_violations(text, counts)
    assert not violations, "the fixture README's numbers do not hold up:\n" + "\n".join(violations)


def test_a_wrong_total_in_the_readme_is_caught() -> None:
    """Mutation proof: the check must go red on a wrong total."""
    text = README_PATH.read_text(encoding="utf-8")
    counts = _collect_assertion_counts()
    assert not readme_violations(text, counts), "the unmutated document must be clean to start from"

    mutated = TOTAL_RE.sub(lambda m: "%s份合计 %d 条" % (m.group(1), int(m.group(2)) + 1), text, count=1)
    assert mutated != text, "the total line was not found, so the mutation did nothing"
    violations = readme_violations(mutated, counts)
    assert any("the README total is" in v for v in violations), (
        "changing only the total did not turn the check red; violations were: %s" % violations
    )


def test_a_wrong_per_module_count_in_the_readme_is_caught() -> None:
    """Mutation proof: one module's stated count must be checked too."""
    text = README_PATH.read_text(encoding="utf-8")
    counts = _collect_assertion_counts()
    assert not readme_violations(text, counts), "the unmutated document must be clean to start from"

    target = FIXTURE_MODULES[-1]
    mutated = re.sub(
        r"(另有 `%s`, )(\d+)( 条)" % re.escape(target),
        lambda m: "%s%d%s" % (m.group(1), int(m.group(2)) + 1, m.group(3)),
        text,
        count=1,
    )
    assert mutated != text, "the module's count line was not found, so the mutation did nothing"
    violations = readme_violations(mutated, counts)
    assert any(target in v and "assertions" in v for v in violations), (
        "changing one module's count did not turn the check red; violations were: %s" % violations
    )


def test_a_module_dropped_from_the_readme_list_is_caught() -> None:
    """Mutation proof: dropping a module must not silently lower the total."""
    text = README_PATH.read_text(encoding="utf-8")
    counts = _collect_assertion_counts()
    assert not readme_violations(text, counts), "the unmutated document must be clean to start from"

    target = FIXTURE_MODULES[-1]
    mutated = re.sub(r"另有 `%s`, \d+ 条[^\n]*\n" % re.escape(target), "", text, count=1)
    assert mutated != text, "the module's paragraph was not found, so the mutation did nothing"
    violations = readme_violations(mutated, counts)
    assert any("missing from the README list" in v for v in violations), (
        "dropping a module from the list did not turn the check red; violations were: %s" % violations
    )


def test_a_module_claimed_but_never_collected_is_caught() -> None:
    """Mutation proof: a module that is not collected is not a valid claim."""
    text = README_PATH.read_text(encoding="utf-8")
    counts = _collect_assertion_counts()
    assert not readme_violations(text, counts), "the unmutated document must be clean to start from"

    stripped = dict(counts)
    stripped.pop(FIXTURE_MODULES[-1], None)
    violations = readme_violations(text, stripped)
    assert any("was not collected" in v for v in violations), (
        "a module that was not collected did not turn the check red; violations were: %s" % violations
    )
