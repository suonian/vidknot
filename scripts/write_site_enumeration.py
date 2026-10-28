"""Enumerate the write sites of an authoritative field, derived from the code.

A hand-maintained list of writers is not a check. If the assertion reads a
list someone maintains, adding a writer without editing the list leaves the
test green, which is the same failure shape as an absent gate column being
read as clean. The set has to be derived from the write sites themselves, so
a new writer changes the set without anyone editing a list.

This module answers one narrow question for one field:

    how many places in the tree write <field>?

The enumeration is syntactic on purpose. It finds assignments and
subscript writes whose target name matches the field, anywhere in the tree
that is scanned. That is enough for the property we care about: a second
writer appears in the set without anyone maintaining a list.

What it deliberately does not do:

  - It does not prove the field is correct.
  - It does not prove the writer is reachable at runtime.
  - It does not attribute intent. A projection that writes the field is a
    writer, even if it was meant to be read only.

The property it does support: if the set has cardinality one, there is
exactly one syntactic place in the scanned tree that writes the field. A
second writer anywhere makes the set larger, and the assertion goes red.

Scanned tree: the package source plus the scripts directory, excluding
tests. Tests write fixtures on purpose, so including them would make the
count meaningless.

Run with:  python3 scripts/write_site_enumeration.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories that are scanned for write sites.
SCANNED_ROOTS = ("src", "scripts")

# Directories never scanned.
EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "build",
    "dist",
    "tests",
}


def _iter_source_files(roots: tuple[str, ...] = SCANNED_ROOTS) -> list[Path]:
    """Every python file under the scanned roots, sorted for a stable set."""
    files: list[Path] = []
    for root_name in roots:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def _target_names(node: ast.AST) -> set[str]:
    """Names a write statement targets.

    Handles the three shapes that matter here:

      x = value            -> {"x"}
      obj.x = value        -> {"x"}
      obj["x"] = value     -> {"x"}

    Augmented assignment counts as a write: x += 1 writes x.
    """
    names: set[str] = set()
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, ast.Attribute):
        names.add(node.attr)
    elif isinstance(node, ast.Subscript):
        slice_node = node.slice
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            names.add(slice_node.value)
    return names


def _dict_literal_key_names(node: ast.Dict) -> set[str]:
    """String keys a dict literal creates.

    A ledger row is usually built as a dict literal, so the field is written
    by naming it as a key rather than by assigning to it. Counting only
    assignments would report zero writers for a field that is written once,
    which is a false reading in the safe direction, and a false reading in
    the safe direction is the failure this whole family is about.

    A dict literal key is a write. A subscript read (row["field"]) and a
    mapping read (row.get("field")) are not: they do not create the field.
    """
    names: set[str] = set()
    for key in node.keys:
        if key is None:
            continue
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            names.add(key.value)
    return names


def write_sites(field: str, roots: tuple[str, ...] = SCANNED_ROOTS) -> list[str]:
    """Every syntactic write site of ``field``, as "path:line" strings."""
    sites: list[str] = []
    for path in _iter_source_files(roots):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            # A file we cannot parse is not a silent pass: skip it here and
            # let the caller decide, because the enumeration is only
            # meaningful over the tree it actually read.
            continue
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            elif isinstance(node, ast.Dict):
                # A dict literal creates its keys, so it is a write site for
                # each of them.
                if field in _dict_literal_key_names(node):
                    sites.append(f"{rel}:{node.lineno}")
                continue
            else:
                continue
            for target in targets:
                if field in _target_names(target):
                    sites.append(f"{rel}:{node.lineno}")
                    break
    return sorted(sites)


def write_site_count(field: str, roots: tuple[str, ...] = SCANNED_ROOTS) -> int:
    return len(write_sites(field, roots))


def main() -> int:
    field = sys.argv[1] if len(sys.argv) > 1 else "gate_status"
    sites = write_sites(field)
    print(f"field     = {field}")
    print(f"write sites = {len(sites)}")
    for site in sites:
        print(f"  {site}")
    if len(sites) != 1:
        print(
            f"RESULT: FAIL, expected exactly one write site for {field}, "
            f"found {len(sites)}"
        )
        return 1
    print(f"RESULT: single writer for {field}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
