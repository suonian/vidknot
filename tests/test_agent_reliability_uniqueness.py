"""Reason-code uniqueness over the assembled arm set.

Why this file exists
---------------------
A peer on the network pointed at a shape we had not checked. Their wording:
a uniqueness criterion must read the arm set that was actually assembled
after parsing, not a published listing of it. A listing can be clean while
the assembled set carries a collision, because the listing is written by the
publisher and the assembled set is what the runner actually holds.

On our own set the gap was real, and we measured it rather than assuming it.
The published arms declare one expected reason code per arm, and nothing in
this repository compared those codes across arms. Two arms could declare the
same failure reason code and every existing check would still pass: each
code was inside the closed set, each must-fail arm declared some reason, and
the binding check compares a run against the arm it reports on, one arm at a
time. A collision is a relation between two arms, and no check related two
arms to each other.

What this file adds
-------------------
  1. the uniqueness rule is stated once, as a function
  2. it is applied to the rows read from the parsed arm files
  3. it is applied to the raw reason codes, not to a normalised key
  4. three mutation proofs, one per direction of the failure

Scope and honest boundary
-------------------------
The published failure codes carry no family prefix, so the assembled set
today holds no pair that differs only by a prefix. This file therefore
proves two things and stops there: a raw duplicate is caught, and a pair
that collides only after normalisation is not folded into a raw collision.
It does not claim that a same-type negative case exists in the published
set. That case is still paper, and the reason is recorded here rather than
implied away.

Scope note on the object of the check
--------------------------------------
The rule reads rows parsed out of the arm files. The manifest is a listing
of files with their digests, and it is not the object of this rule. This
file asserts the two are different objects, so a future change that quietly
points the uniqueness rule at the manifest is caught instead of passing.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_reliability"
ARMS_FILES = ("arms.jsonl", "arms_ext_v0.3.jsonl")
MANIFEST_NAME = "manifest.sha256"


def _rows(directory: Path = FIXTURE_DIR) -> list[dict]:
    """The assembled arm set: every row parsed out of the published arms.

    Two files, eight rows. The manifest is not consulted here on purpose.
    """
    rows: list[dict] = []
    for name in ARMS_FILES:
        for line in (directory / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def uniqueness_violations(rows: list[dict]) -> list[str]:
    """Return why a raw reason code is declared by more than one must-fail arm.

    The rule, in one place:

      a must-fail arm declares the reason its run is expected to fail for,
      and no two must-fail arms may declare the same reason. If they do,
      the two arms cannot be told apart by the reason they report, so a run
      that failed for one of them is evidence for neither in particular.

    Only must-fail arms are compared. A green arm declares NONE, and NONE
    is not a failure reason, so several green arms declaring it is not a
    collision and is not a violation.

    The comparison is on the raw code. A normalised key would fold codes
    that differ only by a family prefix, and folding them here would hide
    exactly the case this criterion exists to catch.
    """
    seen: dict[str, list[str]] = {}
    for row in rows:
        if row.get("control_direction") != "must_fail":
            continue
        code = row.get("expected_reason_code")
        if code in (None, "", "NONE"):
            # A must-fail arm with no reason is a different defect, checked
            # by the reason-binding module. It is not counted as a
            # collision here, because two such arms would collide on an
            # absent value rather than on a reason code.
            continue
        seen.setdefault(str(code), []).append(str(row.get("case_id")))
    return [
        f"reason code {code} is declared by {sorted(cases)}"
        for code, cases in sorted(seen.items())
        if len(cases) > 1
    ]


def _normalise_key(code: str) -> str:
    """The normalisation a peer described: drop a family prefix, lowercase.

    Used only by the test that proves the raw criterion is not folded onto a
    normalised key. Not used by the rule itself.
    """
    tail = str(code).rsplit(".", 1)[-1]
    return tail.lower()


def test_the_checked_object_is_the_assembled_arm_set_not_the_manifest() -> None:
    """The rule must read parsed rows, and the manifest is a different object.

    A published listing can be clean while the assembled set carries a
    collision, because the listing is written by the publisher and the
    assembled set is what the runner holds. If the rule were pointed at the
    listing, this file would assert the wrong thing and still be green.
    """
    rows = _rows()
    assert len(rows) == 8, (
        f"the assembled arm set should be eight parsed rows, got {len(rows)}"
    )
    must_fail = [r for r in rows if r.get("control_direction") == "must_fail"]
    green = [r for r in rows if r.get("control_direction") != "must_fail"]
    assert len(must_fail) == 4, f"expected four must-fail arms, got {len(must_fail)}"
    assert len(green) == 4, f"expected four green arms, got {len(green)}"

    manifest_lines = [
        line
        for line in (FIXTURE_DIR / MANIFEST_NAME).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(manifest_lines) == 3, (
        f"the manifest lists files, not arms: expected three lines, "
        f"got {len(manifest_lines)}"
    )
    for line in manifest_lines:
        assert "arms.jsonl" not in line or line.rstrip().endswith("arms.jsonl"), (
            "a manifest line names a file, so it cannot be the uniqueness object"
        )


def test_failure_reason_codes_are_unique_across_the_assembled_arm_set() -> None:
    """No two must-fail arms may declare the same raw reason code."""
    violations = uniqueness_violations(_rows())
    assert not violations, (
        "raw reason codes collide across must-fail arms: " + "; ".join(violations)
    )


def test_green_arms_declaring_none_are_not_a_collision() -> None:
    """Several green arms declaring NONE is not a violation.

    The rule must not flag the normal case where every green arm declares
    the absence of a failure reason.
    """
    rows = _rows()
    green_codes = [
        r.get("expected_reason_code")
        for r in rows
        if r.get("control_direction") != "must_fail"
    ]
    assert green_codes.count("NONE") >= 3, (
        f"expected several green arms declaring NONE, got {green_codes}"
    )
    assert not uniqueness_violations(rows), (
        "green arms declaring NONE must not be reported as a collision"
    )


def test_the_rule_goes_red_on_a_duplicated_raw_reason_code() -> None:
    """The rule must have discriminating power over the raw codes.

    This copies the fixture set, rewrites one must-fail arm's declared
    reason so it collides with another must-fail arm, and requires the rule
    to report the collision. A rule that read the closed set, or that read
    one arm at a time, would still accept it.
    """
    tmp = FIXTURE_DIR.parent.parent / "_tmp_uniqueness_check"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(FIXTURE_DIR, tmp)
    try:
        victim = "nf-empty-payload-v1"
        collide_with = "nf-mid-file-trunc-v1"
        original = "EMPTY_OUTPUT"
        replaced = "TRUNCATED_INPUT"

        path = tmp / "arms.jsonl"
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("case_id") == victim:
                row["expected_reason_code"] = replaced
            lines.append(json.dumps(row, ensure_ascii=False))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        mutated = _rows(tmp)
        codes = {
            r["case_id"]: r.get("expected_reason_code")
            for r in mutated
            if r.get("control_direction") == "must_fail"
        }
        assert codes[victim] == replaced, "the rewrite did not apply"
        assert codes[collide_with] == replaced, (
            "the fixture copy did not produce the collision this test needs"
        )

        violations = uniqueness_violations(mutated)
        assert violations, (
            "two must-fail arms declaring the same raw reason code were not "
            "reported, so the uniqueness rule cannot catch a collision"
        )
        assert any(replaced in v for v in violations), (
            f"the violation does not name the colliding code: {violations}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_a_pair_colliding_only_after_normalisation_is_not_a_raw_collision() -> None:
    """The raw rule must not fold a normalised collision into a raw one.

    Two arms whose raw codes differ only by a family prefix normalise to
    the same key. That pair is the shape a same-type negative case would
    have. The uniqueness criterion here is on the raw code, so it must
    accept the pair. If the rule were folded onto the normalised key, it
    would report a collision that the criterion does not define, and the
    distinction between the two layers would be lost in the check itself.
    """
    pair = [
        {
            "case_id": "nf-synthetic-alpha-v1",
            "control_direction": "must_fail",
            "expected_reason_code": "NF_ALPHA.EMPTY_PAYLOAD",
        },
        {
            "case_id": "nf-synthetic-beta-v1",
            "control_direction": "must_fail",
            "expected_reason_code": "NF_BETA.EMPTY_PAYLOAD",
        },
    ]
    raw_codes = [row["expected_reason_code"] for row in pair]
    assert len(set(raw_codes)) == 2, "the two raw codes must differ for this test"
    assert _normalise_key(raw_codes[0]) == _normalise_key(raw_codes[1]), (
        "the two codes must normalise to the same key for this test"
    )
    assert not uniqueness_violations(pair), (
        "a pair that differs only by family prefix is not a raw collision, "
        "and folding it into one would hide the case the raw criterion exists "
        "to catch"
    )
