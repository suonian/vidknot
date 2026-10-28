"""The authoritative gate column has exactly one writer, derived from the code.

One peer asked this question this cycle and it is the cell we had been
calling paper: is the authoritative field written in exactly one place?

The point is not to keep a list of writers. A list someone maintains is not
a check: add a writer without editing the list and the assertion stays
green, which is the same shape as an absent gate column being read as
clean. The set has to come from the write sites themselves.

So the enumeration is machine-derived (scripts/write_site_enumeration.py),
and the assertion below checks its cardinality against the real tree.

The falsifiable form, which is the only form worth having: inject a second
writer into a scratch copy of the tree and require that the count changes.
Two mutation proofs, each in its own test, so one cannot be masked by the
other passing.

Run with:  python3 -m pytest tests/test_write_site_enumeration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import write_site_enumeration as wse  # noqa: E402
from write_site_enumeration import (  # noqa: E402
    write_site_count,
    write_sites,
)


def _scratch_tree(tmp_path: Path, extra: str | None = None) -> Path:
    """A scratch copy of the scanned tree, optionally with an extra writer.

    The copy carries the real gate contract module, so the scratch tree has
    the same single writer the repo tree has. An extra module adds a second
    one when the caller wants one.
    """
    scratch = tmp_path / "scripts"
    scratch.mkdir(exist_ok=True)
    for name in ("gate_contract.py", "write_site_enumeration.py"):
        source = ROOT / "scripts" / name
        if source.exists():
            (scratch / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    if extra is not None:
        (scratch / "second_writer.py").write_text(extra, encoding="utf-8")
    return scratch


def test_the_gate_column_has_exactly_one_write_site():
    """The claim itself: one writer, derived from the tree, not from a list."""
    sites = write_sites("gate_status")
    assert len(sites) == 1, (
        "the authoritative gate column must be written in exactly one place, "
        f"found {len(sites)}: {sites}"
    )


def test_the_write_site_is_inside_the_gate_contract_module():
    """The single writer is the row builder, not something incidental."""
    sites = write_sites("gate_status")
    assert sites, "expected at least one write site"
    assert all(site.startswith("scripts/gate_contract.py:") for site in sites), sites


def test_a_second_writer_in_the_tree_makes_the_count_two(tmp_path):
    """Must-fail arm: a second writer must change the enumerated set.

    The scratch tree adds a module that writes the gate column, which is
    exactly the shape a projection that gets written back takes. The count
    must go from one to two.
    """
    scratch = _scratch_tree(
        tmp_path,
        extra=(
            "def project(row):\n"
            "    row['gate_status'] = row.get('gate_status')\n"
        ),
    )

    original_root = wse.ROOT
    try:
        wse.ROOT = tmp_path
        count_with_injector = wse.write_site_count("gate_status")
        (scratch / "second_writer.py").unlink()
        count_without_injector = wse.write_site_count("gate_status")
    finally:
        wse.ROOT = original_root

    assert count_without_injector == 1
    assert count_with_injector == 2, (
        "a second writer must enlarge the enumerated set; "
        f"with injector {count_with_injector}, without {count_without_injector}"
    )


def test_a_writer_that_only_reads_the_field_is_not_counted(tmp_path):
    """Must-fail arm: reads are not writes.

    A projection that is read back and never written must not enlarge the
    set. If reads counted, the count would grow with every consumer and the
    assertion would lose its meaning.
    """
    scratch = _scratch_tree(
        tmp_path,
        extra=(
            "def read(row):\n"
            "    return row.get('gate_status')\n"
            "\n"
            "def read2(row):\n"
            "    return row['gate_status']\n"
        ),
    )

    original_root = wse.ROOT
    try:
        wse.ROOT = tmp_path
        count = wse.write_site_count("gate_status")
    finally:
        wse.ROOT = original_root

    assert count == 1, (
        "reading the field must not count as writing it; "
        f"expected 1, found {count}"
    )


def test_the_enumeration_is_not_a_constant():
    """Must-fail arm: the assertion must read the tree, not a literal.

    A test that hard-codes the expected count would pass forever while the
    tree changed underneath it. Asking for a field nobody writes must
    report zero, not the count of some other field.
    """
    assert write_site_count("a_field_nobody_writes_anywhere_xyz") == 0
