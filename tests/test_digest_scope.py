"""The receipt's scope must cover the artifacts the run actually measures.

The digest scope used to be src/ and scripts/ in full, plus the suite's
own python files. The published fixture artifacts -- the criterion, the
two arm sets, the manifest -- were outside it, because they are not
python files under tests/.

That exclusion was invisible in the readings. A commit that changed only
the criterion produced a tree digest byte-identical to its parent's: in
scope, the two commits were the same tree. A receipt therefore named a
tree it had not fully measured, and any reader who resolved that commit
and recomputed the digest got a match while the criterion had moved.

It is the same shape as the twin-commit bug that was already fixed for
the receipt file itself: the key was present, the pointer was checked,
and the object the key pointed at could not be told apart from another
object in the scope. The fix there was to require the mutation target to
be distinguishable in scope. The fix here is to put the measured
artifacts inside the scope, so they are distinguishable at all.

So two things are checked here. The declaration is read from a data file
rather than restated in code, so the rule that says what is measured and
the code that measures it cannot drift apart. And the published
artifacts are inside the scope, so a criterion change moves the digest.

The tests are mutation proofs: each one has to go red when the thing it
checks is broken, because a check that only ever confirms a right state
measures nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from record_suite_run import (  # noqa: E402
    SCOPE_DECLARATION_PATH,
    _digest_over,
    _excluded,
    _glob_to_regex,
    _scope_declaration,
    _scope_paths,
    commit_tree_digest,
    product_tree_digest,
)

FIXTURE_DIR = "tests/fixtures/agent_reliability"

# The artifacts this repository publishes for cross-implementation
# comparison. Each of them is read by the suite, so each of them is
# something the run measured.
PUBLISHED_ARTIFACTS = (
    "criterion_v0_3.yaml",
    "arms.jsonl",
    "arms_ext_v0.3.jsonl",
    "manifest.sha256",
    "observation_row.v0.3.schema.json",
    "observation_row.v0.3.template.json",
)


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _git_in(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _scratch_repo_with_a_criterion_only_commit(tmp_path: Path, declaration: dict | None = None):
    """A repository whose two commits differ only in the criterion.

    The property under test is about two commits, so it needs two
    commits. This repository's own history cannot supply them: the
    commits before the scope declaration existed have no declaration,
    so their trees cannot be resolved under any rule at all, and the
    commits after it differ in many files rather than in one. So the
    pair is built here, in a scratch repository.

    The declaration the two commits carry is the one passed in, so the
    scope under which they resolve is the scope in force at those
    commits. That matters: each commit is resolved with the
    declaration it has, so narrowing the declaration afterwards would
    change nothing about how the earlier pair resolves.

    The two commits differ in exactly one byte of one file: the
    criterion. Everything else -- the declaration, the script, the
    directory layout -- is identical.
    """
    repo = tmp_path / "scratch"
    (repo / FIXTURE_DIR).mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)

    if declaration is None:
        declaration = _scope_declaration(ROOT)
    (repo / SCOPE_DECLARATION_PATH).write_text(
        json.dumps(declaration, indent=2) + "\n", encoding="utf-8"
    )
    (repo / "scripts" / "tool.py").write_text("VALUE = 1\n", encoding="utf-8")

    criterion = repo / FIXTURE_DIR / "criterion_v0_3.yaml"
    criterion.write_text("criterion_version: nf-v0.3\n", encoding="utf-8")

    _git_in(repo, "init")
    _git_in(repo, "add", "-A")
    _git_in(
        repo,
        "-c",
        "user.email=scratch@example.invalid",
        "-c",
        "user.name=scratch",
        "commit",
        "-m",
        "first",
    )
    first = _git_in(repo, "rev-parse", "HEAD")

    criterion.write_text(
        "criterion_version: nf-v0.3\n# the only change in this commit\n", encoding="utf-8"
    )
    _git_in(repo, "add", "-A")
    _git_in(
        repo,
        "-c",
        "user.email=scratch@example.invalid",
        "-c",
        "user.name=scratch",
        "commit",
        "-m",
        "second",
    )
    second = _git_in(repo, "rev-parse", "HEAD")
    return repo, first, second


def test_the_scope_is_declared_in_a_file_rather_than_restated_in_code() -> None:
    """The rule that says what is measured must be readable as data.

    A scope written only in a docstring cannot be checked by anything,
    and a scope written only in code cannot be found by a reader who
    wants to know what the digest covers. So the declaration is a file,
    and the implementation reads it.
    """
    path = ROOT / SCOPE_DECLARATION_PATH
    assert path.exists(), (
        "the scope declaration must exist at %s, so the rule that says what "
        "a run measures is readable rather than implied" % SCOPE_DECLARATION_PATH
    )
    declaration = _scope_declaration(ROOT)
    assert declaration, "the scope declaration must not be empty"
    assert declaration.get("include_roots"), "the declaration must name the roots it covers"
    assert declaration.get("scope_version"), (
        "the scope declaration must carry a version, so a scope that changed "
        "can be told apart from one that did not"
    )


def test_every_published_artifact_is_inside_the_scope() -> None:
    """The artifacts the suite reads must be things the digest covers.

    This is the check that was missing. The published artifacts were
    outside the scope, so a criterion change did not move the digest and
    the receipt could name a tree it had not measured.
    """
    scope = set(_scope_paths(ROOT))
    missing = [
        name for name in PUBLISHED_ARTIFACTS
        if "%s/%s" % (FIXTURE_DIR, name) not in scope
    ]
    assert not missing, (
        "these published artifacts are read by the suite but are outside the "
        "digest scope, so changing them does not move the digest: %s" % ", ".join(missing)
    )


def test_a_change_to_the_criterion_moves_the_digest() -> None:
    """The point of the fix: a criterion change must be visible.

    The digest is a property of the tree the run measured. If the
    criterion is not in it, then two trees that differ in the criterion
    have the same digest, and the receipt cannot tell a reader which
    criterion the run was judged against.

    The change is applied to the bytes as they are fed to the digest
    rather than to the file on disk, so this test cannot leave the
    working tree altered. The digest function is the same one the
    receipt uses, over the same scope it resolves.
    """
    scope = _scope_paths(ROOT)
    criterion = "%s/criterion_v0_3.yaml" % FIXTURE_DIR
    assert criterion in scope, "the criterion must be in scope for this check to mean anything"

    def real_bytes(rel: str) -> bytes:
        try:
            return (ROOT / rel).read_bytes()
        except OSError:
            return b""

    def edited_bytes(rel: str) -> bytes:
        if rel == criterion:
            return real_bytes(rel) + b"\n# local edit\n"
        return real_bytes(rel)

    before = _digest_over(scope, real_bytes)
    after = _digest_over(scope, edited_bytes)
    assert before != after, (
        "editing the criterion did not move the digest, so the receipt "
        "cannot distinguish a tree with one criterion from a tree with "
        "another"
    )
    assert before == product_tree_digest(ROOT), (
        "the digest computed here must equal the one the receipt uses, "
        "otherwise this check is about a different function"
    )


def test_a_commit_that_changes_only_the_criterion_is_not_a_twin(tmp_path) -> None:
    """A criterion-only commit must not be indistinguishable from its parent.

    This is the shape that broke the must-fail arm before: a commit
    whose only change was outside the scope resolved to the same digest
    as its parent, so binding a receipt to it changed nothing that the
    binding could see.

    The pair of commits is built in a scratch repository rather than
    taken from this one's history, because this history cannot supply
    it: every commit before the scope declaration existed has no
    declaration, so its tree cannot be resolved under any rule at all,
    and every commit after it differs in more than the criterion. The
    scratch pair differs in the criterion and in nothing else, which is
    the case the property is about.
    """
    repo, first, second = _scratch_repo_with_a_criterion_only_commit(tmp_path)
    assert first and second, "the scratch repository needs two commits"

    first_digest = commit_tree_digest(repo, first)
    second_digest = commit_tree_digest(repo, second)
    assert first_digest and second_digest, "both commits must resolve to a tree"
    assert first_digest != second_digest, (
        "the second commit and its parent resolve to the same digest, so a "
        "mutation that only touches the criterion is invisible"
    )


def test_a_criterion_only_commit_was_a_twin_before_the_artifacts_were_in_scope(tmp_path) -> None:
    """The same pair, under the old scope: the two commits are twins.

    This is the proof that the check above has teeth. The scratch
    repository is built with the scope the repository used before the
    fix, one in which the published artifacts were outside what a run
    measures. Under that scope the two commits resolve to one digest,
    and the property the previous test checks does not hold.

    A check that passes on the fixed scope and on the broken scope
    measures nothing; this one is what tells the two apart.
    """
    old_scope = dict(_scope_declaration(ROOT))
    old_scope["include_roots"] = ["scripts"]
    repo, first, second = _scratch_repo_with_a_criterion_only_commit(tmp_path, old_scope)

    first_digest = commit_tree_digest(repo, first)
    second_digest = commit_tree_digest(repo, second)
    assert first_digest and second_digest, "both commits must resolve to a tree"
    assert first_digest == second_digest, (
        "with the criterion outside the scope the two commits are twins, so "
        "the check above would pass for the wrong reason"
    )


def test_the_receipt_is_outside_the_scope_and_that_exclusion_is_declared() -> None:
    """The receipt cannot be in its own scope, and the exclusion is visible.

    A receipt that contained its own digest could never be written. But
    an exclusion nobody can read is a blind spot that a real file at the
    same path inherits, so the exclusion is declared in the same file as
    everything else and checked here.
    """
    scope = set(_scope_paths(ROOT))
    assert "tests/suite_run_receipt.json" not in scope, (
        "the receipt must stay out of the scope it is written into"
    )

    declaration = _scope_declaration(ROOT)
    excluded = set(declaration.get("exclude_paths") or ())
    assert "tests/suite_run_receipt.json" in excluded, (
        "the receipt's exclusion must be declared explicitly, so it is "
        "visible rather than implied"
    )


def test_the_scope_excludes_build_artefacts() -> None:
    """Machine artefacts must stay out, or the digest describes the machine.

    A file git does not track is not part of the tree a receipt names, so
    a build artefact sitting under src/ must not move the digest. This
    is the reason the scope is tracked-only in the first place.
    """
    declaration = _scope_declaration(ROOT)
    assert _excluded("src/__pycache__/thing.pyc", declaration), (
        "compiled artefacts must be excluded from the scope"
    )
    assert _excluded("tests/__pycache__/x.pyc", declaration), (
        "compiled artefacts must be excluded from the scope"
    )
    assert not _excluded("src/app.py", declaration), (
        "source files must not be excluded from the scope"
    )
    assert not _excluded("tests/test_thing.py", declaration), (
        "test modules must not be excluded from the scope"
    )


def test_the_glob_matcher_spans_path_segments() -> None:
    """A '**' pattern must match across directories, and '*' must not.

    The scope excludes build artefacts by pattern. If the matcher
    treated '*' as spanning directories, a pattern meant for one
    directory would quietly exclude a source tree as well.

    A __pycache__ directory holds machine artefacts whatever it holds,
    so the whole directory is out of scope, not only the compiled
    files inside it. The two rules in the declaration are not
    alternatives: one names the directory, the other catches compiled
    files that sit outside one.
    """
    pattern = _glob_to_regex("**/__pycache__/**")
    assert pattern.match("src/__pycache__/x.pyc")
    assert pattern.match("a/b/__pycache__/c/d.pyc")
    assert pattern.match("src/__pycache__/x.py")

    single = _glob_to_regex("tests/*.py")
    assert single.match("tests/test_a.py")
    assert not single.match("tests/sub/test_a.py")


def test_the_build_artefact_rules_leave_source_files_in_scope() -> None:
    """The exclusion rules must not reach past the artefacts.

    A rule that is too wide is as wrong as one that is too narrow: it
    puts real source outside the scope, and then a change to that
    source does not move the digest. So the rules are checked against
    the files they must keep in, not only against the ones they must
    keep out.
    """
    declaration = _scope_declaration(ROOT)
    assert not _excluded("src/app.py", declaration)
    assert not _excluded("tests/test_thing.py", declaration)
    assert not _excluded("tests/fixtures/agent_reliability/criterion_v0_3.yaml", declaration)
    assert _excluded("src/__pycache__/thing.pyc", declaration)
    assert _excluded("tests/__pycache__/x.pyc", declaration)
    assert _excluded("build/thing.pyc", declaration)


def test_the_declaration_file_is_itself_inside_the_scope() -> None:
    """The scope rule must be inside the hashed set.

    A scope that is not itself hashed can be changed without moving the
    digest, which is the invisible-scope-change shape: the rule changed,
    the readings did not, and nobody can tell afterwards whether two
    readings were taken under the same rule.
    """
    scope = set(_scope_paths(ROOT))
    assert SCOPE_DECLARATION_PATH in scope, (
        "the scope declaration must be in scope, so changing the rule "
        "changes the digest"
    )


# The files that decide which tests are collected and how they are
# selected. They are tracked files that sit outside the three roots, so
# they have to be named one by one.
SELECTOR_PATHS = (
    "pytest.ini",
    "pyproject.toml",
    ".github/workflows/ci.yml",
)


def test_the_selector_that_decides_which_tests_measure_is_inside_the_scope() -> None:
    """The rule that says which tests measure the tree must be hashed too.

    This is the same shape as the published artifacts having been outside
    the scope, one level up. The scope covered the criterion and the arm
    set, so a change to either moved the digest. But the selector -- the
    pytest settings that decide which tests are collected, and the
    pipeline command that runs them -- was outside the scope. Changing
    the selector therefore moved the collected count while the tree
    digest stayed exactly where it was: two numbers from two definitions
    sharing one table, and the tree digest could not tell a reader that
    the selection had changed under it.

    The selector is in scope now, so this check reads it back.
    """
    scope = set(_scope_paths(ROOT))
    missing = [name for name in SELECTOR_PATHS if name not in scope]
    assert not missing, (
        "these files decide which tests are collected and how they are "
        "selected, but they are outside the digest scope, so changing the "
        "selector moves the collected count without moving the digest: "
        f"{', '.join(missing)}"
    )


def test_changing_the_selector_moves_the_digest() -> None:
    """The point of the fix: a change to the selector must be visible.

    The digest is a property of the tree the run measured. If the
    selector is not in it, then two trees that differ only in the
    selector have the same digest, and the receipt cannot tell a reader
    which selection the run was taken under.
    """
    scope = _scope_paths(ROOT)
    selector = "pytest.ini"
    assert selector in scope, (
        "the selector must be in scope for this check to mean anything"
    )

    def real_bytes(rel: str) -> bytes:
        try:
            return (ROOT / rel).read_bytes()
        except OSError:
            return b""

    def edited_bytes(rel: str) -> bytes:
        if rel == selector:
            return real_bytes(rel) + b"\n# local edit\n"
        return real_bytes(rel)

    before = _digest_over(scope, real_bytes)
    after = _digest_over(scope, edited_bytes)
    assert before != after, (
        "editing the selector did not move the digest, so the receipt "
        "cannot distinguish a tree with one selection from a tree with "
        "another"
    )
    assert before == product_tree_digest(ROOT), (
        "the digest computed here must equal the one the receipt uses, "
        "otherwise this check is about a different function"
    )


def test_the_scope_version_moved_when_the_selector_was_added() -> None:
    """A scope that changed must be distinguishable from one that did not.

    The scope version is how a reader tells two readings taken under
    different rules apart. The selector was added to the scope, so the
    scope changed, so the version has to say so: a reader comparing a
    tree digest taken under the old scope with one taken under the new
    one would otherwise have no way to tell that the two numbers were
    computed over different file sets.
    """
    declaration = _scope_declaration(ROOT)
    version = declaration.get("scope_version")
    assert version, "the scope declaration must carry a version"
    assert version != "nf-scope-v0.1", (
        "the selector was added to the scope, which changed the scope, so "
        "the scope version must move; a reader could not otherwise tell "
        "that two tree digests were computed over different file sets"
    )


def test_a_scope_without_the_selector_paths_declared_is_not_accepted() -> None:
    """The declaration must name the selector files it claims to cover.

    A declaration that drops the include_paths key falls back to the
    three roots alone, which is the scope that had the hole in it. This
    check reads the declaration rather than the resolved scope, so it
    catches the key going missing before the scope is resolved.
    """
    declaration = _scope_declaration(ROOT)
    declared = list(declaration.get("include_paths") or ())
    assert declared, (
        "the declaration must name the selector files it covers; without "
        "them the scope silently falls back to the roots alone"
    )
    for name in SELECTOR_PATHS:
        assert name in declared, (
            f"the declaration must name {name}, so the selector stays "
            f"inside the scope"
        )
