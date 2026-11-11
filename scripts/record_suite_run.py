"""Record one executed suite run as a machine-readable receipt.

The README badge states a number of tests, and until now the only thing
that verified that number was a collection-only run: a count of the tests
that exist, not a count of the tests that passed. Those two counts come
apart the moment something fails, so a badge whose label says "passed"
while its guard proves only "collected" states more than the evidence
behind it.

This script produces the missing evidence. It runs the suite, reads the
counters out of the run's own summary line, and prints them as one JSON
object: collected, passed, failed, skipped, plus the commit and a digest
of the product tree the run was taken on.

The parser lives here rather than inside a test because a parser is where
this kind of receipt usually goes wrong. A summary line that says nothing
about failures reads exactly like a summary line from a run where nothing
failed, unless the reader can be shown to notice the difference. The
assertions in tests/test_suite_run_receipt.py run a scratch suite in which
one test does fail and one test does skip, so a counter that cannot move
is caught by the check that depends on it.

Run it with:  python3 scripts/record_suite_run.py
It prints one JSON object and writes nothing.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The scope rule is a data file, so the rule and the code that applies it
# are one thing rather than two that can drift apart.
SCOPE_DECLARATION_PATH = "tests/digest_scope.json"

# The published criterion, whose version the receipt names.
CRITERION_PATH = "tests/fixtures/agent_reliability/criterion_v0_3.yaml"

COLLECTED_RE = re.compile(r"(\d+) tests collected")
PASSED_RE = re.compile(r"(\d+) passed")
FAILED_RE = re.compile(r"(\d+) failed")
SKIPPED_RE = re.compile(r"(\d+) skipped")
ERROR_RE = re.compile(r"(\d+) errors?")
DESELECTED_RE = re.compile(r"(\d+) deselected")

# The one test that reads the receipt cannot be part of the run the
# receipt describes: its result is not knowable before the receipt
# exists, which is the same shape as a test that judges its own output.
# It is deselected rather than skipped, so the receipt still accounts
# for every collected item.
RECEIPT_TEST = "tests/test_repo_readme_badge.py::test_the_badge_word_passed_is_backed_by_a_run_of_this_tree"


def parse_collected(output: str) -> int | None:
    """The number of test items a collection-only run reported."""
    match = COLLECTED_RE.search(output)
    return int(match.group(1)) if match else None


def _summary_line(output: str) -> str:
    """The last line of the output that carries the run's counters.

    The counters are only trustworthy on pytest's own summary line. A
    failure message earlier in the output can carry the same words, so
    the last matching line is the one that belongs to the run.
    """
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if "passed" in stripped or "no tests ran" in stripped or "deselected" in stripped:
            return stripped
    return ""


def parse_summary(output: str) -> dict[str, int]:
    """The counters out of a pytest run's summary line.

    A counter the summary line does not mention is zero, but only because
    the reader knows how to read it: the scratch-run assertions in
    tests/test_suite_run_receipt.py feed this parser a run where a test
    failed and a test skipped, so a parser that always answered zero would
    be caught there.

    Only the run's own summary line is read. A failure message can
    contain the same words ("2 failed tests", "1 skipped tests"), and a
    reader that took the first match would report a count that never
    happened.
    """
    line = _summary_line(output)
    if not line or "no tests ran" in line:
        return {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "deselected": 0}

    counters = {
        "passed": PASSED_RE.search(line),
        "failed": FAILED_RE.search(line),
        "skipped": SKIPPED_RE.search(line),
        "errors": ERROR_RE.search(line),
        "deselected": DESELECTED_RE.search(line),
    }
    return {name: int(match.group(1)) if match else 0 for name, match in counters.items()}


def _scope_declaration(root: Path) -> dict:
    """The scope rule, read from its own file.

    The rule that says what a run measures lives in a data file, so the
    code that measures it cannot drift away from the rule that describes
    it. A scope written only in a docstring is a declaration nobody can
    check; a scope written only in code is a declaration a reader cannot
    find.
    """
    path = root / SCOPE_DECLARATION_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _glob_to_regex(pattern: str) -> re.Pattern:
    """A path glob, where '**' spans any number of path segments."""
    out = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern[index : index + 3] == "**/":
            out.append("(?:[^/]+/)*")
            index += 3
            continue
        if pattern[index : index + 2] == "**":
            out.append(".*")
            index += 2
            continue
        if char == "*":
            out.append("[^/]*")
            index += 1
            continue
        if char == "?":
            out.append("[^/]")
            index += 1
            continue
        out.append(re.escape(char))
        index += 1
    out.append("$")
    return re.compile("".join(out))


def _excluded(rel: str, declaration: dict) -> bool:
    """Whether the declaration puts a path outside the scope."""
    if rel in set(declaration.get("exclude_paths") or ()):
        return True
    for pattern in declaration.get("exclude_path_patterns") or ():
        if _glob_to_regex(pattern).match(rel):
            return True
    return False


def _scope_paths(root: Path) -> list[str]:
    """The tracked files a run measures, in a stable order.

    Tracked only, and only what git knows about. A file that git does
    not track is not part of the tree a receipt names, so a build
    artefact that happens to sit under src/ must not move the digest:
    otherwise the digest describes the machine rather than the tree,
    and no receipt could ever be reproduced by someone else. The same
    reason excludes ignored files: they are by definition local.

    The scope is whatever tests/digest_scope.json declares, read from
    there rather than restated here. It used to be src/ and scripts/ in
    full, plus the suite's own python files, which left the published
    fixture artifacts outside it: a change to the criterion or to the
    arm set did not move the digest, so a commit that changed only the
    criterion was a twin of its parent in scope, and the receipt named
    a tree it had not fully measured. A run measures the published
    artifacts, because the assertions in the suite read them, so they
    are in scope now.

    The receipt itself is out of scope, because a receipt that contained
    its own digest could never be written. That exclusion is declared
    in the same file as everything else, so it is visible rather than
    implied.
    """
    declaration = _scope_declaration(root)
    roots = list(declaration.get("include_roots") or ())
    files = list(declaration.get("include_paths") or ())
    if not roots and not files:
        return []
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", *roots, *files],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    paths = []
    for raw in proc.stdout.split("\0"):
        if not raw:
            continue
        rel = raw.replace("\\", "/")
        if _excluded(rel, declaration):
            continue
        paths.append(rel)
    return sorted(paths)


def scope_version(root: Path) -> str | None:
    """The version the scope declaration states, or None when it states none."""
    value = _scope_declaration(root).get("scope_version")
    return value if isinstance(value, str) and value else None


def criterion_version(root: Path) -> str | None:
    """The version the criterion file states, or None when it states none.

    The criterion is a published artifact, so its version belongs next
    to the receipt that measured it: a reader who holds the receipt can
    then tell which criterion the run was judged against, instead of
    inferring it from a tree whose contents they would have to resolve
    themselves.
    """
    path = root / CRITERION_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("criterion_version:"):
            return line.split(":", 1)[1].strip() or None
    return None


def _digest_over(paths: list[str], data_for) -> str:
    """A digest over named paths, hashing path and bytes for each."""
    digest = hashlib.sha256()
    for rel in paths:
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data_for(rel))
        digest.update(b"\0")
    return digest.hexdigest()


def product_tree_digest(root: Path) -> str:
    """A digest over the tree the run measured, so a receipt names it.

    Only tracked files count, so the digest is a property of the tree
    rather than of the machine that happens to hold it. A build
    artefact under src/ no longer moves it.
    """
    def read(rel: str) -> bytes:
        path = root / rel
        try:
            return path.read_bytes()
        except OSError:
            return b""

    return _digest_over(_scope_paths(root), read)


def _commit_scope_entries(root: Path, commit: str) -> list[tuple[str, str]]:
    """The scope as that commit has it: path and blob id for each file.

    The scope is resolved with the declaration as that commit has it, so
    the commit and the working tree are measured by the same rule. If the
    declaration itself changed in that commit, the old rule would still
    be applied to the new tree, and the two digests would be computed
    over different file sets -- which is the same shape as comparing two
    readings that came from different definitions.
    """
    declaration = _commit_scope_declaration(root, commit)
    roots = list(declaration.get("include_roots") or ())
    files = list(declaration.get("include_paths") or ())
    if not roots and not files:
        return []
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "-z", commit, "--", *roots, *files],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    entries = []
    for record in proc.stdout.split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        parts = meta.split()
        if len(parts) < 3:
            continue
        rel = path.replace("\\", "/")
        if _excluded(rel, declaration):
            continue
        entries.append((rel, parts[2]))
    return sorted(entries)


def _commit_scope_declaration(root: Path, commit: str) -> dict:
    """The scope declaration as that commit has it."""
    proc = subprocess.run(
        ["git", "-C", str(root), "cat-file", "blob", "%s:%s" % (commit, SCOPE_DECLARATION_PATH)],
        capture_output=True,
    )
    if proc.returncode != 0:
        return {}
    try:
        data = json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def commit_tree_digest(root: Path, commit: str) -> str | None:
    """The digest of the scope as that commit has it, or None if it cannot be resolved.

    This is the other half of the receipt's binding. A receipt names a
    commit and a digest; the digest says which bytes were measured. When
    the two are read together they have to agree, and this function is
    what turns "agree" into something checkable: it re-derives the
    digest from the commit alone, with no working tree involved, so
    anyone holding that commit can reproduce it.
    """
    entries = _commit_scope_entries(root, commit)
    if not entries:
        return None
    shas = [sha for _, sha in entries]
    proc = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input=("\n".join(shas) + "\n").encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    blobs: dict[str, bytes] = {}
    out = proc.stdout
    pos = 0
    for sha in shas:
        newline = out.find(b"\n", pos)
        if newline == -1:
            return None
        parts = out[pos:newline].decode("utf-8", "replace").split()
        if len(parts) < 3:
            return None
        size = int(parts[2])
        start = newline + 1
        blobs[sha] = out[start : start + size]
        pos = start + size + 1
    by_path = dict(entries)

    def data(rel: str) -> bytes:
        return blobs.get(by_path.get(rel, ""), b"")

    return _digest_over([rel for rel, _ in entries], data)


def commit_binding_violations(receipt: dict, resolved_digest: str | None) -> list[str]:
    """Every way the receipt's commit can fail to name the tree it measured.

    A receipt carries two facts: a commit and a digest. Checked on their
    own they are two well-formed strings. Checked against each other
    they are a claim about which tree was measured, and that claim is
    the one thing a reader cannot make up, because the commit can be
    resolved to its own bytes by anyone.

    So the check is independent of both columns: the commit is resolved
    to a digest on its own, and the digest the receipt recorded has to
    be that one. A receipt whose commit and digest disagree is invalid
    rather than failed: the receipt does not describe anything, so
    there is no run to blame.
    """
    violations: list[str] = []
    if not receipt.get("commit"):
        return ["the receipt names no commit"]
    if resolved_digest is None:
        return ["the receipt names a commit that cannot be resolved to a tree"]
    if receipt.get("product_tree_digest") != resolved_digest:
        violations.append(
            "the receipt names a commit whose tree is not the tree the receipt measured"
        )
    if "commit_tree_digest" not in receipt:
        violations.append("the receipt does not record the tree of the commit it names")
    elif receipt["commit_tree_digest"] != resolved_digest:
        violations.append(
            "the receipt's own record of its commit's tree does not match that commit"
        )
    return violations


_tree_digest = product_tree_digest


def _git_commit(root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    commit = proc.stdout.strip()
    return commit if proc.returncode == 0 and commit else None


def collect_count(root: Path = ROOT) -> int | None:
    """How many test items the suite collects, without running any of them."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    return parse_collected(proc.stdout + proc.stderr)


def run_suite(root: Path = ROOT) -> tuple[int, str]:
    """Run the suite and return its exit code and its combined output.

    The one test that reads the receipt is deselected: its verdict is
    not knowable before the receipt exists, and a test that judges its
    own run is the same shape as a detector with no negative control. It
    is deselected rather than skipped, so the run still accounts for
    every collected item.
    """
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
            "--deselect",
            RECEIPT_TEST,
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def receipt(root: Path = ROOT) -> dict:
    """One receipt: what the suite collected, and what actually happened."""
    returncode, output = run_suite(root)
    counters = parse_summary(output)
    commit = _git_commit(root)
    measured = product_tree_digest(root)
    committed = commit_tree_digest(root, commit) if commit else None
    return {
        "collected": collect_count(root),
        "passed": counters["passed"],
        "failed": counters["failed"],
        "skipped": counters["skipped"],
        "errors": counters["errors"],
        "deselected": counters["deselected"],
        "deselected_tests": [RECEIPT_TEST] if counters["deselected"] else [],
        "deselected_reason": (
            "this test reads the receipt, so its verdict is not knowable before the "
            "receipt exists; a test that judges its own run is a detector with no "
            "negative control"
        ),
        "returncode": returncode,
        "commit": commit,
        "product_tree_digest": measured,
        "commit_tree_digest": committed,
        "scope_version": scope_version(root),
        "criterion_version": criterion_version(root),
        "workspace_clean": bool(committed) and committed == measured,
    }


def write_receipt(root: Path = ROOT) -> dict:
    """Run the suite and record the receipt next to the suite's own files.

    The receipt is written after the run, so it can only ever describe a
    run that actually happened. A run that failed still gets written:
    the point of the receipt is to carry what happened, and a failed run
    is exactly what the badge must not be allowed to claim.

    A receipt is refused when the working tree is not the commit it
    names. The two facts it carries have to describe one tree: the
    commit says which tree, and the digest says which bytes were
    measured. Recording them while the tree carries uncommitted changes
    puts two different trees in one receipt, and then the commit is a
    claim nobody can check. So the recording is refused instead of
    written, which is a smaller lie than a receipt that points at
    something other than the tree it measured.
    """
    data = receipt(root)
    if not data.get("workspace_clean"):
        raise SystemExit(
            "refusing to record a receipt: the working tree is not the commit it names "
            "(commit %s, tree %s, measured %s). Commit the changes first, then record."
            % (data.get("commit"), data.get("commit_tree_digest"), data.get("product_tree_digest"))
        )
    path = root / "tests" / "suite_run_receipt.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def main() -> int:
    if "--write" in sys.argv[1:]:
        data = write_receipt()
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0 if data["returncode"] == 0 and data["failed"] == 0 else 1
    data = receipt()
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0 if data["returncode"] == 0 and data["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
