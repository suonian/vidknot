"""Gate channel contract: a control signal a round can actually read.

Two rules are encoded here, both of which came out of failures where the
signal existed but nobody read it.

1. The gate channel is dedicated. A notice is a line that is exactly a
   notice, and the channel carries gate notices and nothing else. A payload
   that merely contains the same text, or a line that carries a notice plus
   trailing content, is not a notice, and a channel with any other content
   in it is not a gate channel at all. The rule is deliberately strict: when
   the channel is not dedicated, the round is UNVERIFIED rather than CLEAN.
   A strict rule that reports UNVERIFIED is safe; a loose rule that reports
   CLEAN is the failure this whole family is about.

2. The gate column is a first-class column with named states. A round is
   PASS only when the gate column says CLEAN. A missing gate column is
   UNVERIFIED, never PASS, and a gate that blocked the work is BLOCKED,
   never PASS. Notes are not states; states get read.

Both rules are checkable, so each has a must-fail arm in the test file: a
forged payload that embeds the notice text, a notice with trailing content
on the same line, a notice delivered on a channel the round does not trust,
a missing gate column, and a blocked gate.

Run the self-test with:  python3 scripts/verify_gate_channel_contract.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

GATE_MARKER = "[EIGENFLUX-GATE]"

# The notice owns its whole line. Nothing may follow it.
_GATE_LINE = re.compile(
    r"^\[EIGENFLUX-GATE\] (?P<gate_id>[a-z0-9_]+) (?P<status>CLEAN|BLOCKED|FAILED)$"
)

# Channels the round is allowed to read gate notices from. A notice on any
# other channel is not a gate notice for this round, even when the bytes
# are identical.
TRUSTED_GATE_CHANNELS = frozenset({"stderr"})


class GateStatus(str, Enum):
    """Named states for the gate column. Notes are not states; states are read."""

    CLEAN = "CLEAN"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"
    NOT_PROBED = "NOT_PROBED"


class RoundVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class GateNotice:
    gate_id: str
    status: str
    channel: str
    line: str


def probe_gate_notice(channel_text: str, channel: str) -> GateNotice | None:
    """Find a gate notice in one dedicated channel.

    The channel must be one this round trusts, must contain exactly one
    notice, and must contain nothing else. Anything else returns None, and
    the caller turns that into UNVERIFIED rather than CLEAN.
    """
    if channel not in TRUSTED_GATE_CHANNELS:
        return None

    notices: list[GateNotice] = []
    for line in channel_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _GATE_LINE.match(stripped)
        if match is None:
            # Any other content means this channel is not a dedicated gate
            # channel, so the probe cannot claim the channel is clean.
            return None
        notices.append(
            GateNotice(
                gate_id=match.group("gate_id"),
                status=match.group("status"),
                channel=channel,
                line=stripped,
            )
        )

    if len(notices) != 1:
        # Zero notices means the channel was never probed; two means the
        # channel is ambiguous. Both are NOT_PROBED, never CLEAN.
        return None
    return notices[0]


def gate_status_from_notice(notice: GateNotice | None) -> GateStatus:
    if notice is None:
        return GateStatus.NOT_PROBED
    try:
        return GateStatus(notice.status)
    except ValueError:
        return GateStatus.UNVERIFIED


def _coerce_status(gate_status: GateStatus | str | None) -> GateStatus:
    if gate_status is None:
        return GateStatus.UNVERIFIED
    if isinstance(gate_status, GateStatus):
        return gate_status
    try:
        return GateStatus(str(gate_status))
    except ValueError:
        return GateStatus.UNVERIFIED


def assess_round(
    gate_status: GateStatus | str | None,
    stage_verdicts: list[str] | None = None,
) -> RoundVerdict:
    """Decide the round verdict, with the gate column as a first-class input.

    A missing gate column is UNVERIFIED, never PASS. This is the consumer
    side of the contract: the gate column has to be read here, or a blocked
    round and a clean round render the same way.
    """
    status = _coerce_status(gate_status)
    if status in (GateStatus.UNVERIFIED, GateStatus.NOT_PROBED):
        return RoundVerdict.UNVERIFIED
    if status is GateStatus.BLOCKED:
        return RoundVerdict.BLOCKED
    if status is GateStatus.FAILED:
        return RoundVerdict.FAIL
    stages = list(stage_verdicts or [])
    if stages and any(str(v).upper() != "PASS" for v in stages):
        return RoundVerdict.FAIL
    return RoundVerdict.PASS


def build_ledger_row(
    gate_status: GateStatus | str | None,
    stage_verdicts: list[str] | None = None,
    channel: str | None = None,
) -> dict:
    """Build the round ledger row, gate column included.

    The gate column is always present. When it is missing upstream it is
    written as UNVERIFIED rather than omitted, because an absent column and
    a clean column are the same thing to every reader that only sees counts.
    """
    status = _coerce_status(gate_status)
    verdict = assess_round(status, stage_verdicts)
    return {
        "gate_status": status.value,
        "gate_channel": channel,
        "round_verdict": verdict.value,
        "stage_verdicts": list(stage_verdicts or []),
    }


def ledger_row_is_clean(row: dict) -> bool:
    """Consumer predicate. A row is clean only when the gate column says so."""
    return (
        row.get("gate_status") == GateStatus.CLEAN.value
        and row.get("round_verdict") == RoundVerdict.PASS.value
    )
