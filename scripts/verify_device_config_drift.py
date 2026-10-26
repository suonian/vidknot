"""Verify the config drift between VIDKNOT_DEVICE and the transcriber's device read.

Claim under test:
  VIDKNOT_DEVICE writes to  local_whisper.device
  FasterWhisperTranscriber reads  faster_whisper.device
  => the env var never reaches the transcriber; device silently stays cpu.

Run with:  python3 scripts/verify_device_config_drift.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vidknot.utils.config_manager import ConfigManager  # noqa: E402


def main() -> int:
    os.environ["VIDKNOT_DEVICE"] = "cuda"

    cfg = ConfigManager()
    resolved = cfg._config

    local_whisper_device = (resolved.get("local_whisper") or {}).get("device")
    faster_whisper_device = (resolved.get("faster_whisper") or {}).get("device")

    # This is exactly the read the transcriber performs.
    fw = cfg.get("faster_whisper") or {}
    transcriber_device = fw.get("device", "cpu")

    print(f"VIDKNOT_DEVICE           = {os.environ['VIDKNOT_DEVICE']}")
    print(f"local_whisper.device     = {local_whisper_device}")
    print(f"faster_whisper.device    = {faster_whisper_device}")
    print(f"transcriber effective    = {transcriber_device}")

    if transcriber_device == "cuda":
        print("RESULT: no drift, env var reaches the transcriber")
        return 0

    print("RESULT: DRIFT CONFIRMED, env var does not reach the transcriber")
    print(f"        env asked for {os.environ['VIDKNOT_DEVICE']}, "
          f"transcriber will run on {transcriber_device}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
