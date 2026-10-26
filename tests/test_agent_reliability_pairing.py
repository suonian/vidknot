"""Pairing and green-arm checks for the agent-reliability fixture set.

Why this file exists separately
-------------------------------
The pairing assertion that used to live in
tests/test_agent_reliability_fixtures.py read:

    covered = {r["class_id"] for r in rows if r["control_direction"] != "must_fail"}
    for cls in must_fail:
        assert cls in covered or green

`green` is non-empty whenever any green arm exists anywhere in the batch,
so the `or green` branch made the assertion true for every failure class
regardless of whether a single green arm was actually paired with it. The
check could not go red.

That is the same shape as a control arm that was never injected yet still
reports green: presence in the batch is read as coverage.

What the fixture set can and cannot express
--------------------------------------------
The published fixture set expresses the green side at batch level: one
batch-level control arm (class no_injection) plus three arms that prove
injector liveness, injector reach and a positive path. It does not carry
an explicit per-failure-class link, so a per-class pairing check is not
implementable on this data without changing the arms, which would change
the published digests. This file therefore checks the property the data
does express, and the checks below are written so that they can go red.

The gap itself is recorded rather than hidden: the criterion file states
the control-arm rule as one control arm per class, while the fixture set
carries one batch-level control arm. Aligning the two needs a criterion
version bump and is tracked as scheduled work, not as done.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_reliability"
ARMS_FILES = ("arms.jsonl", "arms_ext_v0.3.jsonl")
GREEN_ROLES = {"control_must_stay_green", "positive_must_stay_green"}


def _rows(directory: Path = FIXTURE_DIR) -> list[dict]:
    rows: list[dict] = []
    for name in ARMS_FILES:
        for line in (directory / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _batch_green_arm_present(rows: list[dict]) -> tuple[bool, str]:
    """A batch must carry at least one green arm, and it must be a real green.

    Every arm row carries an expected verdict, so a green arm is one whose
    role is a green role and whose expected verdict is PASS. Counting arms
    with a green role alone would let an arm that is expected to fail count
    as coverage.
    """
    green = [
        r
        for r in rows
        if r.get("control_direction") in GREEN_ROLES
        and r.get("expected_verdict") == "PASS"
    ]
    if not green:
        return False, "no arm with a green role and an expected PASS verdict"
    return True, f"{len(green)} green arm(s)"


def _green_arm_count(rows: list[dict]) -> int:
    return sum(
        1
        for r in rows
        if r.get("control_direction") in GREEN_ROLES
        and r.get("expected_verdict") == "PASS"
    )


def _must_fail_classes(rows: list[dict]) -> set[str]:
    return {r["class_id"] for r in rows if r.get("control_direction") == "must_fail"}


def _copy_to_tmp(tmp: Path) -> Path:
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(FIXTURE_DIR, tmp)
    return tmp


def _rewrite(tmp: Path, name: str, fn) -> None:
    lines = []
    for line in (tmp / name).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        fn(row)
        lines.append(json.dumps(row, ensure_ascii=False))
    (tmp / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_every_batch_carries_a_real_green_arm() -> None:
    """The green side of the batch must actually exist.

    A batch with zero green arms is a batch where every arm is expected to
    fail, so a green reading of that batch carries no information.
    """
    rows = _rows()
    ok, why = _batch_green_arm_present(rows)
    assert ok, f"batch has no usable green arm: {why}"


def test_green_arm_count_is_not_zero_and_is_not_derived_from_arms() -> None:
    """The green count must come from green arms, not from the arm total.

    This is the counting column a batch-level summary needs. Counting every
    arm and calling it coverage would read a batch of only failing arms as
    fully covered.
    """
    rows = _rows()
    green = _green_arm_count(rows)
    total = len(rows)
    assert green > 0, "green arm count is zero"
    assert green < total, (
        f"green arm count {green} equals the arm total {total}; "
        "the count is not discriminating between green and failing arms"
    )


def test_green_arms_are_not_expected_to_fail() -> None:
    """An arm whose expected verdict is FAIL must not be counted as green."""
    for row in _rows():
        if row.get("control_direction") in GREEN_ROLES:
            assert row.get("expected_verdict") == "PASS", (
                f"{row['case_id']}: green role but expected verdict "
                f"{row.get('expected_verdict')!r}"
            )


def test_the_green_check_can_go_red_when_the_green_arm_is_removed() -> None:
    """The green check must have discriminating power.

    A checker that cannot go red is not evidence. This removes every green
    arm from a copy of the fixture set and requires the same check to
    report failure on the copy.
    """
    tmp = _copy_to_tmp(Path(__file__).parent / "_tmp_pairing_check")
    try:
        for name in ARMS_FILES:
            _rewrite(
                tmp,
                name,
                lambda row: row.__setitem__(
                    "control_direction", "must_fail"
                )
                if row.get("control_direction") in GREEN_ROLES
                else None,
            )
        mutated = _rows(tmp)
        ok, why = _batch_green_arm_present(mutated)
        assert not ok, (
            "removing every green arm left the green check passing, "
            "so the check cannot detect a batch with no green side"
        )
        assert _green_arm_count(mutated) == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_the_green_check_can_go_red_when_a_green_arm_is_expected_to_fail() -> None:
    """A green role with a FAIL expectation must not satisfy the check.

    This is the shape where an arm sits in the batch in a green role but is
    expected to fail, so its presence says nothing about coverage.
    """
    tmp = _copy_to_tmp(Path(__file__).parent / "_tmp_pairing_check")
    try:
        for name in ARMS_FILES:
            _rewrite(
                tmp,
                name,
                lambda row: row.__setitem__("expected_verdict", "FAIL")
                if row.get("control_direction") in GREEN_ROLES
                else None,
            )
        mutated = _rows(tmp)
        ok, why = _batch_green_arm_present(mutated)
        assert not ok, (
            "turning every green arm into an expected failure left the green "
            "check passing"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_each_failure_class_appears_exactly_once() -> None:
    """Each failure class is exercised by exactly one must-fail arm."""
    rows = _rows()
    counts: dict[str, int] = {}
    for row in rows:
        if row.get("control_direction") == "must_fail":
            counts[row["class_id"]] = counts.get(row["class_id"], 0) + 1
    for cls, n in counts.items():
        assert n == 1, f"failure class {cls} appears {n} times, expected exactly 1"
    assert counts, "no must-fail arm in the batch"


def test_the_failure_class_set_is_not_empty() -> None:
    """A batch with no failing arm exercises nothing."""
    assert _must_fail_classes(_rows()), "batch carries no must-fail arm"
