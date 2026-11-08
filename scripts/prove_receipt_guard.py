"""Prove the receipt guard turns red on a receipt that does not back the badge.

This is a mutation proof run against the real tree: it writes a receipt
that claims more than the run could have produced, then checks that the
guard reads it and refuses it. It restores the real receipt afterwards,
and it never touches anything but that one file.

Run it with:  python3 scripts/prove_receipt_guard.py
It exits non-zero when the guard failed to notice the bad receipt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

RECEIPT_PATH = ROOT / "tests" / "suite_run_receipt.json"


def _run_guard() -> tuple[int, str]:
    """Run the badge guard and return its exit code and its output."""
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "tests/test_repo_readme_badge.py",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    if not RECEIPT_PATH.exists():
        print("no recorded receipt, so there is nothing to prove")
        return 1

    original = RECEIPT_PATH.read_text(encoding="utf-8")
    receipt = json.loads(original)

    cases = []

    failed_run = dict(receipt)
    failed_run["failed"] = 2
    failed_run["passed"] = receipt["passed"] - 2
    cases.append(("a receipt from a failing run", failed_run))

    skipped_run = dict(receipt)
    skipped_run["skipped"] = 1
    skipped_run["passed"] = receipt["passed"] - 1
    cases.append(("a receipt with a skipped test", skipped_run))

    other_tree = dict(receipt)
    other_tree["product_tree_digest"] = "0" * 64
    cases.append(("a receipt from another tree", other_tree))

    unaccounted = dict(receipt)
    unaccounted["passed"] = receipt["passed"] - 1
    cases.append(("a receipt that does not account for every test", unaccounted))

    misbound = dict(receipt)
    misbound["commit"] = _some_other_commit()
    cases.append(("a receipt whose commit names another tree", misbound))

    self_contradicting = dict(receipt)
    self_contradicting["commit_tree_digest"] = "0" * 64
    cases.append(("a receipt whose own commit-tree record is wrong", self_contradicting))

    nameless = dict(receipt)
    nameless["commit"] = ""
    cases.append(("a receipt that names no commit", nameless))

    noticed = 0
    try:
        for label, bad in cases:
            RECEIPT_PATH.write_text(json.dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            code, output = _run_guard()
            if code == 0:
                print("NOT NOTICED: %s" % label)
            else:
                noticed += 1
                print("noticed: %s" % label)
    finally:
        RECEIPT_PATH.write_text(original, encoding="utf-8")

    print("%d of %d bad receipts were refused" % (noticed, len(cases)))
    return 0 if noticed == len(cases) else 1


def _some_other_commit() -> str:
    """A commit in this repository that is not the current head."""
    import subprocess

    proc = subprocess.run(
        ["git", "-C", str(ROOT), "rev-list", "--max-count=5", "HEAD"],
        capture_output=True,
        text=True,
    )
    commits = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    for candidate in commits:
        if candidate != head:
            return candidate
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
