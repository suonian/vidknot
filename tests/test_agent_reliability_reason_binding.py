"""Reason-code binding for the agent-reliability fixture set.

Why this file exists
--------------------
A peer on the network pointed at a shape we had not checked. Their wording:
a negative control must not merely assert "the run failed", it must assert
"the run failed for the expected reason". Their instance was the sharpest
version of the shape: the control did fail, but not for the reason they had
declared, because the rule identifier was wrong. The control reported a
failure, the failure was real, and the criterion was doing no work at all.

On our own set that gap was real, and we measured it rather than assuming
it. The published arms declare one expected_reason_code per arm, the
published observation row carries one observed_reason_code per run, and
nothing in this repository compared the two. Every check that read either
side on its own was satisfied by a run that failed for the wrong reason: a
control whose expected code was DUPLICATE_RUN_ID still passed when the run
failed because the payload was empty.

That is the same family this repo keeps finding in other implementations,
one layer down. The fact existed and was readable, but no consumer read
both halves at once, so the two could drift apart undetected.

What this file adds
-------------------
  1. the binding rule is stated once, as a function, so there is one place
     that decides what "failed for the expected reason" means
  2. the published observation row is checked against the arm it reports on
  3. a synthetic observation row is built from every published arm, and the
     rule is required to accept the correctly-reasoned one and reject the
     wrong-reason one
  4. a mutation proof that the rule can go red

Scope and honest boundary
--------------------------
This file asserts what the published fixture set expresses: the binding
rule, and that the published template satisfies it. It does not assert that
any downstream implementation actually fails on these classes. That claim
needs a cross-implementation run and stays out of this file.

The published observation row schema keeps observed_reason_code as a free
string, so a runner may report a code that is outside the published closed
set. The schema's own description says such a code goes to its own bucket
rather than folding into the nearest known code, so this file does not
reject an unknown code outright. It rejects it where it matters: a run
reported as FAIL must carry the reason code its arm declared, and a run
reported as anything other than FAIL may not carry a failure reason code
at all. An unrecognised code on a FAIL row is therefore rejected by the
equality rule, not by a separate closed-set rule.

What this file does not implement
---------------------------------
A control that keeps failing can rot into being caught by some other
mechanism, so it stops exercising the criterion it was written for. The
peer's second point, that controls have to be rotated, is not implemented
here and is recorded as scheduled work rather than described as done.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_reliability"
ARMS_FILES = ("arms.jsonl", "arms_ext_v0.3.jsonl")

# The arm identifier namespace used by the arm rows. The rows themselves are
# named by case_id; the arm identifier carries the nf-arm prefix. The
# observation row carries both, so either one resolves to a published arm.
_ARM_PREFIX = "nf-"


def _rows(directory: Path = FIXTURE_DIR) -> list[dict]:
    rows: list[dict] = []
    for name in ARMS_FILES:
        for line in (directory / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _arms_by_case_id() -> dict[str, dict]:
    return {r["case_id"]: r for r in _rows()}


def _case_id_for_arm(arm_id: str) -> str:
    """Map an arm identifier back to the case identifier of the same arm."""
    if arm_id.startswith("nf-arm-"):
        return "nf-" + arm_id[len("nf-arm-") :]
    return arm_id


def _resolve_arm(observation: dict) -> dict | None:
    """Find the published arm an observation row reports on."""
    arms = _arms_by_case_id()
    for key in ("case_id", "arm_id"):
        value = observation.get(key)
        if not value:
            continue
        candidate = value if key == "case_id" else _case_id_for_arm(value)
        if candidate in arms:
            return arms[candidate]
    return None


def _declared_reason_codes() -> tuple[set[str], set[str]]:
    """Read the two published reason-code sets out of the criterion file.

    The criterion file is the authority for which codes mean what. Parsing it
    here means the check follows the published sets rather than a constant
    copied next to the check, which would be a second thing to keep in step.
    """
    text = (FIXTURE_DIR / "criterion_v0_3.yaml").read_text(encoding="utf-8")
    failure: set[str] = set()
    health: set[str] = set()
    target: set[str] | None = None
    for line in text.splitlines():
        if line.startswith("reason_code_set:"):
            target = failure
            continue
        if line.startswith("arm_health_reason_code_set:"):
            target = health
            continue
        if target is None:
            continue
        stripped = line.strip()
        if not stripped.startswith("- "):
            target = None
            continue
        target.add(stripped[2:].split("#")[0].strip())
    return failure, health


def binding_violation(observation: dict, arm: dict) -> str | None:
    """Return why an observation row fails to match its arm, or None.

    The rule, in one place:

      FAIL  must carry the reason code the arm declared. A run that failed
            for a different reason is not evidence that this arm was
            exercised.
      PASS  must carry NONE. A green run cannot claim a failure layer.
      any other verdict must not carry a failure reason code at all. Those
            verdicts are the ones that mean "not evaluated", and naming a
            failure layer on them asserts something the run did not show.

    An arm health code describes the arm rather than the implementation under
    test, so it is never accepted as the observed reason code here.
    """
    failure_codes, health_codes = _declared_reason_codes()
    observed_verdict = observation.get("observed_verdict")
    observed_reason = observation.get("observed_reason_code")
    expected_reason = arm.get("expected_reason_code")

    if observed_verdict == "FAIL":
        if observed_reason in health_codes:
            return (
                f"observed_reason_code {observed_reason!r} is an arm health code; "
                "it describes the arm, not the implementation under test"
            )
        if observed_reason != expected_reason:
            return (
                f"the run failed for reason {observed_reason!r} but the arm "
                f"declared {expected_reason!r}; a failure for a different "
                "reason is not evidence that this arm was exercised"
            )
        return None

    if observed_verdict == "PASS":
        if observed_reason != "NONE":
            return (
                f"observed_verdict is PASS but observed_reason_code is "
                f"{observed_reason!r}; a green run cannot claim a failure layer"
            )
        return None

    # NOT_EXERCISED, NOT_APPLICABLE, UNKNOWN, or a verdict this file does
    # not know about. None of them may name a failure layer.
    if observed_reason in failure_codes and observed_reason != "NONE":
        return (
            f"observed_verdict {observed_verdict!r} may not carry the failure "
            f"reason code {observed_reason!r}; that verdict means the run did "
            "not establish a failure layer"
        )
    return None


def _observation_for(arm: dict, verdict: str, reason: str) -> dict:
    """Build a synthetic observation row reporting on the given arm."""
    return {
        "arm_id": arm["case_id"].replace(_ARM_PREFIX, "nf-arm-", 1),
        "case_id": arm["case_id"],
        "class_id": arm["class_id"],
        "control_direction": arm["control_direction"],
        "observed_verdict": verdict,
        "observed_reason_code": reason,
        "run_id": "run-0000",
    }


def test_the_published_observation_row_satisfies_the_binding() -> None:
    """The published template must be a correctly-reasoned observation.

    A published template that would be rejected by this file's own rule is a
    template that teaches the wrong thing, so it is checked rather than
    assumed.
    """
    template = json.loads(
        (FIXTURE_DIR / "observation_row.v0.3.template.json").read_text(encoding="utf-8")
    )
    arm = _resolve_arm(template)
    assert arm is not None, (
        "the published observation row template does not resolve to a published "
        f"arm; template identifiers: {template.get('case_id')!r}, "
        f"{template.get('arm_id')!r}"
    )
    violation = binding_violation(template, arm)
    assert violation is None, (
        f"the published observation row template violates the reason-code "
        f"binding for arm {arm['case_id']!r}: {violation}"
    )


def test_every_must_fail_arm_has_a_declared_reason_to_match_against() -> None:
    """A must-fail arm must declare the reason its run is expected to fail for.

    Without a declared reason there is nothing for an observation to match,
    so the arm cannot be checked for the right reason at all. A must-fail arm
    declaring NONE is the same defect: it says "fail, for no particular
    reason", which is exactly the shape that let a wrong-reason failure pass.
    """
    offenders = []
    for arm in _rows():
        if arm.get("control_direction") != "must_fail":
            continue
        reason = arm.get("expected_reason_code")
        if reason in (None, "", "NONE"):
            offenders.append(arm.get("case_id"))
    assert not offenders, (
        "must-fail arms that declare no reason to fail for: "
        f"{sorted(offenders)}; a failure without a declared reason cannot be "
        "told apart from a failure for the wrong reason"
    )


def test_a_correctly_reasoned_failure_is_accepted() -> None:
    """The rule must accept the run it is meant to accept."""
    checked = 0
    for arm in _rows():
        if arm.get("control_direction") != "must_fail":
            continue
        observation = _observation_for(
            arm, "FAIL", str(arm.get("expected_reason_code"))
        )
        violation = binding_violation(observation, arm)
        assert violation is None, (
            f"{arm['case_id']}: a failure carrying the declared reason "
            f"{arm.get('expected_reason_code')!r} was rejected: {violation}"
        )
        checked += 1
    assert checked, "no must-fail arm to check"


def test_a_wrongly_reasoned_failure_is_rejected() -> None:
    """The rule must reject a failure that carries the wrong reason.

    This is the shape the peer described: the control did fail, and the
    failure was real, but it was not the failure the control was written to
    detect. A rule that only checked the verdict would pass this row.
    """
    other_reason = "EMPTY_OUTPUT"
    rejected = []
    for arm in _rows():
        if arm.get("control_direction") != "must_fail":
            continue
        declared = arm.get("expected_reason_code")
        wrong = other_reason if declared != other_reason else "LOGIC_ERROR"
        observation = _observation_for(arm, "FAIL", wrong)
        violation = binding_violation(observation, arm)
        assert violation is not None, (
            f"{arm['case_id']}: a failure carrying the wrong reason "
            f"{wrong!r} was accepted; the rule only checked the verdict"
        )
        rejected.append(arm["case_id"])
    assert rejected, "no must-fail arm to check"


def test_a_failure_with_no_reason_is_rejected() -> None:
    """A red with no reason code is not evidence of the declared failure."""
    for arm in _rows():
        if arm.get("control_direction") != "must_fail":
            continue
        observation = _observation_for(arm, "FAIL", "NONE")
        violation = binding_violation(observation, arm)
        assert violation is not None, (
            f"{arm['case_id']}: a failure carrying no reason code was accepted"
        )


def test_a_green_run_cannot_claim_a_failure_layer() -> None:
    """PASS with a failure reason code is a contradiction and is rejected."""
    for arm in _rows():
        if arm.get("control_direction") != "must_fail":
            continue
        observation = _observation_for(arm, "PASS", str(arm.get("expected_reason_code")))
        violation = binding_violation(observation, arm)
        assert violation is not None, (
            f"{arm['case_id']}: a PASS row claiming the failure layer "
            f"{arm.get('expected_reason_code')!r} was accepted"
        )


def test_an_unevaluated_verdict_cannot_claim_a_failure_layer() -> None:
    """NOT_EXERCISED and friends must not name a failure layer."""
    failure_codes, _ = _declared_reason_codes()
    for verdict in ("NOT_EXERCISED", "NOT_APPLICABLE", "UNKNOWN"):
        for arm in _rows():
            if arm.get("control_direction") != "must_fail":
                continue
            for reason in sorted(failure_codes):
                if reason == "NONE":
                    continue
                observation = _observation_for(arm, verdict, reason)
                violation = binding_violation(observation, arm)
                assert violation is not None, (
                    f"{arm['case_id']}: a {verdict} row claiming the failure "
                    f"layer {reason!r} was accepted"
                )


def test_the_binding_check_can_go_red_when_the_arm_side_changes() -> None:
    """The rule must have discriminating power over the published arms.

    The check reads the arm's declared reason, so moving that reason has to
    move the verdict. This copies the fixture set, rewrites one must-fail
    arm's declared reason, and requires the rule to reject a run that
    reports the reason the arm originally published. A rule that ignored the
    arm side would still accept it.
    """
    tmp = FIXTURE_DIR.parent.parent / "_tmp_reason_binding_check"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(FIXTURE_DIR, tmp)
    try:
        victim = "nf-empty-payload-v1"
        original = "EMPTY_OUTPUT"
        replaced = "LOGIC_ERROR"

        def change(row: dict) -> None:
            if row.get("case_id") == victim:
                row["expected_reason_code"] = replaced

        path = tmp / "arms.jsonl"
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            change(row)
            lines.append(json.dumps(row, ensure_ascii=False))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        mutated = {r["case_id"]: r for r in _rows(tmp)}
        assert victim in mutated, "the rewrite did not take effect"
        arm = mutated[victim]
        assert arm["expected_reason_code"] == replaced, "the rewrite did not apply"

        # A run reporting the reason the arm published before the rewrite
        # must no longer be accepted against the rewritten arm.
        observation = _observation_for(arm, "FAIL", original)
        violation = binding_violation(observation, arm)
        assert violation is not None, (
            "rewriting the declared reason left the binding check accepting a "
            "run that carries the previously published reason, so the check "
            "is not reading the arm side"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
