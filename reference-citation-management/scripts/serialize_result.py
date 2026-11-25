#!/usr/bin/env python3
"""把 results_draft.json 组装成契约 result.json（九字段 + 本题 results 结构校验）。"""
import argparse
import datetime
import json
import sys
from pathlib import Path

STATUS = ("success", "partial", "undetermined", "refused")
TOP = ("case_id", "task_id", "status", "results", "sources", "uncertainty",
       "changes", "artifacts", "metadata")
RESULT_KEYS = ("citations", "reference_list", "dedup", "consistency_checks", "format_notes")
CIT_KEYS = ("claim_span", "ref_keys", "placement", "style")
REF_KEYS = ("key", "metadata", "doi", "source", "status")
DEDUP_KEYS = ("merged_keys", "basis", "kept_key")
CHK_KEYS = ("claim", "ref_key", "match", "evidence")


def fail(msg):
    print("FAIL: " + msg, file=sys.stderr)
    sys.exit(1)


def norm_ref_keys(v):
    if isinstance(v, list):
        return ";".join(str(x) for x in v)
    return str(v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="case.json")
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skill-name", default="reference-citation-management")
    ap.add_argument("--skill-version", default="1.0.0")
    ap.add_argument("--model", default="")
    ap.add_argument("--runtime", default="")
    a = ap.parse_args(argv)

    case = json.loads(Path(a.input).read_text(encoding="utf-8"))
    draft = json.loads(Path(a.draft).read_text(encoding="utf-8"))
    case_id = case.get("case_id") or case.get("caseId") or "UNKNOWN-CASE"
    task_id = case.get("task_id") or case.get("challenge_id") or case.get("taskId") or ""

    body = draft.get("results") if isinstance(draft.get("results"), dict) else draft
    results = {k: body.get(k) for k in RESULT_KEYS}
    missing = [k for k in RESULT_KEYS if results.get(k) in (None, "")]
    if missing:
        fail("results 缺少 %s" % missing)
    if not isinstance(results["format_notes"], dict):
        fail("format_notes 必须是对象")
    for k in ("target_style", "converted_from", "kept_fields"):
        if k not in results["format_notes"]:
            fail("format_notes 缺 %s" % k)

    for row in results["citations"]:
        for k in CIT_KEYS:
            if k not in row:
                fail("citations 条目缺 %s" % k)
        row["ref_keys"] = norm_ref_keys(row["ref_keys"])
    for row in results["reference_list"]:
        for k in REF_KEYS:
            if k not in row:
                fail("reference_list 条目缺 %s" % k)
    for row in results["dedup"]:
        for k in DEDUP_KEYS:
            if k not in row:
                fail("dedup 条目缺 %s" % k)
    for row in results["consistency_checks"]:
        for k in CHK_KEYS:
            if k not in row:
                fail("consistency_checks 条目缺 %s" % k)
        if row["match"] not in ("strong", "weak", "mismatch", "dangling", "undetermined"):
            fail("consistency_checks.match 取值非法：%s" % row["match"])

    status = draft.get("status", "partial")
    if status not in STATUS:
        fail("status 必须是 %s 之一" % (STATUS,))

    sources = draft.get("sources") or []
    for s in sources:
        for k in ("source_id", "locator", "quote"):
            if k not in s:
                fail("sources 条目缺 %s" % k)

    doc = {
        "case_id": case_id,
        "task_id": task_id,
        "status": status,
        "results": results,
        "sources": sources,
        "uncertainty": draft.get("uncertainty") or [],
        "changes": draft.get("changes") or [],
        "artifacts": draft.get("artifacts") or [],
        "metadata": {
            "skill_name": a.skill_name,
            "skill_version": a.skill_version,
            "model": a.model or draft.get("metadata", {}).get("model", ""),
            "runtime": a.runtime or draft.get("metadata", {}).get("runtime", ""),
            "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "example_only": bool(draft.get("metadata", {}).get("example_only", False)),
        },
    }
    unknown = [k for k in TOP if k not in doc]
    if unknown:
        fail("顶层缺 %s" % unknown)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote %s status=%s citations=%d refs=%d dedup=%d checks=%d sources=%d" % (
        a.out, status, len(results["citations"]), len(results["reference_list"]),
        len(results["dedup"]), len(results["consistency_checks"]), len(sources)))


if __name__ == "__main__":
    sys.exit(main())
