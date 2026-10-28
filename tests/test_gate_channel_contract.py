"""Tests for the gate channel contract (scripts/gate_contract.py).

Every rule in the module has a matching must-fail arm here, so a rule that
silently stops failing shows up as a red test rather than a green round.

Must-fail arms, one per rule:

1. A payload that embeds the notice text is NOT a notice.
2. A notice with trailing content on the same line is NOT a notice.
3. A notice delivered on a channel the round does not trust is NOT read.
4. A round ledger with no gate column is UNVERIFIED, never PASS.
5. A blocked gate is BLOCKED, never PASS.
6. A clean gate with a failing stage is FAIL.
7. A channel carrying a notice plus other content is NOT a clean channel.

Run with:  python3 -m pytest tests/test_gate_channel_contract.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from gate_contract import (  # noqa: E402
    GATE_MARKER,
    TRUSTED_GATE_CHANNELS,
    GateStatus,
    RoundVerdict,
    _coerce_status,
    assess_round,
    build_ledger_row,
    gate_status_from_notice,
    ledger_row_is_clean,
    probe_gate_notice,
)


# --- rule 1: the notice owns its line and its channel ---

def test_notice_on_its_own_line_is_found():
    notice = probe_gate_notice("[EIGENFLUX-GATE] skill_sync CLEAN\n", "stderr")
    assert notice is not None
    assert notice.gate_id == "skill_sync"
    assert notice.status == "CLEAN"
    assert notice.channel == "stderr"


def test_embedded_notice_in_a_payload_is_not_found():
    """Must-fail arm: the rule text embedded in another payload is not a notice."""
    payload = (
        "The contract says the exact line is\n"
        "[EIGENFLUX-GATE] skill_sync CLEAN\n"
        "and nothing after it.\n"
    )
    notice = probe_gate_notice(payload, "stderr")
    assert notice is None
    assert gate_status_from_notice(notice) is GateStatus.NOT_PROBED


def test_notice_with_trailing_content_is_not_found():
    """Must-fail arm: trailing content means the line is not the notice."""
    channel = "[EIGENFLUX-GATE] skill_sync CLEAN but only because we forced it\n"
    assert probe_gate_notice(channel, "stderr") is None


def test_notice_with_leading_content_is_not_found():
    assert probe_gate_notice("prefix [EIGENFLUX-GATE] skill_sync CLEAN\n", "stderr") is None


def test_two_notices_on_one_channel_are_ambiguous():
    channel = (
        "[EIGENFLUX-GATE] skill_sync CLEAN\n"
        "[EIGENFLUX-GATE] version_floor BLOCKED\n"
    )
    assert probe_gate_notice(channel, "stderr") is None


def test_untrusted_channel_does_not_find_the_notice():
    """Must-fail arm: the channel is part of the contract, not a hint."""
    channel = "[EIGENFLUX-GATE] skill_sync CLEAN\n"
    assert probe_gate_notice(channel, "stdout") is None
    assert probe_gate_notice(channel, "stderr") is not None


def test_dedicated_channel_with_extra_content_is_not_clean():
    """Must-fail arm: a channel carrying a notice plus other content is not clean."""
    channel = (
        "[EIGENFLUX-GATE] skill_sync CLEAN\n"
        "some other diagnostic line\n"
    )
    assert probe_gate_notice(channel, "stderr") is None


def test_trusted_channels_are_declared():
    assert "stderr" in TRUSTED_GATE_CHANNELS
    assert "stdout" not in TRUSTED_GATE_CHANNELS


def test_notice_marker_constant_matches_the_parser():
    assert GATE_MARKER == "[EIGENFLUX-GATE]"


# --- rule 2: the gate column is a first-class column ---

def test_missing_gate_column_is_unverified_not_pass():
    """Must-fail arm: a ledger without the gate column must never read PASS."""
    row = build_ledger_row(None, ["PASS", "PASS"])
    assert row["gate_status"] == GateStatus.UNVERIFIED.value
    assert row["round_verdict"] == RoundVerdict.UNVERIFIED.value
    assert ledger_row_is_clean(row) is False


def test_blocked_gate_is_blocked_not_pass():
    """Must-fail arm: a blocked gate and a clean gate must render differently."""
    row = build_ledger_row(GateStatus.BLOCKED, ["PASS"])
    assert row["round_verdict"] == RoundVerdict.BLOCKED.value
    assert ledger_row_is_clean(row) is False


def test_failed_gate_is_fail():
    row = build_ledger_row(GateStatus.FAILED, ["PASS"])
    assert row["round_verdict"] == RoundVerdict.FAIL.value
    assert ledger_row_is_clean(row) is False


def test_not_probed_gate_is_unverified():
    row = build_ledger_row(GateStatus.NOT_PROBED, ["PASS"])
    assert row["round_verdict"] == RoundVerdict.UNVERIFIED.value
    assert ledger_row_is_clean(row) is False


def test_clean_gate_with_failing_stage_is_fail():
    """Must-fail arm: a clean gate cannot mask a failing stage."""
    row = build_ledger_row(GateStatus.CLEAN, ["PASS", "FAIL"])
    assert row["round_verdict"] == RoundVerdict.FAIL.value
    assert ledger_row_is_clean(row) is False


def test_clean_gate_with_all_passing_stages_is_pass():
    row = build_ledger_row(GateStatus.CLEAN, ["PASS", "PASS"])
    assert row["round_verdict"] == RoundVerdict.PASS.value
    assert ledger_row_is_clean(row) is True


def test_gate_column_is_always_present_in_the_row():
    for status in (None, GateStatus.CLEAN, GateStatus.BLOCKED, GateStatus.FAILED):
        row = build_ledger_row(status, ["PASS"])
        assert "gate_status" in row
        assert row["gate_status"]


# --- rule 3: a superseded gate is its own verdict, not a current conclusion ---

def test_superseded_gate_is_superseded_not_pass():
    """Must-fail arm: an old criterion revision's result must not read PASS."""
    row = build_ledger_row(GateStatus.SUPERSEDED, ["PASS", "PASS"])
    assert row["gate_status"] == GateStatus.SUPERSEDED.value
    assert row["round_verdict"] == RoundVerdict.SUPERSEDED.value
    assert ledger_row_is_clean(row) is False


def test_superseded_gate_is_superseded_not_fail():
    """Must-fail arm: superseded is not a failure either. The remedy differs."""
    row = build_ledger_row(GateStatus.SUPERSEDED, ["PASS"])
    assert row["round_verdict"] != RoundVerdict.FAIL.value
    assert row["round_verdict"] != RoundVerdict.UNVERIFIED.value


def test_a_gate_result_from_an_older_revision_is_superseded():
    """The ledger carries the criterion revision, so staleness is readable."""
    row = build_ledger_row(
        GateStatus.CLEAN,
        ["PASS"],
        channel="stderr",
        criterion_revision="criterion:nf-v0.2",
        current_revision="criterion:nf-v0.3",
    )
    assert row["gate_status"] == GateStatus.SUPERSEDED.value
    assert row["round_verdict"] == RoundVerdict.SUPERSEDED.value
    assert ledger_row_is_clean(row) is False


def test_a_gate_result_from_the_current_revision_is_kept():
    """Must-fail arm: matching revisions must not be demoted to superseded."""
    row = build_ledger_row(
        GateStatus.CLEAN,
        ["PASS", "PASS"],
        channel="stderr",
        criterion_revision="criterion:nf-v0.3",
        current_revision="criterion:nf-v0.3",
    )
    assert row["gate_status"] == GateStatus.CLEAN.value
    assert row["round_verdict"] == RoundVerdict.PASS.value


def test_a_gate_result_without_a_revision_is_not_read_as_current():
    """Must-fail arm: no revision means staleness is unknown, not absent."""
    row = build_ledger_row(
        GateStatus.CLEAN,
        ["PASS", "PASS"],
        channel="stderr",
        criterion_revision=None,
        current_revision="criterion:nf-v0.3",
    )
    assert row["gate_status"] != GateStatus.CLEAN.value
    assert ledger_row_is_clean(row) is False


def test_superseded_is_a_distinct_member_of_the_closed_set():
    """The closed set grows by one value, and the set stays closed."""
    values = {status.value for status in GateStatus}
    assert "SUPERSEDED" in values
    assert len(values) == 6
    # An unknown string must still not become a member of the set.
    assert _coerce_status("SOMETHING_ELSE") is GateStatus.UNVERIFIED


def test_channel_is_recorded_next_to_the_fact():
    """The record carries which channel a notice arrived on."""
    row = build_ledger_row(GateStatus.CLEAN, ["PASS"], channel="stderr")
    assert row["gate_channel"] == "stderr"


def test_assess_round_rejects_an_unknown_status():
    """Must-fail arm: an unrecognised status is not silently treated as clean."""
    verdict = assess_round("SOMETHING_ELSE", ["PASS"])
    assert verdict is RoundVerdict.UNVERIFIED


# --- the consumer path, end to end ---

def test_a_blocked_notice_on_the_trusted_channel_blocks_the_round():
    channel = "[EIGENFLUX-GATE] version_floor BLOCKED\n"
    notice = probe_gate_notice(channel, "stderr")
    status = gate_status_from_notice(notice)
    row = build_ledger_row(status, ["PASS"], channel="stderr")
    assert row["round_verdict"] == RoundVerdict.BLOCKED.value


def test_a_notice_on_an_untrusted_channel_leaves_the_round_unverified():
    """Must-fail arm: the same bytes on the wrong channel must not clear the gate."""
    channel = "[EIGENFLUX-GATE] version_floor CLEAN\n"
    notice = probe_gate_notice(channel, "stdout")
    status = gate_status_from_notice(notice)
    row = build_ledger_row(status, ["PASS"], channel="stdout")
    assert row["round_verdict"] == RoundVerdict.UNVERIFIED.value
    assert ledger_row_is_clean(row) is False


def test_a_clean_notice_on_the_trusted_channel_clears_the_round():
    channel = "[EIGENFLUX-GATE] skill_sync CLEAN\n"
    notice = probe_gate_notice(channel, "stderr")
    status = gate_status_from_notice(notice)
    row = build_ledger_row(status, ["PASS", "PASS"], channel="stderr")
    assert row["round_verdict"] == RoundVerdict.PASS.value
    assert ledger_row_is_clean(row) is True
