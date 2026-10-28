"""Per-arm content digests for the agent-reliability fixture set.

Why this file exists
---------------------
A peer on the network measured a shape we had not checked: a coverage check
that only compares the KEY SET of an arm row stays green when the VALUES
change collectively while the key set stays identical. On our own fixture set
that shape was real, and we measured it rather than assuming it:

  We changed the prose value of one non-example must-fail arm
  (the duplicate_run_id row, its trigger_condition text), regenerated
  manifest.sha256 the way a publisher legitimately would, and ran the whole
  suite. 461 passed. The digest guard was satisfied because the publisher
  refreshed it; every other check was satisfied because none of them read
  the value.

This file is the part that reads the value.

  A check that reads the thing it is checking cannot assert that the thing
  is unchanged. The manifest is written by the same publisher who writes the
  arms, so a publisher who changes an arm and refreshes the manifest is
  self-consistent by construction, and every digest they publish agrees
  with their own bytes. The manifest is a staleness check, not a
  correctness check.

  What closes the shape is a frozen copy of the per-arm content digest,
  held somewhere that the arm publisher does not rewrite. It is duplicated
  on purpose for the same reason the published failure class list is
  duplicated in tests/test_agent_reliability_class_coverage.py.

How the digest is computed
--------------------------
  Over the semantic fields of the arm row, canonicalised as sorted-key JSON
  with no whitespace and no trailing newline. Cosmetic fields are excluded,
  so reformatting a row is not read as a semantic change. This is a
  canonicalisation choice, and it is stated here so another implementation
  can reproduce it rather than guess.

  The digest is over the ARM, not over the whole file. A whole-file digest
  would also catch this shape, but it would not say WHICH arm changed, and
  a per-arm digest can be compared across implementations arm by arm.

Scope and honest boundary
-------------------------
This file asserts that the published arms still say what criterion:nf-v0.3
published. It says nothing about whether a downstream implementation
actually fails on these classes. That claim needs a cross-implementation
run and stays out of this file.

The frozen copy below covers the eight arms published in criterion:nf-v0.3.
Changing an arm is a criterion version bump, which changes the published
digests, which changes this constant on purpose and in the same commit.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_reliability"
ARMS_FILES = ("arms.jsonl", "arms_ext_v0.3.jsonl")

# The fields that carry the meaning of an arm. Excluding the cosmetic ones
# keeps a reformat from reading as a semantic change.
SEMANTIC_FIELDS = (
    "case_id",
    "class_id",
    "control_direction",
    "expected_verdict",
    "expected_reason_code",
    "trigger_condition",
    "failing_behavior",
    "must_fail_arm_ref",
    "injector_id",
    "channel",
    "criterion_digest",
)

# The per-arm content digests published in criterion:nf-v0.3.
# Frozen on purpose, see the module docstring.
PUBLISHED_ARM_DIGESTS = {
    "nf-mid-file-trunc-v1": ("78d90784fc2f9314e2b11be33a6c22cd6749ad073bd92bcd95055c571c403699", "mid_file_truncation"),
    "nf-empty-payload-v1": ("51fdf8290c3c077ea9325e714e8734d1945c215189c3c32708df9a8c7157bd4b", "empty_payload"),
    "nf-duplicate-run-id-v1": ("98dd04d6b916d86609df4dcfe013f2f2c7bd0cf1290818484802b341dffe875d", "duplicate_run_id"),
    "nf-round-id-conflict-v1": ("6a28b9ce9d048b1f3100a39899025e45a8214042ece9b9cf40ab2d6cde854baa", "round_id_conflict"),
    "nf-control-v1": ("9d8e347df7d532b4604d749c30416fe2f218117c61f6cf834693a3e6cddf5de7", "no_injection"),
    "nf-positive-valid-v1": ("bfa20276a093cad2918b8bcea9297b35d08f46457d304e8b7e791c0b378e69a3", "positive_valid_fixture"),
    "nf-liveness-noop-differs-v1": ("8f56a8d463fc056fa4c0c420b0a9092367d394ded8386698f15f3007a15fb6fd", "injector_liveness"),
    "nf-reach-injected-shape-v1": ("704781600ea5856864d8ac6c7f43e7e631b6dafa8d57127c27513e2774bfe58b", "injector_reach"),
}


def _rows(directory: Path = FIXTURE_DIR) -> list[dict]:
    rows: list[dict] = []
    for name in ARMS_FILES:
        for line in (directory / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _canonical(row: dict) -> str:
    subset = {k: row[k] for k in SEMANTIC_FIELDS if k in row}
    return json.dumps(subset, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _digest(row: dict) -> str:
    return hashlib.sha256(_canonical(row).encode("utf-8")).hexdigest()


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


def test_every_published_arm_still_has_the_published_content_digest() -> None:
    """An arm cannot change its content while the key set stays the same.

    This is the shape a key-set-only coverage check cannot see: the row
    still has every field, the same field names, the same class, and it
    still parses. Only the value moved.

    A publisher who changes an arm and refreshes manifest.sha256 is
    self-consistent by construction, so the manifest cannot catch this. The
    frozen per-arm digest can, because it is not written by the arm
    publisher.
    """
    rows = {r["case_id"]: r for r in _rows()}
    missing = sorted(set(PUBLISHED_ARM_DIGESTS) - set(rows))
    assert not missing, f"published arms missing from the fixture set: {missing}"

    changed = []
    for case_id, (expected_digest, expected_class) in PUBLISHED_ARM_DIGESTS.items():
        row = rows[case_id]
        assert row.get("class_id") == expected_class, (
            f"{case_id}: class is {row.get('class_id')!r}, "
            f"criterion:nf-v0.3 published {expected_class!r}"
        )
        actual = _digest(row)
        if actual != expected_digest:
            changed.append((case_id, expected_digest, actual))
    assert not changed, (
        "published arm content changed while the key set stayed identical; "
        "the manifest guard cannot see this because the publisher refreshes it: "
        + "; ".join(f"{cid} expected {exp} got {got}" for cid, exp, got in changed)
    )


def test_the_published_arm_set_is_exactly_the_published_set() -> None:
    """The fixture set carries the published arms and nothing else.

    Without this, a publisher could satisfy the digest check by dropping an
    arm whose digest check is skipped, or by adding an arm that no digest
    covers. Both directions have to be closed.
    """
    published = set(PUBLISHED_ARM_DIGESTS)
    present = {r["case_id"] for r in _rows()}
    missing = sorted(published - present)
    extra = sorted(present - published)
    assert not missing, f"published arms missing from the fixture set: {missing}"
    assert not extra, (
        f"fixture set carries arms that criterion:nf-v0.3 did not publish: {extra}"
    )


def test_the_digest_check_can_go_red_when_an_arm_value_changes() -> None:
    """The value check must have discriminating power.

    A checker that cannot go red is not evidence. This changes the VALUE of
    one arm, leaving the key set, the class and the row count untouched,
    and requires the digest check to report the change.

    This is the exact mutation that was measured against the whole suite
    before this check existed: the same edit, with the manifest refreshed the
    way a publisher legitimately would, left all 461 suite checks green.
    """
    tmp = _copy_to_tmp(Path(__file__).parent / "_tmp_arm_digest_check")
    try:
        victim = "nf-duplicate-run-id-v1"
        original = "aggregation silently deduplicates"
        mutated = "aggregation silently merges them"

        def change_value(row: dict) -> None:
            if row.get("case_id") == victim:
                assert original in row["trigger_condition"]
                row["trigger_condition"] = row["trigger_condition"].replace(
                    original, mutated
                )

        _rewrite(tmp, "arms.jsonl", change_value)

        # The key set is untouched, which is the whole point: a check that
        # only compared key sets would see nothing.
        before = {r["case_id"]: sorted(r.keys()) for r in _rows()}
        after = {r["case_id"]: sorted(r.keys()) for r in _rows(tmp)}
        assert before == after, "the key set changed, so this is not the target shape"

        rows = {r["case_id"]: r for r in _rows(tmp)}
        expected_digest, _ = PUBLISHED_ARM_DIGESTS[victim]
        assert _digest(rows[victim]) != expected_digest, (
            "changing the arm value did not change its digest, so the digest "
            "is not reading the value"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_the_digest_check_can_go_red_when_a_published_arm_is_removed() -> None:
    """Removing an arm must be caught by the same check.

    The digest guard against the manifest cannot see this, because the
    publisher refreshes the manifest and the remaining arms are untouched.
    """
    tmp = _copy_to_tmp(Path(__file__).parent / "_tmp_arm_digest_check")
    try:
        victim = "nf-empty-payload-v1"

        def drop(row: dict) -> None:
            if row.get("case_id") == victim:
                row["case_id"] = "nf-empty-payload-v2"

        _rewrite(tmp, "arms.jsonl", drop)

        rows = {r["case_id"]: r for r in _rows(tmp)}
        assert victim not in rows, "the removal did not take effect"
        assert set(PUBLISHED_ARM_DIGESTS) - set(rows), (
            "removing a published arm left the digest check passing, so it "
            "cannot detect a published arm that disappeared"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
