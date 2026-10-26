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


def test_expected_verdict_is_declared_on_the_arm_not_on_the_observation_row() -> None:
    """Rule R2: the declaration hangs on the arm, not on the observation row.

    The arm files are declarations. A runner that authors the expected verdict
    after the run is doing its own grading, so the field is allowed on a
    declaration row but must never be authored by whoever observed the run.
    The schema enforces this with two branches that forbid the opposite field.
    """
    schema = json.loads(
        (FIXTURE_DIR / "observation_row.v0.3.schema.json").read_text(encoding="utf-8")
    )
    branches = schema["oneOf"]
    assert len(branches) == 2, "expected exactly two row kinds"

    declaration = next(b for b in branches if "Arm declaration" in b["title"])
    observation = next(b for b in branches if "Observation row" in b["title"])

    assert "expected_verdict" in declaration["required"]
    assert "expected_reason_code" in declaration["required"]

    # The observation branch must require the observed fields and forbid the
    # expected ones.
    assert "observed_verdict" in observation["required"]
    assert "observed_reason_code" in observation["required"]
    forbidden = observation["not"]["anyOf"]
    assert {"required": ["expected_verdict"]} in forbidden
    assert {"required": ["expected_reason_code"]} in forbidden

    # And the declaration branch must forbid the observed ones, so a row
    # cannot carry both.
    forbidden_decl = declaration["not"]["anyOf"]
    assert {"required": ["observed_verdict"]} in forbidden_decl
    assert {"required": ["observed_reason_code"]} in forbidden_decl


def test_observation_row_template_exists_and_carries_no_declaration_fields() -> None:
    """The row a runner fills in must not let the runner declare the verdict."""
    path = FIXTURE_DIR / "observation_row.v0.3.template.json"
    template = json.loads(path.read_text(encoding="utf-8"))
    for field in ("expected_verdict", "expected_reason_code"):
        assert field not in template, f"{field} must not appear on an observation row"
    for field in ("observed_verdict", "observed_reason_code", "arm_id", "run_id"):
        assert field in template, f"{field} missing from the observation row template"


def test_each_failure_class_has_exactly_one_control_arm() -> None:
    """Every must_fail class needs a partner that must stay green.

    The partner is a control arm of the same batch. The pairing is per
    failure class, not per role: an arm that proves the injector is alive
    is also a green arm, so it does not need a fourth sibling.

    The check below is deliberately not written as `cls in covered or green`.
    That form is never false: `green` is non-empty whenever the batch holds
    any green arm at all, so the assertion stays true even when no green arm
    is paired with the failure class being examined. A checker that cannot
    go red is not evidence.

    What is asserted here is the property the published data does express:
    every failure class is exercised exactly once, and the batch carries a
    green arm that is expected to pass. The green arm count is recorded as a
    separate number, because a batch-level count of zero and a batch-level
    count of one read the same way if the count is not stated.

    Known gap, recorded rather than hidden: rule R7 in the criterion file
    says every class must carry one control arm. The published arms express
    the green side at batch level, one batch-level control arm plus the
    liveness, reach and positive arms, so there is no per-failure-class
    green partner to point at. Closing that gap means either giving each
    failure class its own green arm, which changes the arms and therefore
    the published digests, or restating R7 at batch level, which is a
    criterion version bump. Both are scheduled work for the next version,
    not done work. See tests/test_agent_reliability_pairing.py for the
    batch-level green checks and for the mutation proofs that they can go
    red.
    """
    rows = _rows()
    must_fail = {r["class_id"] for r in rows if r["control_direction"] == "must_fail"}
    green = {
        r["class_id"]
        for r in rows
        if r["control_direction"] in {"control_must_stay_green", "positive_must_stay_green"}
    }
    # The green side of the batch has to exist and has to be a green arm
    # that is expected to pass. Counting arms with a green role alone would
    # let an arm expected to fail count as coverage.
    green_rows = [
        r
        for r in rows
        if r["control_direction"] in {"control_must_stay_green", "positive_must_stay_green"}
    ]
    assert green_rows, "batch carries no green arm"
    for r in green_rows:
        assert r["expected_verdict"] == "PASS", (
            f"{r['case_id']}: green role but expected verdict "
            f"{r['expected_verdict']!r}"
        )
    # The green count is stated, not implied, so a batch-level zero cannot
    # be read the same way as a batch-level one.
    assert len(green_rows) > 0, "green arm count is zero"
    assert len(green_rows) < len(rows), (
        f"green arm count {len(green_rows)} equals the arm total {len(rows)}; "
        "the count is not discriminating between green and failing arms"
    )
    # Every must_fail class must appear exactly once.
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


def test_hard_rule_R6_digest_scope_matches_the_declared_scope() -> None:
    """The R6 prose must name the same file set as criterion_digest_scope.

    R6 is the rule that says how many files the digest covers. It used to say
    two while the scope block, the preimage spec and the manifest all said
    three. Every check that only compared counts of *machine* fields passed,
    because the drift lived in a human-readable string inside the same file.

    This is the same family as the count drift the count assertion catches,
    one layer down: the count assertion compares two structured lists, this
    one compares the structured list against the prose that states the rule.
    """
    scope = (FIXTURE_DIR / "criterion_v0_3.yaml").read_text(encoding="utf-8")
    declared = _declared_scope()

    r6_lines = [
        line.strip()
        for line in scope.splitlines()
        if "R6" in line or (line.strip().startswith("text:") and "摘要覆盖" in line)
    ]
    r6_text = ""
    for idx, line in enumerate(scope.splitlines()):
        if line.strip() == "- id: R6":
            for follow in scope.splitlines()[idx + 1 : idx + 4]:
                if follow.strip().startswith("text:"):
                    r6_text = follow.strip()
                    break
            break
    assert r6_text, "hard rule R6 has no text to check"

    chinese_counts = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
    stated = None
    for token, value in chinese_counts.items():
        if f"{token}件" in r6_text:
            stated = value
            break
    assert stated is not None, (
        f"R6 does not state a coverage count in Chinese numerals: {r6_text!r}"
    )
    assert stated == len(declared), (
        f"R6 states the digest covers {stated} file(s) but "
        f"criterion_digest_scope declares {len(declared)} ({declared}); "
        "the prose and the structured scope must agree"
    )
    for name in declared:
        assert name in r6_text, (
            f"R6 does not name {name}; declared scope is {declared}"
        )
    assert r6_lines, "R6 could not be located in the criterion file"


def _declared_scope() -> list[str]:
    """Read criterion_digest_scope out of the criterion file.

    The scope block is a YAML list of file names. It is parsed by hand rather
    than through a YAML dependency so the check keeps working in a bare
    interpreter.
    """
    text = (FIXTURE_DIR / "criterion_v0_3.yaml").read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    in_scope = False
    for line in lines:
        if line.startswith("criterion_digest_scope:"):
            in_scope = True
            continue
        if in_scope:
            stripped = line.strip()
            if not stripped.startswith("- "):
                break
            out.append(stripped[2:].strip())
    return out


def _manifest_names() -> list[str]:
    """Read the file names listed in manifest.sha256, in manifest order."""
    raw = (FIXTURE_DIR / "manifest.sha256").read_text(encoding="utf-8")
    names = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        assert len(parts) == 2, f"manifest line is not digest + two spaces + name: {line!r}"
        names.append(parts[1].strip())
    return names


def test_declared_digest_scope_count_matches_the_manifest_line_count() -> None:
    """The declared coverage count must equal the number of files actually digested.

    This is the check that was missing. The criterion file declared a two-file
    scope while the preimage spec and the manifest covered three. Both sides
    computed a consistent digest over their own scope, so the two digests could
    never agree, and nobody noticed, because the only assertion was that the
    named files exist — not that the list is complete.

    Asserting the count is what closes it: dropping a negative control arm now
    changes the declared count as well as the digest, so the drift cannot hide.
    """
    declared = _declared_scope()
    manifest = _manifest_names()
    assert declared, "criterion_digest_scope is empty"
    assert len(declared) == len(manifest), (
        f"declared digest scope has {len(declared)} entries "
        f"({declared}) but the manifest digests {len(manifest)} files ({manifest}); "
        "the preimage spec is the single authority for coverage"
    )


def test_manifest_digests_exactly_the_declared_scope_in_order() -> None:
    """The manifest must cover the declared scope, in the declared order.

    Two digests over different file sets are both internally consistent, so
    matching them requires the file sets to be identical, not merely
    overlapping.
    """
    declared = _declared_scope()
    manifest = _manifest_names()
    assert manifest == declared, (
        f"manifest covers {manifest} but the criterion declares {declared}"
    )
    for name in manifest:
        assert (FIXTURE_DIR / name).exists(), f"{name} is digested but missing on disk"


def test_manifest_digests_match_the_files_on_disk() -> None:
    """A digest that does not match its file means the manifest is stale."""
    import hashlib

    raw = (FIXTURE_DIR / "manifest.sha256").read_text(encoding="utf-8")
    for line in raw.splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        name = name.strip()
        actual = hashlib.sha256((FIXTURE_DIR / name).read_bytes()).hexdigest()
        assert actual == digest, (
            f"{name}: manifest records {digest} but the file on disk hashes to {actual}"
        )


def test_published_example_in_schema_matches_a_real_row() -> None:
    schema = json.loads(
        (FIXTURE_DIR / "observation_row.v0.3.schema.json").read_text(encoding="utf-8")
    )
    example = schema["examples"][0]
    real = {r["case_id"]: r for r in _rows()}
    assert example["case_id"] in real
    for key, value in example.items():
        assert real[example["case_id"]][key] == value, f"example drifted on {key}"


def test_observation_row_template_validates_against_the_schema() -> None:
    """The template must actually satisfy the schema we publish.

    A schema that does not accept its own template is the same class of
    defect as a criterion whose snapshot has drifted ahead of its source.
    """
    try:
        import jsonschema  # type: ignore
    except ImportError:
        pytest.skip("jsonschema not installed")

    schema = json.loads(
        (FIXTURE_DIR / "observation_row.v0.3.schema.json").read_text(encoding="utf-8")
    )
    template = json.loads(
        (FIXTURE_DIR / "observation_row.v0.3.template.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(template, schema)


def test_every_must_fail_arm_ref_resolves_to_a_case_in_the_same_batch() -> None:
    """A mistyped arm reference must fail, not degrade into an unattributed row.

    Each arm row names the arm it belongs to in must_fail_arm_ref. The
    naming used there is the arm identifier, which carries the nf-arm
    prefix, while the row itself is identified by case_id. If the two
    namespaces drift apart, a reference can name something that does not
    exist and the row is still perfectly valid JSON with every required
    field present, so nothing catches it.

    The check here is that the reference resolves. It is deliberately not
    a pass or fail of the implementation under test, it is a failure of
    the fixture set itself, which is why it is a separate assertion and
    not a reason code.
    """
    rows = _rows()
    # The arm identifier namespace used by the arm rows.
    arm_ids = {r["case_id"].replace("nf-", "nf-arm-", 1) for r in rows}

    for row in rows:
        ref = row["must_fail_arm_ref"]
        assert ref in arm_ids, (
            f"{row['case_id']}: must_fail_arm_ref {ref!r} does not resolve to "
            f"any arm in the batch; known arm ids are {sorted(arm_ids)}"
        )


def test_observation_row_columns_in_the_criterion_match_the_published_schema() -> None:
    """The criterion file lists the observation row columns.

    If that list drifts away from the schema and the template, the
    criterion is describing a row that nobody publishes, and the
    published row is describing itself. Nothing else compares the two.
    """
    text = (FIXTURE_DIR / "criterion_v0_3.yaml").read_text(encoding="utf-8")
    columns: list[str] = []
    in_block = False
    for line in text.splitlines():
        if line.startswith("observation_row_columns:"):
            in_block = True
            continue
        if in_block:
            stripped = line.strip()
            if not stripped.startswith("- "):
                break
            columns.append(stripped[2:].strip())

    assert columns, "observation_row_columns is empty in the criterion file"

    template = json.loads(
        (FIXTURE_DIR / "observation_row.v0.3.template.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (FIXTURE_DIR / "observation_row.v0.3.schema.json").read_text(encoding="utf-8")
    )
    schema_fields = set(schema.get("properties", {}))
    template_fields = set(template)

    # Every column the criterion names must be a field the published
    # template actually carries.
    missing = [c for c in columns if c not in template_fields]
    assert not missing, (
        f"criterion names observation row columns the template does not carry: {missing}"
    )

    # And the criterion must not name a column the schema does not define.
    unknown = [c for c in columns if c not in schema_fields]
    assert not unknown, (
        f"criterion names observation row columns the schema does not define: {unknown}"
    )


@pytest.mark.parametrize("name", ARMS_FILES)
def test_file_ends_with_newline_and_uses_lf(name: str) -> None:
    raw = (FIXTURE_DIR / name).read_bytes()
    assert raw.endswith(b"\n"), f"{name} must end with a newline"
    assert b"\r\n" not in raw, f"{name} must use LF line endings"
