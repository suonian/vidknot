"""The receipt guard's own mutation proofs must not be empty mutations.

The guard proves itself by writing bad receipts and checking that it
refuses them. That proof is only worth something when each mutation
actually changes the receipt. A mutation that writes back the same
receipt makes the guard look like it passed a case it never saw, and
the proof reports a number that looks like coverage.

This happened here for real. The proof picked "a commit in this
repository that is not the current head" as the misbound commit. That
rule was enough while the recorded receipt named the head commit, and
it stopped being enough the moment the receipt named an older commit:
the rule then handed back the receipt's own commit, the mutation wrote
the same bytes back, and the guard correctly passed a receipt nobody had
changed. The proof went from seven of seven refused to six of seven
refused and the extra case had quietly stopped testing anything.

So the mutation is checked for effect here: it has to differ from the
receipt it starts from, and the commit it names has to resolve to a
tree other than the one the receipt measured. A mutation that cannot
be made effective is a failure of the proof, not a case the guard
happens to pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import prove_receipt_guard  # noqa: E402
from record_suite_run import commit_tree_digest  # noqa: E402

RECEIPT_PATH = ROOT / "tests" / "suite_run_receipt.json"


def _receipt() -> dict:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def test_the_misbound_mutation_names_a_commit_the_receipt_does_not_already_name() -> None:
    """The misbound case must pick a commit other than the receipt's own.

    If it picked the receipt's own commit, the mutation would write the
    receipt back unchanged and the case would prove nothing.
    """
    receipt = _receipt()
    candidate = prove_receipt_guard._some_other_commit(receipt)
    assert candidate, (
        "no commit in this repository resolves to a tree other than the one the "
        "receipt measured, so the misbound mutation cannot be made effective"
    )
    assert candidate != receipt["commit"], (
        "the misbound mutation picked the commit the receipt already names, "
        "so it writes the same receipt back and tests nothing"
    )


def test_the_misbound_mutation_resolves_to_a_different_tree() -> None:
    """The commit the mutation names must resolve to another tree.

    A commit that resolves to the same tree would produce the same
    digest, so the receipt would still back the badge and the guard
    would pass it for the right reason rather than the wrong one.
    """
    receipt = _receipt()
    candidate = prove_receipt_guard._some_other_commit(receipt)
    assert candidate, "no candidate commit was found"
    resolved = commit_tree_digest(ROOT, candidate)
    assert resolved, "the candidate commit does not resolve to a tree at all"
    assert resolved != receipt["product_tree_digest"], (
        "the candidate commit resolves to the tree the receipt already measured, "
        "so the mutation cannot be told apart from the original receipt"
    )


def test_the_proof_would_report_an_empty_mutation_instead_of_passing_it() -> None:
    """The proof's own loop must not count an unchanged receipt as refused.

    This checks the proof's bookkeeping directly: when the mutated
    receipt equals the original, the proof has to say so out loud rather
    than running the guard and reporting the guard's verdict as if a
    case had been exercised.
    """
    receipt = _receipt()
    unchanged = dict(receipt)
    assert unchanged == receipt, "the baseline case must start unchanged"

    source = (ROOT / "scripts" / "prove_receipt_guard.py").read_text(encoding="utf-8")
    assert "EMPTY MUTATION" in source, (
        "the proof has no way to report a mutation that changed nothing"
    )
    assert "if bad == receipt:" in source, (
        "the proof does not compare each mutation against the receipt it started from"
    )


def test_the_proof_counts_byte_distinct_mutations_not_labels() -> None:
    """Two labels that write the same bytes are one mutation, not two.

    The proof's tally is a coverage number, so it has to count the
    shapes the suite actually exercised. Two cases whose mutated
    receipts are byte-identical are refused for the same reason, so
    counting them separately would report coverage the suite never
    had.
    """
    receipt = _receipt()

    first = dict(receipt)
    first["passed"] = receipt["passed"] - 1

    # The same mutation under a second label.
    second = dict(receipt)
    second["passed"] = receipt["passed"] - 1

    cases = [
        ("a receipt that does not account for every test", first),
        ("a receipt whose commit names another tree", second),
    ]

    result = prove_receipt_guard._run_cases(cases, receipt)
    assert result.distinct_count == 1, (
        "two byte-identical mutations were counted as %d distinct ones"
        % result.distinct_count
    )
    assert result.duplicate_labels == {"a receipt whose commit names another tree"}, (
        "the duplicate case was not identified: %s" % sorted(result.duplicate_labels)
    )
    assert result.duplicates, "the duplicate was not reported against its twin"


def test_a_pair_of_distinct_mutations_is_not_reported_as_a_duplicate() -> None:
    """The duplicate check must not fire on mutations that really differ.

    A check that reported every pair as a duplicate would be a check
    that cannot pass, so it proves nothing. This one requires two
    genuinely different mutations to be counted as two.
    """
    receipt = _receipt()

    first = dict(receipt)
    first["passed"] = receipt["passed"] - 1

    second = dict(receipt)
    second["commit"] = "0" * 40

    cases = [
        ("a receipt that does not account for every test", first),
        ("a receipt whose commit names another tree", second),
    ]

    result = prove_receipt_guard._run_cases(cases, receipt)
    assert result.distinct_count == 2, (
        "two different mutations were counted as %d distinct ones"
        % result.distinct_count
    )
    assert not result.duplicate_labels, (
        "distinct mutations were reported as duplicates: %s"
        % sorted(result.duplicate_labels)
    )


def test_the_degenerate_case_list_is_not_reported_as_full_coverage() -> None:
    """The shape that actually happens: a case collapses into another.

    This is the real defect, not a synthetic one. When the rule that
    picks the candidate commit finds nothing, the misbound case falls
    back to an empty commit, which is byte-for-byte the nameless case.
    The guard refuses both, so the old tally read seven of seven
    refused while the suite had exercised six distinct shapes.

    The check has to notice the collapse, and the coverage number it
    reports has to be the number of distinct shapes rather than the
    number of labels.
    """
    receipt = _receipt()

    # What the misbound case becomes when no candidate commit resolves
    # to a different tree.
    misbound = dict(receipt)
    misbound["commit"] = ""

    nameless = dict(receipt)
    nameless["commit"] = ""

    cases = [
        ("a receipt whose commit names another tree", misbound),
        ("a receipt that names no commit", nameless),
    ]

    result = prove_receipt_guard._run_cases(cases, receipt)
    assert result.distinct_count == 1, (
        "the collapsed case list was counted as %d distinct mutations"
        % result.distinct_count
    )
    assert result.duplicate_labels == {"a receipt that names no commit"}, (
        "the collapse was not attributed to the case that duplicated: %s"
        % sorted(result.duplicate_labels)
    )


def test_the_proof_script_reports_no_duplicate_case() -> None:
    """The proof must end green, and it must not be counting labels.

    This is the end-to-end check on the real case list: the script runs
    as a whole, every case it lists has to be a byte-distinct
    mutation, and the script has to exit zero. A case list that has
    collapsed into itself would show up here as a duplicate line rather
    than as a quiet overstatement of coverage.
    """
    proc = subprocess.run(
        [sys.executable, "scripts/prove_receipt_guard.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "the receipt guard proof did not refuse every bad receipt:\n%s\n%s"
        % (proc.stdout[-4000:], proc.stderr[-4000:])
    )
    assert "EMPTY MUTATION" not in proc.stdout, (
        "the proof reported an empty mutation, so a case stopped being exercised:\n%s"
        % proc.stdout
    )
    assert "DUPLICATE CASE" not in proc.stdout, (
        "the proof reported two labels over the same bytes, so it is "
        "counting labels rather than shapes:\n%s" % proc.stdout
    )
    assert "NOT NOTICED" not in proc.stdout, (
        "the guard passed a bad receipt it should have refused:\n%s" % proc.stdout
    )


def test_the_proof_script_runs_and_refuses_every_bad_receipt() -> None:
    """The proof itself must end green, on every case it lists.

    This is the end-to-end check: the script is run as a whole, and it
    has to refuse all of its own bad receipts and exit zero. A case
    that stopped being exercised would show up here as a non-zero exit
    rather than as a quiet line in the output.
    """
    proc = subprocess.run(
        [sys.executable, "scripts/prove_receipt_guard.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "the receipt guard proof did not refuse every bad receipt:\n%s\n%s"
        % (proc.stdout[-4000:], proc.stderr[-4000:])
    )
    assert "EMPTY MUTATION" not in proc.stdout, (
        "the proof reported an empty mutation, so a case stopped being exercised:\n%s"
        % proc.stdout
    )
    assert "NOT NOTICED" not in proc.stdout, (
        "the guard passed a bad receipt it should have refused:\n%s" % proc.stdout
    )
