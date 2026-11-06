"""Decide whether a byte-count difference between two runs is a property of
the program under test, or of the environment it happened to run in.

Why this exists
---------------
A peer asked for exactly this rule: an absolute path inside stderr must be
normalised before it takes part in any comparison, and when normalisation is
not possible the column must be marked LOCATION_DEPENDENT and kept out of
PASS/FAIL.

The rule is not hypothetical here. Measured on this tree, the same commit and
the same assertions under two interpreter paths differ in stderr by exactly
the difference in path length: 663 vs 682 bytes for a 19-character path
difference, with one occurrence of the path in each stream. So the byte
delta is not noise and not a stability measurement -- it is
``k * (path length delta)``, where k is the number of times the path occurs
in the stream. k is countable before the comparison, which makes the delta
predictable rather than merely observed.

Three verdicts, one function
----------------------------
IDENTICAL           same bytes, nothing to explain.
LOCATION_DEPENDENT  the bytes differ only by a path that moved. The column
                    measures where the program ran, not what it did, so it
                    must not enter a PASS/FAIL ratio.
DIFFERENT           the bytes differ in content. This one may drive a verdict.

Where the arithmetic guard actually bites
-----------------------------------------
When both streams contain the declared path the same number of times and
normalise to the same bytes, the byte delta necessarily equals
``k * (path length delta)``: the path text is the only thing that differs,
and it is replaced token for token. The arithmetic check is therefore not an
extra proof in that case -- it is a second, independent read on the same
evidence, and it earns its keep by catching the cases where the declared
path is not the path that actually appears:

  - the declared path is absent from a stream (occurrence count 0). The
    streams may still normalise to the same bytes if the other stream also
    lacks it, but there is then no path evidence at all, and calling that
    LOCATION_DEPENDENT would attribute a difference to the environment
    without having observed the environment in the bytes.
  - the two streams carry the path a different number of times. The
    normalised forms differ, and the difference is not a moved path.

Both fall back to DIFFERENT. The false-green shape this module exists to
prevent is a normaliser that turns everything into the same token and
reports "equal" for two streams whose content differs.
"""

from __future__ import annotations

from dataclasses import dataclass

PATH_TOKEN = "<PATH>"

IDENTICAL = "IDENTICAL"
LOCATION_DEPENDENT = "LOCATION_DEPENDENT"
DIFFERENT = "DIFFERENT"


@dataclass(frozen=True)
class StreamComparison:
    """The outcome of comparing two captured streams."""

    verdict: str
    byte_delta: int
    path_length_delta: int
    path_occurrences: int
    expected_byte_delta: int
    normalised_identical: bool

    @property
    def enters_verdict(self) -> bool:
        """Whether this comparison may contribute to a PASS/FAIL judgement.

        A location-dependent reading may not. It is a property of where the
        program ran, and folding it into a pass rate reports the runtime
        layout as if it were the program's behaviour.
        """
        return self.verdict != LOCATION_DEPENDENT

    @property
    def explained(self) -> bool:
        """Whether the byte difference is fully accounted for.

        True when the streams are byte-identical, or when the difference is
        exactly the path occurrences times the path length difference. A
        difference that survives normalisation but does not match that
        arithmetic is unexplained, and unexplained is not the same as
        location-dependent.
        """
        if self.verdict == IDENTICAL:
            return True
        if self.verdict == LOCATION_DEPENDENT:
            return self.byte_delta == self.expected_byte_delta
        return False


def _encode(path: str) -> bytes:
    return path.encode("utf-8")


def _normalise(data: bytes, path: str) -> bytes:
    """Replace every occurrence of the path with a fixed token."""
    if not path:
        return data
    return data.replace(_encode(path), PATH_TOKEN.encode("utf-8"))


def compare_streams(
    first: bytes,
    second: bytes,
    first_path: str,
    second_path: str,
) -> StreamComparison:
    """Compare two captured streams and classify the difference.

    ``first_path`` and ``second_path`` are the absolute paths the two runs
    were launched from. They are used to remove the environment from the
    comparison; they are never used to hide a content difference.
    """
    first_bytes = _encode(first_path)
    second_bytes = _encode(second_path)

    occurrences_first = first.count(first_bytes) if first_bytes else 0
    occurrences_second = second.count(second_bytes) if second_bytes else 0

    path_length_delta = len(second_bytes) - len(first_bytes)
    byte_delta = len(second) - len(first)

    normalised_first = _normalise(first, first_path)
    normalised_second = _normalise(second, second_path)
    normalised_identical = normalised_first == normalised_second

    same_occurrence_count = occurrences_first == occurrences_second
    expected_byte_delta = (
        occurrences_first * path_length_delta if same_occurrence_count else 0
    )

    if first == second:
        verdict = IDENTICAL
    elif (
        normalised_identical
        and same_occurrence_count
        and occurrences_first > 0
        and byte_delta == expected_byte_delta
    ):
        verdict = LOCATION_DEPENDENT
    else:
        verdict = DIFFERENT

    return StreamComparison(
        verdict=verdict,
        byte_delta=byte_delta,
        path_length_delta=path_length_delta,
        path_occurrences=occurrences_first,
        expected_byte_delta=expected_byte_delta,
        normalised_identical=normalised_identical,
    )
