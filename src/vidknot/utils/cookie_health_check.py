"""Douyin cookie health check.

Netscape ``cookies.txt`` files are quietly invalidated by Douyin every
2–4 weeks. When this happens, ``f2`` and ``yt-dlp`` start returning
``403`` / ``Fresh cookies needed`` and the entire downstream pipeline
sits idle. The first time you notice is usually when your Monday
content report produces no data.

This module provides a small watchdog:

1. ``check_cookie_health()`` — performs a probe request with the current
   cookie and classifies it as ``healthy`` / ``warning`` / ``expired``.
2. ``write_health_flag()`` — writes a ``{date}.flag`` file under a
   configurable directory so downstream cron jobs can short-circuit
   before they waste cycles calling broken APIs.
3. ``HealthStatus`` — the result dataclass, deliberately framework-only.

A typical cron wiring looks like::

    every Monday 08:30:
        status = check_cookie_health(cookie_file)
        write_health_flag(flag_dir, status)
        if status.severity == "expired":
            notify_operator("Cookie expired — please re-export")

No credentials are logged or returned.
"""

from __future__ import annotations

import enum
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class HealthStatus(str, enum.Enum):
    """Severity bucket for a single cookie health probe."""

    HEALTHY = "healthy"
    WARNING = "warning"
    EXPIRED = "expired"


@dataclass(frozen=True)
class HealthReport:
    """Outcome of a cookie health probe."""

    status: HealthStatus
    aweme_id: str
    detail: str
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def severity(self) -> HealthStatus:
        return self.status

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "aweme_id": self.aweme_id,
            "detail": self.detail,
            "checked_at": self.checked_at,
        }


# A small, stable video known to be publicly accessible. Override via the
# ``VIDKNOT_HEALTH_PROBE_AWEME_ID`` env var if this one ever disappears.
DEFAULT_PROBE_AWEME_ID = os.getenv(
    "VIDKNOT_HEALTH_PROBE_AWEME_ID", "7636872072064470298"
)


def _read_cookie(cookie_file: str | os.PathLike[str]) -> str:
    """Convert Netscape cookie file to ``key=val; key2=val2`` string."""
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


def check_cookie_health(
    cookie_file: str | os.PathLike[str],
    *,
    probe_aweme_id: str = DEFAULT_PROBE_AWEME_ID,
    timeout_seconds: int = 30,
) -> HealthReport:
    """Probe Douyin with the current cookie and classify the response.

    The probe is intentionally cheap — it issues a HEAD request to
    ``iesdouyin.com/share/video/{aweme_id}/`` with the cookie and a
    mobile UA, then inspects the response:

    * HTTP 200 with redirect to a valid video page → ``healthy``
    * HTTP 200 but empty / no JSON body → ``warning``
    * HTTP 403 / 404 / network error → ``expired``
    """
    if not Path(cookie_file).exists():
        return HealthReport(
            status=HealthStatus.EXPIRED,
            aweme_id=probe_aweme_id,
            detail=f"cookie file not found: {cookie_file}",
        )

    try:
        cookie_str = _read_cookie(cookie_file)
    except Exception as exc:  # noqa: BLE001
        return HealthReport(
            status=HealthStatus.EXPIRED,
            aweme_id=probe_aweme_id,
            detail=f"failed to parse cookie file: {exc!r}",
        )

    url = f"https://www.iesdouyin.com/share/video/{probe_aweme_id}/"
    try:
        proc = subprocess.run(
            [
                "curl",
                "-sS",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--max-time",
                str(timeout_seconds),
                "-H",
                "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)",
                "-H",
                f"Cookie: {cookie_str}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 5,
        )
        http_code = proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return HealthReport(
            status=HealthStatus.EXPIRED,
            aweme_id=probe_aweme_id,
            detail="probe timed out",
        )
    except FileNotFoundError:
        # curl is not available — surface as warning, not error.
        return HealthReport(
            status=HealthStatus.WARNING,
            aweme_id=probe_aweme_id,
            detail="curl not available; install curl for accurate health check",
        )

    if http_code.startswith("200"):
        return HealthReport(
            status=HealthStatus.HEALTHY,
            aweme_id=probe_aweme_id,
            detail=f"HTTP {http_code}",
        )
    if http_code.startswith("403") or http_code.startswith("404"):
        return HealthReport(
            status=HealthStatus.EXPIRED,
            aweme_id=probe_aweme_id,
            detail=f"HTTP {http_code} (likely cookie revoked)",
        )
    return HealthReport(
        status=HealthStatus.WARNING,
        aweme_id=probe_aweme_id,
        detail=f"HTTP {http_code}",
    )


def write_health_flag(
    flag_dir: str | os.PathLike[str],
    report: HealthReport,
    *,
    date: str | None = None,
) -> Path:
    """Write a ``{date}.flag`` file so downstream jobs can short-circuit.

    The flag content is JSON containing the full :class:`HealthReport`
    so a debugging human can inspect it without re-running the probe.
    """
    d = Path(flag_dir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
    flag_path = d / f"{date}.flag"
    flag_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return flag_path
