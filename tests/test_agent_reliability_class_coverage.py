"""Class-level coverage checks for the agent-reliability fixture set.

Why this file exists
--------------------
The published fixture set carries four must-fail classes. Until this file
existed, nothing asserted that those four classes are still *there*.

What the existing checks actually covered, measured by mutation:

  Deleting an entire arm row, or flipping its expected_verdict from FAIL to
  PASS, and then regenerating manifest.sha256 the way a publisher legitimately
  would, left the whole suite green for three of the four classes. The only
  row that any check noticed was the one whose full text happens to be
  embedded in the published schema as its example row. That is a preimage for
  exactly one row, not a coverage rule.

The digest guard is not the answer. It catches a publisher who changes the
arms without refreshing the manifest, which is a staleness check, not a
correctness check. A publisher who changes the arms *and* refreshes the
manifest is self-consistent, and every digest they publish agrees with their
own bytes. This file is the part that does not depend on the digest.

Two different checks, because they catch different things:

  1. class presence   - a published class cannot quietly disappear
  2. verdict direction - a must-fail arm cannot quietly be declared green

Both are written so that they can go red, and both carry a mutation proof
that proves it.

Scope and honest boundary
-------------------------
The expected class list below is a frozen copy of what criterion:nf-v0.3
published. It is duplicated on purpose: it is an immutability assertion about
a version-pinned artefact, and a check that reads the thing it is checking
cannot assert that the thing is unchanged. Changing the published class set
is a criterion version bump, which changes the digests, which changes this
constant on purpose and in the same commit.

These checks cover the published fixture set only. They say nothing about
whether a downstream implementation actually fails on these classes. That
claim needs a cross-implementation run and stays out of this file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_reliability"
ARMS_FILES = ("arms.jsonl", "arms_ext_v0.3.jsonl")
GREEN_ROLES = {"control_must_stay_green", "positive_must_stay_green"}

# The four failure classes published in criterion:nf-v0.3.
# Frozen on purpose, see the module docstring.
PUBLISHED_FAILURE_CLASSES = frozenset(
    {
        "mid_file_truncation",
        "empty_payload",
        "duplicate_run_id",
        "round_id_conflict",
    }
)


def _rows(directory: Path = FIXTURE_DIR) -> list[dict]:
    rows: list[dict] = []
    for name in ARMS_FILES:
        for line in (directory / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


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


def test_every_published_failure_class_is_still_present() -> None:
    """A published must-fail class cannot disappear without going red.

    This is the reverse sample the network asked for: an arm that should be
    there, taken away entirely. Removing the row is not enough to go red on
    its own, because the digest guard only notices when the manifest is left
    stale. The check below does not read a digest at all.
    """
    present = _must_fail_classes(_rows())
    missing = PUBLISHED_FAILURE_CLASSES - present
    assert not missing, (
        f"published failure classes missing from the arms: {sorted(missing)}; "
        f"present: {sorted(present)}"
    )
    extra = present - PUBLISHED_FAILURE_CLASSES
    assert not extra, (
        f"arms carry failure classes that criterion:nf-v0.3 did not publish: "
        f"{sorted(extra)}"
    )


def test_every_must_fail_arm_declares_fail_with_a_non_none_reason_code() -> None:
    """A must-fail arm cannot be quietly declared green.

    Flipping expected_verdict to PASS would make the arm pass by
    declaration, so the failure it was supposed to exercise would never be
    exercised. The expected fields live on the arm, so the arm is exactly
    where this has to be checked.
    """
    for row in _rows():
        if row.get("control_direction") != "must_fail":
            continue
        assert row.get("expected_verdict") == "FAIL", (
            f"{row.get('case_id')}: must-fail arm declares "
            f"expected_verdict={row.get('expected_verdict')!r}; a must-fail arm "
            f"that expects PASS exercises nothing"
        )
        assert row.get("expected_reason_code") not in (None, "", "NONE"), (
            f"{row.get('case_id')}: must-fail arm carries no expected reason "
            f"code; a red with no reason code cannot be told apart from a "
            f"red for the wrong reason"
        )


def test_the_class_presence_check_can_go_red_when_a_class_is_removed() -> None:
    """The presence check must have discriminating power.

    A checker that cannot go red is not evidence. This removes one published
    class from a copy of the fixture set and requires the presence check to
    report it missing.
    """
    tmp = _copy_to_tmp(Path(__file__).parent / "_tmp_class_coverage")
    try:
        victim = "duplicate_run_id"
        _rewrite(
            tmp,
            "arms.jsonl",
            lambda row: row.__setitem__("class_id", "renamed_" + row["class_id"])
            if row.get("class_id") == victim
            else None,
        )
        present = _must_fail_classes(_rows(tmp))
        assert victim not in present, "the removal did not take effect"
        assert PUBLISHED_FAILURE_CLASSES - present, (
            "the presence check reported nothing missing after a published "
            "class was removed, so it cannot detect the removal"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_the_verdict_check_can_go_red_when_a_must_fail_arm_is_flipped() -> None:
    """The verdict-direction check must have discriminating power.

    This flips one must-fail arm to expect PASS and requires the verdict
    check to reject it.
    """
    tmp = _copy_to_tmp(Path(__file__).parent / "_tmp_class_coverage")
    try:
        victim = "empty_payload"

        def flip(row: dict) -> None:
            if row.get("class_id") == victim:
                row["expected_verdict"] = "PASS"
                row["expected_reason_code"] = "NONE"

        _rewrite(tmp, "arms.jsonl", flip)
        offenders = [
            r.get("case_id")
            for r in _rows(tmp)
            if r.get("control_direction") == "must_fail"
            and r.get("expected_verdict") != "FAIL"
        ]
        assert offenders, (
            "flipping a must-fail arm to expect PASS left the verdict check "
            "passing, so it cannot detect a must-fail arm declared green"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
