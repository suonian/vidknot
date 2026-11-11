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

The scope of the normalisation
------------------------------
``compare_streams`` treats the path text as replaceable *wherever it
appears* in the captured bytes. That is the right rule for an opaque
stderr capture, where there is no field structure to consult and every
path-looking string is an artefact of the runtime layout.

It is the wrong rule for a structured record. A record carries business
fields that a user can see, and one of those fields may legitimately
contain the same path string. Blanket replacement then erases a real
content difference and reports two records that differ in a visible field
as equal -- the same false-green shape, reached from the opposite
direction.

So the scope of the replacement has to be declared, not assumed.
``compare_records`` takes the set of fields that may be normalised and
leaves every other field byte-for-byte alone. A peer supplied the case
that made this concrete: a record pair where the caption embeds the
source path and the caption itself changed. Under the blanket rule the
two records normalise to the same bytes and the verdict comes out
LOCATION_DEPENDENT, while the caption difference is a content difference
and the verdict should be DIFFERENT. The field-scoped rule gets that
right, and the two rules disagree, so they are not interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass

PATH_TOKEN = "<PATH>"

IDENTICAL = "IDENTICAL"
LOCATION_DEPENDENT = "LOCATION_DEPENDENT"
DIFFERENT = "DIFFERENT"

# The verdicts that may contribute to a PASS/FAIL judgement. This is a
# whitelist, not a blacklist: a new verdict must be named here before it
# can enter a pass rate. A blacklist of the excluded value would let every
# verdict added later pass the filter by default, so adding a state would
# silently widen the denominator -- the "add a state and the check is
# wrong" trap.
VERDICTS_ENTERING = (IDENTICAL, DIFFERENT)


@dataclass(frozen=True)
class StreamComparison:
    """The outcome of comparing two captured streams."""

    verdict: str
    byte_delta: int
    path_length_delta: int
    path_occurrences: int
    path_occurrences_second: int
    expected_byte_delta: int
    normalised_identical: bool

    @property
    def enters_verdict(self) -> bool:
        """Whether this comparison may contribute to a PASS/FAIL judgement.

        A location-dependent reading may not. It is a property of where the
        program ran, and folding it into a pass rate reports the runtime
        layout as if it were the program's behaviour.

        The filter is a whitelist of the verdicts that may enter, not a
        blacklist of the one that may not. A blacklist lets any verdict
        added later enter by default, so widening the verdict domain
        would silently widen the denominator. The whitelist makes the
        default "does not enter", so a new state has to be named here
        before it can be counted.
        """
        return self.verdict in VERDICTS_ENTERING

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
        path_occurrences_second=occurrences_second,
        expected_byte_delta=expected_byte_delta,
        normalised_identical=normalised_identical,
    )


@dataclass(frozen=True)
class RecordComparison:
    """The outcome of comparing two structured records field by field.

    ``differing_fields`` names the fields whose values differ, and
    ``normalised_fields`` names the fields that were allowed to be
    normalised. A difference in a field outside the declared scope is a
    content difference: it is not explained by the environment and it
    drives the verdict.
    """

    verdict: str
    differing_fields: tuple[str, ...]
    normalised_fields: tuple[str, ...]

    @property
    def enters_verdict(self) -> bool:
        """Whether this comparison may contribute to a PASS/FAIL judgement.

        A location-dependent reading may not. It is a property of where the
        program ran, and folding it into a pass rate reports the runtime
        layout as if it were the program's behaviour.

        The filter is a whitelist, for the same reason as in
        :class:`StreamComparison`: a verdict added later must be named
        before it can enter a pass rate.
        """
        return self.verdict in VERDICTS_ENTERING


def _normalise_field(value: object, path: str) -> object:
    """Replace the path with a token inside one field value.

    Only the declared field is touched. A path string that appears in
    another field is content, and content is left exactly as it is.
    """
    if not path or not isinstance(value, str):
        return value
    return value.replace(path, PATH_TOKEN)


def compare_records(
    first: dict,
    second: dict,
    normalisable_fields: tuple[str, ...],
    first_path: str = "",
    second_path: str = "",
) -> RecordComparison:
    """Compare two structured records, normalising only the declared fields.

    ``normalisable_fields`` is the declared scope of the normalisation: the
    only fields whose path text may be replaced. Every other field is
    compared byte-for-byte, so a path string embedded in a business field
    stays a content difference.

    The verdict follows the same three-state domain as
    :func:`compare_streams`:

    IDENTICAL           every field matches exactly.
    LOCATION_DEPENDENT  the fields that differ are exactly the declared
                        normalisable ones, and they differ only by the path.
    DIFFERENT           some field outside the declared scope differs, which
                        is a content difference and may drive a verdict.
    """
    first_keys = set(first)
    second_keys = set(second)
    all_keys = sorted(first_keys | second_keys)

    differing: list[str] = []
    normalised_differing: list[str] = []
    scope = set(normalisable_fields)

    for key in all_keys:
        in_first = key in first
        in_second = key in second
        if not in_first or not in_second:
            differing.append(key)
            continue

        left = first[key]
        right = second[key]
        if left == right:
            continue

        differing.append(key)
        if key in scope:
            left_value = _normalise_field(left, first_path)
            right_value = _normalise_field(right, second_path)
            if left_value == right_value:
                normalised_differing.append(key)

    if not differing:
        verdict = IDENTICAL
    elif set(differing) <= scope and set(differing) == set(normalised_differing):
        verdict = LOCATION_DEPENDENT
    else:
        verdict = DIFFERENT

    return RecordComparison(
        verdict=verdict,
        differing_fields=tuple(differing),
        normalised_fields=tuple(normalised_differing),
    )
