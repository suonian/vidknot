---
name: Bug report
about: Report a defect or unexpected behavior
title: '[Bug]: '
labels: bug
---

## Describe the bug

A clear and concise description of what the bug is.

## Reproduction

```bash
# Minimal command that reproduces the issue
python -m vidknot "<url>" --destination none --no-cache
```

## Expected behavior

What you expected to happen.

## Actual behavior

What actually happened. Include the full traceback if any.

```text
(paste here)
```

## Environment

- VidkNot version (e.g. `v0.6.3`): <!-- run `python -m vidknot --version` -->
- Python version (`python --version`):
- OS (macOS / Linux / Windows + version):
- FFmpeg version (`ffmpeg -version | head -1`):
- Platform of the failing URL (Douyin / Bilibili / ...):

## URL and metadata

- Video URL:
- Cookie file configured? (yes / no / path)
- Was the video public or login-only?
- Did `python -m vidknot --check-env` pass?

## Relevant logs

Attach the relevant lines from `logs/vidknot-*.log` (without secrets, cookies, or tokens).

## Additional context

Anything else that might help reproduce or diagnose the issue.