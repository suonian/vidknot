"""f2 CLI wrapper for single-video Douyin download.

The :mod:`f2.apps.douyin.handler.DouyinHandler` API has been brittle
across releases — its XBOGUS signing algorithm is known to be revoked
by Douyin on a regular basis. The ``f2 dy --mode one`` CLI entry point
has been more stable in our testing, so we wrap it here.

This module:

* Reads a Netscape-format ``cookies.txt`` file and converts it to the
  ``key=val; key2=val2`` string ``f2`` expects.
* Invokes ``f2 dy --mode one --url <iesdouyin-share-url>`` with the
  cookie.
* Returns the resolved on-disk video path, or raises
  :class:`F2DownloadError` on failure.

Layer order (kept in sync with :class:`vidknot.core.platforms.douyin`):

1. **Layer 0** — ``f2 dy --mode one`` via this helper. May fail because
   the XBOGUS algorithm is revoked.
2. **Layer 1** — :mod:`vidknot.core.douyin_parser` (iesdouyin share page
   via ``requests``).
3. **Layer 2** — ``yt-dlp`` + Cookie. The Douyin extractor is known to
   return ``"Fresh cookies needed"`` even with valid cookies; treat as
   last resort.
4. **Layer 3 (opt-in)** — Third-party API (apibyte / canxiang / alapi /
   tikhub). TikHub is a **paid** service and must only be used as the
   final fallback after the free layers are exhausted.

No credentials are stored in this module. Cookies are read on demand
from a caller-provided path.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class F2DownloadError(RuntimeError):
    """Raised when f2-based download fails for any reason."""


# The f2 CLI executable is in the f2env venv. Tests / docs should not
# hard-code this — set ``F2_BIN`` env var to override.
# Default: <project-root>/.venv-f2/bin/f2 (portable, matches f2_helper.py)
_F2_BIN = os.getenv("F2_BIN") or str(Path(__file__).resolve().parent.parent / ".venv-f2" / "bin" / "f2")


@dataclass(frozen=True)
class F2DownloadResult:
    """Outcome of a single f2-mode-one download."""

    video_path: Path
    aweme_id: str
    title: str
    author: str


def read_cookie_file(cookie_file: str | os.PathLike[str]) -> str:
    """Convert a Netscape ``cookies.txt`` file to a single cookie string.

    Lines starting with ``#`` and blank lines are ignored. The returned
    string has the form ``key1=val1; key2=val2`` — exactly what f2 expects.
    """
    p = Path(cookie_file).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Cookie file not found: {p}")

    parts: list[str] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 7:
            continue
        parts.append(f"{fields[5]}={fields[6]}")
    return "; ".join(parts)


def iesdouyin_share_url(aweme_id: str) -> str:
    """Build the iesdouyin share URL for a given ``aweme_id``."""
    if not aweme_id.isdigit():
        raise ValueError(f"aweme_id must be numeric, got {aweme_id!r}")
    return f"https://www.iesdouyin.com/share/video/{aweme_id}/"


_AWEME_RE = re.compile(r"/video/(\d+)")


def find_downloaded_mp4(
    output_root: str | os.PathLike[str],
    aweme_id: str,
    *,
    max_depth: int = 4,
) -> Path | None:
    """Locate the most recently written ``*_video.mp4`` under ``output_root``.

    f2 writes to ``<root>/douyin/one/<author>/<date>_<title>_video.mp4``
    but the exact author/date subdirectory layout may shift across f2
    versions. We fall back to a recursive search keyed on the aweme_id
    substring of the filename (f2 includes it when available).
    """
    root = Path(output_root).expanduser()
    if not root.exists():
        return None

    candidates: list[Path] = []
    for path in root.rglob("*_video.mp4"):
        rel = path.relative_to(root)
        depth = len(rel.parts) - 1
        if depth > max_depth:
            continue
        candidates.append(path)

    if not candidates:
        return None

    # Prefer files whose stem contains the aweme_id (some f2 versions
    # embed it). Fall back to the most recently modified file.
    for path in candidates:  # noqa: F402 — readable intent
        if aweme_id in path.stem:
            return path
    return max(candidates, key=lambda p: p.stat().st_mtime)


def download_one(
    aweme_id: str,
    *,
    cookie_file: str | os.PathLike[str],
    output_dir: str | os.PathLike[str] = "/tmp",
    timeout_seconds: int = 120,
    f2_bin: str | None = None,
) -> F2DownloadResult:
    """Download a single Douyin video via ``f2 dy --mode one``.

    Args:
        aweme_id: Numeric Douyin aweme id.
        cookie_file: Path to a Netscape ``cookies.txt`` file.
        output_dir: Root directory f2 will write to. f2 creates
            ``<output_dir>/douyin/one/<author>/`` automatically.
        timeout_seconds: How long to wait for the f2 subprocess.
        f2_bin: Override path to the ``f2`` executable. Defaults to the
            ``F2_BIN`` env var or ``/home/ubuntu/f2env/bin/f2``.

    Returns:
        :class:`F2DownloadResult` with the on-disk path and parsed
        metadata.

    Raises:
        F2DownloadError: if ``f2`` is not available, exits non-zero, or
            the downloaded file cannot be located.
    """
    f2 = f2_bin or _F2_BIN
    if not shutil.which(f2) and not Path(f2).exists():
        raise F2DownloadError(
            f"f2 executable not found at {f2}. Install f2 or set F2_BIN."
        )

    cookie_str = read_cookie_file(cookie_file)
    output_root = Path(output_dir).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)

    url = iesdouyin_share_url(aweme_id)
    cmd = [
        f2,
        "dy",
        "--url",
        url,
        "--mode",
        "one",
        "-p",
        str(output_root),
        "-k",
        cookie_str,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise F2DownloadError(
            f"f2 download timed out after {timeout_seconds}s for {aweme_id}"
        ) from exc

    # f2 prints "完成" on success and exits 0. We do not rely on the
    # exit code alone because the optional Bark push can fail with 405
    # without aborting the actual download.
    if proc.returncode != 0 and "完成" not in proc.stdout:
        raise F2DownloadError(
            f"f2 exited {proc.returncode} for {aweme_id}.\n"
            f"stdout: {proc.stdout[-500:]}\nstderr: {proc.stderr[-500:]}"
        )

    video_path = find_downloaded_mp4(output_root, aweme_id)
    if not video_path:
        raise F2DownloadError(
            f"f2 reported success but no *_video.mp4 was written under "
            f"{output_root}."
        )

    # Best-effort metadata extraction from the filename. f2 names files as
    # ``<created_at>_<author>_video.mp4`` or ``<created_at>_<title>_video.mp4``.
    stem = video_path.stem
    if "_video" in stem:
        author = stem.split("_video")[0].split("_")[-1]
    else:
        author = ""

    return F2DownloadResult(
        video_path=video_path,
        aweme_id=aweme_id,
        title=stem[:120],
        author=author,
    )
