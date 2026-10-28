"""Count-shaped conclusions must be re-derivable, not published as prose.

A peer asked where the "exactly three assertions turn red" number was
recorded, and the honest answer was: nowhere. It lived in a commit message,
a README paragraph and a broadcast, and nowhere in a form a test could
check. That is the same failure shape this repo keeps finding in other
implementations: the fact exists, nobody reads it, so it drifts.

So the count is now derived here. This module injects a second writer into
a scratch copy of the scanned tree, runs the write-site module against it,
and counts how many of its assertions fail. The recorded number in
tests/suite_baseline.json is asserted against what actually happened, so a
future change that moves the count fails this test instead of silently
invalidating a published conclusion.

The injection only ever touches a scratch copy. The real tree is never
modified, so running this test cannot itself alter the write-site set.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "suite_baseline.json"

WRITE_SITE_MODULE = "tests/test_write_site_enumeration.py"

INJECTED_WRITER = "def project(row):\n    row['gate_status'] = row.get('gate_status')\n"


def _baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _run_write_site_module_with_injection(tmp_path: Path) -> tuple[int, int, str]:
    """Run the write-site module against a scratch tree with a second writer.

    Returns (failed, passed, output). The scratch copy carries the real
    gate contract module, so the scratch tree has the same single writer
    the repo tree has; the injected module adds a second one.
    """
    scratch = tmp_path / "scripts"
    scratch.mkdir(parents=True, exist_ok=True)
    for name in ("gate_contract.py", "write_site_enumeration.py"):
        source = ROOT / "scripts" / name
        if source.exists():
            (scratch / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    (scratch / "second_writer.py").write_text(INJECTED_WRITER, encoding="utf-8")

    # Copy the test module next to the scratch tree so it resolves the
    # scratch scripts directory, and point its ROOT at the scratch tree.
    test_dir = tmp_path / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    shutil_copy(ROOT / WRITE_SITE_MODULE, test_dir / Path(WRITE_SITE_MODULE).name)

    env = {"PYTHONPATH": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"tests/{Path(WRITE_SITE_MODULE).name}"],
        cwd=tmp_path,
        env={**dict(_base_env()), **env},
        capture_output=True,
        text=True,
    )
    return _parse_counts(proc.stdout + proc.stderr)


def shutil_copy(src: Path, dst: Path) -> None:
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _base_env() -> dict:
    import os

    return dict(os.environ)


def _parse_counts(output: str) -> tuple[int, int, str]:
    """Read the failed and passed counts out of the pytest summary line."""
    import re

    match = re.search(r"(\d+) failed", output)
    failed = int(match.group(1)) if match else 0
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    return failed, passed, output


def test_the_recorded_red_count_is_still_true(tmp_path: Path) -> None:
    """The number in the baseline file must match what actually happens.

    If the write-site module changes shape, or the injection stops
    changing the count, this fails rather than leaving a stale number in a
    file that looks authoritative.
    """
    baseline = _baseline()
    failed, passed, output = _run_write_site_module_with_injection(tmp_path)

    assert failed > 0, (
        "the injected second writer must turn at least one assertion red; "
        f"got {failed} failed, {passed} passed\n{output}"
    )
    assert failed == baseline["expected_red_count"], (
        "the recorded red count no longer matches the measured count: "
        f"recorded {baseline['expected_red_count']}, measured {failed}. "
        "Re-measure and update tests/suite_baseline.json together with the "
        "commit identifier, do not recompute and reuse the old number.\n"
        f"{output}"
    )


def test_the_baseline_records_a_commit_and_a_suite_total() -> None:
    """A count-shaped conclusion must carry the commit and suite total."""
    baseline = _baseline()
    assert baseline["measured_at_commit"], "the baseline must name a commit"
    assert len(baseline["measured_at_commit"]) == 40, (
        "the baseline must name a full commit identifier, not a short one"
    )
    assert isinstance(baseline["suite_total_at_measured_commit"], int)
    assert baseline["suite_total_at_measured_commit"] > 0


def test_the_superseded_claim_is_recorded_rather_than_deleted() -> None:
    """A retracted number stays on the record with its reason.

    Deleting the wrong number leaves no way to tell a reader who saw the
    earlier figure that it was wrong, and leaves the same shape of gap
    that produced it.
    """
    baseline = _baseline()
    superseded = baseline["superseded_claim"]
    assert superseded["expected_red_count"] != baseline["expected_red_count"], (
        "the superseded claim must record the number it retracts"
    )
    assert superseded["why_superseded"].strip(), "the retraction needs a reason"
    assert superseded["claimed_in"], "the retraction must say where the wrong number was published"
