"""Must-fail arms for the byte-stream comparability rule.

A peer asked for the rule this file locks down: an absolute path inside a
captured stream must be normalised before it takes part in any comparison,
and when normalisation is not possible the column must be marked
LOCATION_DEPENDENT and kept out of PASS/FAIL.

Every arm here is written so that it can go red. The point is not that the
helper works on the happy path -- it is that a rule which quietly stops
holding still reports green.

The arms, one per failure mode:

1. A real content difference must not be explained away by normalisation.
2. A path-only difference must be classified LOCATION_DEPENDENT.
3. A location-dependent reading must not enter a PASS/FAIL ratio.
4. The occurrence count must be counted, not assumed to be one.
5. A path that is declared but absent from the stream must not be reported
   as LOCATION_DEPENDENT.
6. Two streams carrying the path a different number of times must not be
   reported as LOCATION_DEPENDENT.

Run with:  python3 -m pytest tests/test_byte_stream_comparability.py
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
    VERDICTS_ENTERING,
    StreamComparison,
    compare_streams,
)

SHORT_ROOT = "/tmp/short"
LONG_ROOT = "/tmp/a_much_longer_root_directory"


def _stream(root: str, occurrences: int = 1) -> bytes:
    """A captured stream that carries the absolute path `occurrences` times."""
    body = b"warning: something happened\n"
    return body + b"".join(
        root.encode("utf-8") + b"/lib/plugin.py:300\n" for _ in range(occurrences)
    )


def test_identical_streams_are_identical() -> None:
    same = b"warning: something happened\n"
    result = compare_streams(same, same, SHORT_ROOT, LONG_ROOT)
    assert result.verdict == IDENTICAL
    assert result.byte_delta == 0
    assert result.explained is True


def test_a_path_only_difference_is_location_dependent() -> None:
    """The measured shape: same content, path moved by a known length."""
    first = _stream(SHORT_ROOT)
    second = _stream(LONG_ROOT)
    result = compare_streams(first, second, SHORT_ROOT, LONG_ROOT)

    assert result.verdict == LOCATION_DEPENDENT, (
        "a difference that is only the moved path must be classified "
        f"LOCATION_DEPENDENT, got {result.verdict}"
    )
    assert result.path_length_delta == len(LONG_ROOT) - len(SHORT_ROOT)
    assert result.byte_delta == result.expected_byte_delta, (
        "the byte difference must equal the occurrence count times the path "
        f"length difference; measured {result.byte_delta}, expected "
        f"{result.expected_byte_delta}"
    )
    assert result.normalised_identical is True


def test_a_location_dependent_reading_must_not_enter_a_verdict() -> None:
    """Must-fail arm: the column measures where the program ran, not what it did."""
    result = compare_streams(
        _stream(SHORT_ROOT), _stream(LONG_ROOT), SHORT_ROOT, LONG_ROOT
    )
    assert result.verdict == LOCATION_DEPENDENT
    assert result.enters_verdict is False, (
        "a location-dependent reading must not be usable in a PASS/FAIL "
        "ratio; it would report the runtime layout as program behaviour"
    )


def test_a_real_content_difference_is_not_explained_away() -> None:
    """Must-fail arm: normalisation must not turn a real difference into equality.

    This is the false-green shape: a normaliser that replaces everything
    with the same token will report these two streams as equal, and the
    verdict then silently flips from DIFFERENT to "nothing to explain".
    """
    first = _stream(SHORT_ROOT) + b"content differs here\n"
    second = _stream(LONG_ROOT)
    result = compare_streams(first, second, SHORT_ROOT, LONG_ROOT)

    assert result.verdict == DIFFERENT, (
        "a real content difference must stay DIFFERENT; normalisation may "
        f"not absorb it, got {result.verdict}"
    )
    assert result.enters_verdict is True, (
        "a genuine content difference is exactly the case that may drive a "
        "verdict"
    )
    assert result.explained is False


def test_the_occurrence_count_is_counted_not_assumed() -> None:
    """The byte delta is k times the path delta, so k has to be measured.

    With the path appearing twice, a helper that assumed one occurrence
    would predict the wrong byte delta and would classify the difference
    by the wrong rule.
    """
    first = _stream(SHORT_ROOT, occurrences=2)
    second = _stream(LONG_ROOT, occurrences=2)
    result = compare_streams(first, second, SHORT_ROOT, LONG_ROOT)

    assert result.path_occurrences == 2, (
        "the number of path occurrences must be counted from the stream, got "
        f"{result.path_occurrences}"
    )
    assert result.expected_byte_delta == 2 * (len(LONG_ROOT) - len(SHORT_ROOT))
    assert result.byte_delta == result.expected_byte_delta
    assert result.verdict == LOCATION_DEPENDENT


def test_a_declared_path_absent_from_the_stream_is_not_location_dependent() -> None:
    """Must-fail arm: no path in the bytes means no path evidence.

    The two streams here normalise to the same bytes because neither
    carries the declared path. Attributing the difference to the
    environment would be an explanation with no observation behind it.
    """
    first = b"warning: one\n"
    second = b"warning: one\n"
    result = compare_streams(first, second, SHORT_ROOT, LONG_ROOT)

    assert result.path_occurrences == 0, (
        "the declared path is not in this stream, so its occurrence count "
        f"must be zero, got {result.path_occurrences}"
    )
    assert result.verdict == IDENTICAL
    assert result.enters_verdict is True


def test_a_different_occurrence_count_is_not_location_dependent() -> None:
    """Must-fail arm: the path moved and also appeared a different number of times.

    Normalisation does not make these two streams equal, and the
    occurrence counts differ, so the difference is not a moved path.
    """
    first = _stream(SHORT_ROOT, occurrences=1)
    second = _stream(LONG_ROOT, occurrences=2)
    result = compare_streams(first, second, SHORT_ROOT, LONG_ROOT)

    assert result.normalised_identical is False
    assert result.verdict == DIFFERENT, (
        "streams carrying the path a different number of times must not be "
        f"reported as LOCATION_DEPENDENT, got {result.verdict}"
    )
    assert result.enters_verdict is True


def test_a_stream_without_any_path_is_compared_as_content() -> None:
    """With no path in the stream there is nothing to normalise away."""
    first = b"warning: one\n"
    second = b"warning: two\n"
    result = compare_streams(first, first, SHORT_ROOT, LONG_ROOT)

    assert result.path_occurrences == 0
    assert result.verdict == IDENTICAL


def test_the_verdict_domain_is_closed() -> None:
    """Only three verdicts exist, and only two of them may drive a verdict."""
    verdicts = {IDENTICAL, LOCATION_DEPENDENT, DIFFERENT}
    cases = (
        (_stream(SHORT_ROOT), _stream(LONG_ROOT)),
        (b"same\n", b"same\n"),
        (b"a\n", b"b\n"),
        (_stream(SHORT_ROOT, occurrences=1), _stream(LONG_ROOT, occurrences=2)),
    )
    for first, second in cases:
        result = compare_streams(first, second, SHORT_ROOT, LONG_ROOT)
        assert result.verdict in verdicts
        assert result.enters_verdict is (result.verdict != LOCATION_DEPENDENT)


def test_a_verdict_outside_the_whitelist_does_not_enter_the_denominator() -> None:
    """Must-fail arm: a new verdict must not enter a pass rate by default.

    The filter used to be a blacklist: it excluded one known verdict and
    let every other value through. A blacklist is a filter whose default
    side is "enters", so adding a verdict later would silently widen the
    denominator -- and a state that was added precisely because it must
    not be counted would be counted anyway.

    The filter is a whitelist now, so a value that is not named in it does
    not enter. This arm checks that directly: it builds a comparison
    carrying a verdict outside the whitelist and requires that it stays
    out of the denominator. With the old blacklist this arm goes red.
    """
    result = StreamComparison(
        verdict="NOT_COMPARABLE",
        byte_delta=3,
        path_length_delta=3,
        path_occurrences=1,
        path_occurrences_second=2,
        expected_byte_delta=0,
        normalised_identical=False,
    )
    assert result.enters_verdict is False, (
        "a verdict that is not named in the whitelist must not enter a "
        "PASS/FAIL denominator; the default side of the filter has to be "
        "does-not-enter, or adding a state widens the denominator"
    )


def test_the_whitelist_names_exactly_the_two_verdicts_that_may_enter() -> None:
    """The whitelist must be the set it claims to be, not a subset of it.

    A whitelist that names too few verdicts silently drops real
    differences from the denominator; one that names too many puts a
    state back in that must stay out. Both directions are read here.
    """
    assert set(VERDICTS_ENTERING) == {IDENTICAL, DIFFERENT}, (
        "the whitelist must name exactly the identical and different "
        "verdicts; the location-dependent one measures where the program "
        "ran and must not be counted"
    )
    assert LOCATION_DEPENDENT not in VERDICTS_ENTERING
    assert len(set(VERDICTS_ENTERING)) == len(VERDICTS_ENTERING), (
        "the whitelist must not name a verdict twice"
    )


def test_both_occurrence_counts_are_recorded() -> None:
    """Must-fail arm: the second stream's occurrence count must be kept.

    The occurrence count of the first stream was recorded and the second
    one's was computed and then thrown away, so a comparison that came
    out as not-comparable could not be re-examined afterwards: the
    evidence for which side carried the path an extra time was gone. The
    count is the evidence, so it is recorded for both sides.
    """
    first = _stream(SHORT_ROOT, occurrences=1)
    second = _stream(LONG_ROOT, occurrences=2)
    result = compare_streams(first, second, SHORT_ROOT, LONG_ROOT)

    assert result.path_occurrences == 1, (
        f"the first stream's occurrence count must be recorded, got "
        f"{result.path_occurrences}"
    )
    assert result.path_occurrences_second == 2, (
        "the second stream's occurrence count must be recorded too; it was "
        "computed and discarded, so the evidence for which side carried "
        "the path an extra time was lost"
    )


def test_the_two_occurrence_counts_differ_when_the_streams_do() -> None:
    """A pair whose counts differ must show it in both recorded columns."""
    result = compare_streams(
        _stream(SHORT_ROOT, occurrences=1),
        _stream(LONG_ROOT, occurrences=2),
        SHORT_ROOT,
        LONG_ROOT,
    )
    assert result.path_occurrences != result.path_occurrences_second, (
        f"the two recorded counts must show the difference, got "
        f"{result.path_occurrences} and {result.path_occurrences_second}"
    )
