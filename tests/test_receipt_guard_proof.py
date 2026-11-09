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
