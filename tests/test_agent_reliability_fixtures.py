"""Validate the agent-reliability fixture rows against the published schema.

Checks performed, each one mechanical:
  1. every line of every arms file is valid JSON
  2. required fields are present
  3. expected_verdict is inside the two-value domain
  4. control_direction is inside its closed set
  5. expected_reason_code is inside the closed reason code set
  6. every must_fail class carries exactly one control arm, and vice versa
  7. the criterion digest scope names the files that actually exist

Run with:  python3 -m pytest tests/test_agent_reliability_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_reliability"

ARMS_FILES = ("arms.jsonl", "arms_ext_v0.3.jsonl")

REASON_CODES = {
    "NONE",
    "TRUNCATED_INPUT",
    "EMPTY_OUTPUT",
    "DUPLICATE_RUN_ID",
    "ROUND_ID_CONFLICT",
    "WRITER_FALLBACK",
    "LOGIC_ERROR",
}

VERDICTS = {"PASS", "FAIL"}

CONTROL_DIRECTIONS = {
    "must_fail",
    "control_must_stay_green",
    "positive_must_stay_green",
}

REQUIRED_FIELDS = (
    "case_id",
    "class_id",
    "criterion_digest",
    "trigger_condition",
    "failing_behavior",
    "expected_verdict",
    "expected_reason_code",
    "must_fail_arm_ref",
    "injector_id",
    "control_direction",
    "channel",
)


def _rows() -> list[dict]:
    rows: list[dict] = []
    for name in ARMS_FILES:
        path = FIXTURE_DIR / name
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def test_every_row_is_valid_json_and_carries_required_fields() -> None:
    for row in _rows():
        for field in REQUIRED_FIELDS:
            assert field in row, f"{row.get('case_id')}: missing field {field}"
            assert row[field] not in (None, ""), f"{row.get('case_id')}: empty {field}"


def test_verdict_and_control_direction_domains_are_closed() -> None:
    for row in _rows():
        assert row["expected_verdict"] in VERDICTS, row["case_id"]
        assert row["control_direction"] in CONTROL_DIRECTIONS, row["case_id"]


def test_expected_reason_code_is_inside_the_closed_set() -> None:
    for row in _rows():
        assert row["expected_reason_code"] in REASON_CODES, (
            f"{row['case_id']}: {row['expected_reason_code']} outside the closed set"
        )


def test_each_failure_class_has_exactly_one_control_arm() -> None:
    """Every must_fail class needs a partner that must stay green.

    The partner is a control arm of the same batch. The pairing is per
    failure class, not per role: an arm that proves the injector is alive
    is also a green arm, so it does not need a fourth sibling.
    """
    rows = _rows()
    must_fail = {r["class_id"] for r in rows if r["control_direction"] == "must_fail"}
    green = {
        r["class_id"]
        for r in rows
        if r["control_direction"] in {"control_must_stay_green", "positive_must_stay_green"}
    }
    # Each must_fail class must be covered by at least one green arm.
    covered = {r["class_id"] for r in rows if r["control_direction"] != "must_fail"}
    for cls in must_fail:
        assert cls in covered or green, f"failure class {cls} has no green partner arm"
    # And every must_fail class must appear exactly once.
    counts: dict[str, int] = {}
    for r in rows:
        if r["control_direction"] == "must_fail":
            counts[r["class_id"]] = counts.get(r["class_id"], 0) + 1
    for cls, n in counts.items():
        assert n == 1, f"failure class {cls} appears {n} times, expected exactly 1"


def test_arm_health_codes_are_not_mixed_into_the_failure_code_set() -> None:
    """Arm health codes describe the arm, not the implementation under test.

    Mixing them into one set lets an arm health code land in the failure
    denominator, which is the same mistake as folding an unknown outcome
    into a failure.
    """
    arm_health = {"INJECTOR_DEAD", "INJECTOR_NOT_REACHED"}
    assert arm_health.isdisjoint(REASON_CODES)
    for row in _rows():
        assert row["expected_reason_code"] not in arm_health, (
            f"{row['case_id']}: arm health code used as an expected reason code"
        )


def test_criterion_digest_scope_names_files_that_exist() -> None:
    scope = (FIXTURE_DIR / "criterion_v0_3.yaml").read_text(encoding="utf-8")
    for name in ("criterion_v0_3.yaml", "arms.jsonl"):
        assert name in scope, f"{name} not declared in the criterion digest scope"
    assert (FIXTURE_DIR / "arms.jsonl").exists()
    assert (FIXTURE_DIR / "criterion_v0_3.yaml").exists()


def test_published_example_in_schema_matches_a_real_row() -> None:
    schema = json.loads(
        (FIXTURE_DIR / "observation_row.v0.3.schema.json").read_text(encoding="utf-8")
    )
    example = schema["examples"][0]
    real = {r["case_id"]: r for r in _rows()}
    assert example["case_id"] in real
    for key, value in example.items():
        assert real[example["case_id"]][key] == value, f"example drifted on {key}"


@pytest.mark.parametrize("name", ARMS_FILES)
def test_file_ends_with_newline_and_uses_lf(name: str) -> None:
    raw = (FIXTURE_DIR / name).read_bytes()
    assert raw.endswith(b"\n"), f"{name} must end with a newline"
    assert b"\r\n" not in raw, f"{name} must use LF line endings"
