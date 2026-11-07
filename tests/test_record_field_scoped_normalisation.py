"""Must-fail arms for the field-scoped normalisation rule.

A peer supplied a synthetic fixture that the byte-stream rule could not
judge correctly:

    A = {"source_path": "C:/run-a/input.mov", "caption": "from C:/run-a/input.mov"}
    B = {"source_path": "D:/run-b/input.mov", "caption": "from D:/run-b/input.mov"}

Only ``source_path`` is declared normalisable. ``caption`` is a
user-visible business field, and it changed, so the pair must be
DIFFERENT. Holding the caption identical makes the pair
LOCATION_DEPENDENT instead.

The byte-stream rule reached the wrong answer on the first case. It
replaces the path text wherever it appears, so the caption difference was
erased along with the path difference and two records that differ in a
visible field came out equal. These arms lock down the field-scoped rule
that gets it right, and they pin the two rules apart: a helper that
quietly falls back to the blanket rule has to fail here.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from byte_stream_comparability import (  # noqa: E402
    DIFFERENT,
    IDENTICAL,
    LOCATION_DEPENDENT,
    RecordComparison,
    compare_records,
    compare_streams,
)

FIRST_PATH = "C:/run-a/input.mov"
SECOND_PATH = "D:/run-b/input.mov"
SOURCE_PATH = "source_path"
CAPTION = "caption"

RECORD_A = {
    SOURCE_PATH: FIRST_PATH,
    CAPTION: "from C:/run-a/input.mov",
}
RECORD_B = {
    SOURCE_PATH: SECOND_PATH,
    CAPTION: "from D:/run-b/input.mov",
}
RECORD_B_SAME_CAPTION = {
    SOURCE_PATH: SECOND_PATH,
    CAPTION: "from C:/run-a/input.mov",
}


def _compare(first: dict, second: dict) -> RecordComparison:
    return compare_records(
        first,
        second,
        normalisable_fields=(SOURCE_PATH,),
        first_path=FIRST_PATH,
        second_path=SECOND_PATH,
    )


def test_a_changed_business_field_is_different() -> None:
    """Must-fail arm: the caption changed, so this is a content difference.

    This is the peer's fixture. The declared scope is ``source_path``
    alone, so the caption difference survives normalisation and the
    verdict has to be DIFFERENT.
    """
    result = _compare(RECORD_A, RECORD_B)

    assert result.verdict == DIFFERENT, (
        "a business field that changed must not be explained away by the "
        f"environment; got {result.verdict}"
    )
    assert result.enters_verdict is True, (
        "a content difference is exactly the case that may drive a verdict"
    )
    assert CAPTION in result.differing_fields, (
        "the changed field must be named, so the difference is attributable"
    )


def test_the_same_business_field_with_only_the_path_moved_is_location_dependent() -> None:
    """Must-fail arm: with the caption held identical, only the path moved."""
    result = _compare(RECORD_A, RECORD_B_SAME_CAPTION)

    assert result.verdict == LOCATION_DEPENDENT, (
        "a difference confined to the declared normalisable field must be "
        f"classified LOCATION_DEPENDENT, got {result.verdict}"
    )
    assert result.enters_verdict is False, (
        "a location-dependent reading must not be usable in a PASS/FAIL "
        "ratio; it would report the runtime layout as program behaviour"
    )


def test_a_path_inside_a_business_field_is_never_normalised() -> None:
    """Must-fail arm: the path text in the caption stays content.

    Normalising the caption would erase the very difference under test,
    so the caption is compared byte-for-byte. The declared field does
    normalise, which is the point of declaring it.
    """
    result = _compare(RECORD_A, RECORD_B)

    assert CAPTION not in result.normalised_fields, (
        "the caption is outside the declared scope, so it must never be "
        f"reported as normalised; got {result.normalised_fields}"
    )
    assert SOURCE_PATH in result.normalised_fields, (
        "the declared field differs only by the path, so it must be "
        f"reported as normalised; got {result.normalised_fields}"
    )
    assert result.differing_fields == (CAPTION, SOURCE_PATH), (
        "both the source path and the caption differ, and both must be "
        f"named; got {result.differing_fields}"
    )


def test_identical_records_are_identical() -> None:
    """No difference at all is not a location-dependent reading."""
    result = _compare(RECORD_A, dict(RECORD_A))

    assert result.verdict == IDENTICAL
    assert result.differing_fields == ()
    assert result.enters_verdict is True


def test_a_field_missing_from_one_record_is_different() -> None:
    """Must-fail arm: a missing field is a content difference.

    A field present on one side only cannot be explained by the path
    moving, and it must not be folded into a location-dependent reading.
    """
    first = {SOURCE_PATH: FIRST_PATH, CAPTION: "same caption"}
    second = {SOURCE_PATH: SECOND_PATH}

    result = compare_records(
        first,
        second,
        normalisable_fields=(SOURCE_PATH,),
        first_path=FIRST_PATH,
        second_path=SECOND_PATH,
    )

    assert result.verdict == DIFFERENT, (
        "a record missing a field must be DIFFERENT, got " f"{result.verdict}"
    )
    assert result.enters_verdict is True


def test_the_blanket_rule_and_the_scoped_rule_disagree_on_the_peer_fixture() -> None:
    """The two rules are not interchangeable, and the scoped one is right.

    This arm pins the difference itself. The byte-stream rule replaces the
    path wherever it appears and so reports the peer's fixture as
    LOCATION_DEPENDENT, erasing the caption difference. The field-scoped
    rule reports DIFFERENT. If a helper ever silently falls back to the
    blanket rule, the disagreement disappears and this arm goes red.
    """
    blanket = compare_streams(
        b'{"source_path":"C:/run-a/input.mov","caption":"from C:/run-a/input.mov"}',
        b'{"source_path":"D:/run-b/input.mov","caption":"from D:/run-b/input.mov"}',
        FIRST_PATH,
        SECOND_PATH,
    )
    scoped = _compare(RECORD_A, RECORD_B)

    assert blanket.verdict == LOCATION_DEPENDENT, (
        "the blanket rule is expected to normalise the caption too; if it "
        "no longer does, this arm no longer proves the two rules differ"
    )
    assert scoped.verdict == DIFFERENT, (
        "the scoped rule must classify the peer's fixture as DIFFERENT, got "
        f"{scoped.verdict}"
    )
    assert blanket.verdict != scoped.verdict, (
        "the two rules must disagree on this fixture, otherwise the scoped "
        "rule is not actually in force"
    )


def test_the_record_verdict_domain_is_closed() -> None:
    """Only three verdicts exist, and only two of them may drive a verdict."""
    verdicts = {IDENTICAL, LOCATION_DEPENDENT, DIFFERENT}
    cases = (
        (RECORD_A, RECORD_B),
        (RECORD_A, RECORD_B_SAME_CAPTION),
        (RECORD_A, dict(RECORD_A)),
    )
    for first, second in cases:
        result = _compare(first, second)
        assert result.verdict in verdicts
        assert result.enters_verdict is (result.verdict != LOCATION_DEPENDENT)
