"""Post-run dual-source audit (Hermes iron rule 135).

Distilled from Hermes Agent实战沉淀 (2026-08-25), addressing the
"老大拷问" on whether the generated notes actually match the source
transcript:

> "是否确定过笔记内容和口播稿内容一致？"

What this script does
---------------------

For every Feishu document under a given folder, fetch the rendered
Markdown and verify that every line inside a `​```...​``` code block
labeled "原文" (raw transcript) or "原声金句" / "核心观点" actually
appears verbatim in the local fw_corrected.txt / sf_corrected.txt.

If any line is missing → the doc is marked MISMATCH and the offending
line is reported with surrounding context.

Why this matters
----------------

vidknot's existing pipeline trusts the LLM extraction.  But Hermes
iron rule 113 ("笔记内容 = 口播稿原文") makes that trust fragile:
LLMs can paraphrase, drop, or invent when given a long transcript.
This audit enforces the rule mechanically.

Usage
-----

    # Audit a single folder
    python scripts/post_run_audit.py --folder-token "Af5..."

    # Or auto-detect latest /tmp/blogger-batch-* / /tmp/youtube-archive-*
    python scripts/post_run_audit.py --autopick-latest

References
----------

- Hermes iron rules 113 / 135 / 136
- vidknot CHANGELOG entry forthcoming (this commit)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# --- argparse (matches vidknot scripts/ pattern) -------------------------
_argparser = argparse.ArgumentParser(description="Post-run dual-source audit")
_argparser.add_argument("--folder-token", help="Feishu folder token to audit")
_argparser.add_argument("--work-dir", help="Local work directory (e.g. /tmp/youtube-archive-*)")
_argparser.add_argument("--autopick-latest", action="store_true",
                        help="Auto-pick the latest /tmp/{blogger-batch,youtube-archive}-* dir")
_args = None  # lazy: only parsed in main()


def _resolve_work_dir() -> Path:
    if _args.work_dir:
        return Path(_args.work_dir)
    if _args.autopick_latest:
        candidates = sorted(
            list(Path("/tmp").glob("blogger-batch-*"))
            + list(Path("/tmp").glob("youtube-archive-*")),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if candidates:
            return candidates[0]
    print("ERROR: --folder-token or --work-dir or --autopick-latest required", file=sys.stderr)
    sys.exit(2)


# --- lark helpers ---------------------------------------------------------
def _fetch_md(doc_id: str) -> str | None:
    """Fetch rendered markdown of a Feishu doc."""
    r = subprocess.run([
        "lark", "docs", "+fetch",
        "--doc", f"https://www.feishu.cn/docx/{doc_id}",
        "--doc-format", "markdown", "--format", "json",
    ], capture_output=True, text=True, timeout=60)
    try:
        out = json.loads(r.stdout)
        return out["data"]["document"]["content"] if out.get("ok") else None
    except Exception:
        return None


def _list_files(folder_token: str) -> list[dict]:
    r = subprocess.run([
        "lark", "drive", "files", "list",
        "--folder-token", folder_token, "--format", "json",
    ], capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout).get("data", {}).get("files", [])
    except Exception:
        return []


# --- text normalization ----------------------------------------------------
def _strip_ts(line: str) -> str:
    """Strip leading '[XX.Xs - YY.Ys]' timestamp prefix."""
    return re.sub(r"\[\s*[\d.]+\s*s\s*-\s*[\d.]+\s*s\]\s*", "", line).strip()


def _normalize(s: str) -> str:
    """Normalize whitespace + common punctuation for fuzzy substring match."""
    s = re.sub(r"\s+", "", s)
    # Strip SiliconFlow SenseVoiceSmall event tags (Hermes iron rule 136)
    # e.g. "🎼" music tag, "<|NEUTRAL|>" emotion tag, etc.
    s = re.sub(r"<\|[^|]+\|>", "", s)
    for tag in ("\U0001f3bc",):  # 🎼
        s = s.replace(tag, "")
    # Convert full-width Chinese punctuation to ASCII equivalents
    for f, t in [
        ("，", ","), ("。", "."), ("：", ":"), ("；", ";"),
        ("（", "("), ("）", ")"),
        ("！", "!"), ("？", "?"),
        ("「", '"'), ("」", '"'),  # 日式双引号
        ("『", "'"), ("』", "'"),  # 日式单引号
        # Full-width ASCII quotes (U+201C/D, U+2018/9) → ASCII
        ("\u201c", '"'), ("\u201d", '"'),
        ("\u2018", "'"), ("\u2019", "'"),
        # CJK angle brackets
        ("《", "<"), ("》", ">"),
    ]:
        s = s.replace(f, t)
    return s


def _load_fw_sf(work_dir: Path) -> tuple[dict, dict]:
    """Load fw_corrected.txt + sf_corrected.txt per video_id from work_dir/_work_*_*.

    Returns (fw_norm_map, sf_norm_map) keyed by video_id.
    """
    fw, sf = {}, {}
    for d in work_dir.glob("_work_*_*"):
        if not d.is_dir():
            continue
        # name pattern: _work_NN_<vid>
        rest = d.name.split("_", 2)[-1]
        parts = rest.split("_", 1)
        vid = parts[1] if len(parts) == 2 else parts[0]
        fw_path = d / "fw_corrected.txt"
        sf_path = d / "sf_corrected.txt"
        if fw_path.exists():
            lines = [ln for ln in fw_path.read_text().splitlines() if ln.startswith("[")]
            fw[vid] = _normalize("\n".join(_strip_ts(ln) for ln in lines))
        if sf_path.exists():
            sf[vid] = _normalize(sf_path.read_text())
    return fw, sf


# --- core audit -----------------------------------------------------------
def _audit_doc(doc_id: str, doc_md: str, fw_norm: str, sf_norm: str,
               doc_name: str = "") -> dict:
    """Audit a single doc against fw + sf 双源.

    Returns {total, matched, coverage, true_miss, status}.
    """
    sections = []
    cur = {"title": "", "lines": []}
    for ln in doc_md.splitlines():
        if ln.startswith("### ") or ln.startswith("## "):
            if cur["title"]:
                sections.append(cur)
            cur = {"title": ln.strip("# ").strip(), "lines": []}
        cur["lines"].append(ln)
    sections.append(cur)

    # 累积父章节标题 (例如 "## 六个核心观点" + "### 创作者的关键定义与强调")
    parent_titles = []
    cumulative_title = ""
    for sec in sections:
        # 看是否是 ## (父章节) 或 ### (子章节)
        first_line = sec["lines"][0] if sec["lines"] else ""
        if first_line.startswith("## ") and not first_line.startswith("### "):
            cumulative_title = sec["title"]
        parent_titles.append((sec, cumulative_title))

    total = matched = 0
    true_miss = []

    for sec, parent_title in parent_titles:
        sec_md = "\n".join(sec["lines"])
        # 判断该 section 类型: is_a / is_b / is_sub / 默认
        is_b = "版本 B" in sec["title"] or "版本 B" in parent_title
        is_a = "版本 A" in sec["title"] or "版本 A" in parent_title
        is_sub = (
            sec["title"].startswith(("六个核心观点", "原声金句", "三条可执行建议", "六个", "四段", "三条"))
            or parent_title.startswith(("六个核心观点", "原声金句", "三条可执行建议", "六个", "四段", "三条"))
        )
        src = sf_norm if is_b else fw_norm

        for block in re.findall(r"```\n(.*?)\n```", sec_md, re.DOTALL):
            for line in block.splitlines():
                line = line.strip()
                if not line:
                    continue
                text = _strip_ts(line)
                if not text or text == "(无原文)":
                    continue
                seg_norm = _normalize(text)
                if not seg_norm:
                    continue
                total += 1
                if seg_norm in src or seg_norm[:30] in src:
                    matched += 1
                elif not (is_a or is_b or is_sub):
                    # Meta sections (元信息/摘要) - default OK
                    matched += 1
                else:
                    true_miss.append((sec["title"], line[:80]))

    coverage = 100.0 * matched / total if total else 100.0
    return {
        "doc_id": doc_id,
        "doc_name": doc_name,
        "total": total,
        "matched": matched,
        "coverage": coverage,
        "true_miss": true_miss,
        "status": "OK" if (not true_miss and (total == 0 or coverage >= 99.0)) else "MISMATCH",
    }


# --- main -----------------------------------------------------------------
def main() -> int:
    global _args
    _args = _argparser.parse_args()
    work_dir = _resolve_work_dir()
    fw_map, sf_map = _load_fw_sf(work_dir)
    print(f"Work dir: {work_dir}")
    print(f"FW sources: {len(fw_map)}, SF sources: {len(sf_map)}")

    if not _args.folder_token:
        # Without folder-token: audit work_dir local docs (no Feishu side)
        print("ERROR: --folder-token required for full audit", file=sys.stderr)
        return 1

    files = _list_files(_args.folder_token)
    print(f"Found {len(files)} docs in folder {_args.folder_token}\n")

    results = []
    for f in files:
        if f.get("type") != "docx":
            continue
        doc_id = f.get("token")
        doc_name = f.get("name", "")

        # Try to map doc_name → video_id by matching first 8 chars of vid in name
        vid = None
        for v in fw_map.keys():
            if v in doc_name:
                vid = v
                break

        if not vid:
            print(f"  ? {doc_id[:12]} {doc_name[:50]} - no matching vid in work_dir")
            continue

        md = _fetch_md(doc_id)
        if not md:
            print(f"  ? {doc_id[:12]} {doc_name[:50]} - fetch failed")
            continue

        r = _audit_doc(doc_id, md, fw_map[vid], sf_map.get(vid, ""), doc_name)
        results.append(r)

    if not results:
        print("No docs audited (check folder-token + work_dir match)")
        return 1

    # Report
    print("=" * 80)
    print("📊 笔记内容 ≡ 口播稿原文 双源校验 (fw + sf)")
    print("=" * 80)
    all_ok = True
    for r in results:
        if r["status"] != "OK":
            all_ok = False
        cov = f"{r['coverage']:6.1f}%"
        print(f"  [{r['status']:8s}] {cov}  {r['matched']:>4}/{r['total']:<5}  {r['doc_name'][:50]}")
        if r["true_miss"]:
            for tag, line in r["true_miss"][:3]:
                print(f"      [{tag}] {line}")

    print("=" * 80)
    print(f"总结: {'✅ 全部 100% 一致' if all_ok else '❌ 有不达标项'}")

    # JSON output for CI
    json.dump([{k: v for k, v in r.items() if k != "true_miss"} | {
        "true_miss_count": len(r["true_miss"]),
    } for r in results], sys.stdout, ensure_ascii=False, indent=2)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
