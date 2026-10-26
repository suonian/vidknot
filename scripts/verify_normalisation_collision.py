"""Measure the normalisation collision in the transcript comparison layer.

Claim under test:
  src/vidknot/core/corrector.py::_normalize() strips whitespace, punctuation,
  digits and emoji before the two transcripts are compared.
  => two transcripts whose RAW BYTES differ only in digits or emoji produce an
     IDENTICAL normalised form, while a byte-level digest of the same two
     transcripts differs.

This is the "same normalised form, different raw bytes" case.

Run with:  python3 scripts/verify_normalisation_collision.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vidknot.core.corrector import _normalize, _strip_timestamps  # noqa: E402

PAIRS = [
    (
        "digit_in_timestamp",
        "[  1.0s -  2.0s] 今天讲三件事\n[ 12.5s - 13.0s] 第一件是自动化",
        "[  9.9s - 10.5s] 今天讲三件事\n[ 48.2s - 49.0s] 第一件是自动化",
    ),
    (
        "emoji_only",
        "[  1.0s -  2.0s] 开工了 🎬\n[ 12.5s - 13.0s] 第一步是下载",
        "[  1.0s -  2.0s] 开工了\n[ 12.5s - 13.0s] 第一步是下载",
    ),
    (
        "punctuation_only",
        "[  1.0s -  2.0s] 开工了，动手\n[ 12.5s - 13.0s] 第一步是下载",
        "[  1.0s -  2.0s] 开工了 动手\n[ 12.5s - 13.0s] 第一步是下载",
    ),
]


def main() -> int:
    collisions = 0
    for label, a, b in PAIRS:
        norm_a = _normalize(_strip_timestamps(a))
        norm_b = _normalize(_strip_timestamps(b))
        raw_a = hashlib.sha256(a.encode("utf-8")).hexdigest()
        raw_b = hashlib.sha256(b.encode("utf-8")).hexdigest()

        same_norm = norm_a == norm_b
        same_raw = raw_a == raw_b

        print(f"[{label}]")
        print(f"  normalised identical : {same_norm}")
        print(f"  raw bytes identical  : {same_raw}")
        print(f"  normalised form       : {norm_a!r}")
        if same_norm and not same_raw:
            collisions += 1
            print("  => COLLISION: normalised form equal, raw bytes differ")
        print()

    print(f"collisions measured: {collisions} of {len(PAIRS)}")
    if collisions:
        print("RESULT: the logical-layer comparison in this repo cannot distinguish")
        print("        these pairs, while a byte-level digest can. The two layers")
        print("        answer different questions and must not share one digest name.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
