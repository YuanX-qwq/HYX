#!/usr/bin/env python3
"""把 results 草稿序列化为符合 output_contract 的 result.json，并做必填/枚举校验。

用法：
  python3 scripts/serialize_result.py --input /input/case.json --draft /app/work/results_draft.json \
      --out /app/output/result.json --skill-name reference-citation-management
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

TOP = ["case_id", "task_id", "status", "results", "sources", "uncertainty",
       "changes", "artifacts", "metadata"]
STATUS = {"success", "partial", "undetermined", "refused"}
RESULT_KEYS = {
    "citations": ["claim_span", "ref_keys", "placement", "style"],
    "reference_list": ["key", "metadata", "doi", "source", "status"],
    "dedup": ["merged_keys", "basis", "kept_key"],
    "consistency_checks": ["claim", "ref_key", "match", "evidence"],
    "format_notes": ["target_style", "converted_from", "kept_fields"],
}
MATCH_ENUM = {"strong", "supported", "weak", "mismatch", "no_entry", "unverifiable", "missing", "dangling", "duplicate", "unmatched"}


def fail(msg):
    print("FAIL: " + msg, file=sys.stderr)
    raise SystemExit(1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="")
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skill-name", default="reference-citation-management")
    ap.add_argument("--version", default="1.0.0")
    a = ap.parse_args(argv)

    draft = json.loads(Path(a.draft).read_text(encoding="utf-8"))
    case = {}
    if a.input and Path(a.input).exists():
        try:
            case = json.loads(Path(a.input).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            case = {}

    res = {k: draft.get(k) for k in TOP}
    res["case_id"] = draft.get("case_id") or case.get("case_id", "")
    res["task_id"] = draft.get("task_id") or case.get("task_id", "")
    res["status"] = draft.get("status") or "partial"
    res["sources"] = draft.get("sources") or []
    res["uncertainty"] = draft.get("uncertainty") or []
    res["changes"] = draft.get("changes") or []
    res["artifacts"] = draft.get("artifacts") or []

    missing = [k for k in TOP if k not in draft and k not in res]
    if missing:
        fail("缺少顶层字段: %s" % missing)
    if res["status"] not in STATUS:
        fail("status 非法: %r（允许 %s）" % (res["status"], sorted(STATUS)))
    if not res["case_id"]:
        fail("case_id 为空；必须原样写入 case.json 的 case_id")

    results = draft.get("results") or {k: draft[k] for k in RESULT_KEYS if k in draft}
    res["results"] = results
    for c in results.get("citations") or []:
        if isinstance(c.get("ref_keys"), list):
            c["ref_keys"] = ", ".join(str(x) for x in c["ref_keys"])
    for key, fields in RESULT_KEYS.items():
        if key not in results:
            fail("results 缺少 %s" % key)
        val = results[key]
        if key == "format_notes":
            if not isinstance(val, dict):
                fail("results.format_notes 必须是对象")
            for f in fields:
                if f not in val:
                    fail("results.format_notes 缺少字段 %s" % f)
            continue
        if not isinstance(val, list):
            fail("results.%s 必须是数组" % key)
        for i, item in enumerate(val):
            for f in fields:
                if f not in item:
                    fail("results.%s[%d] 缺少字段 %s" % (key, i, f))
            if key == "consistency_checks" and item.get("match") not in MATCH_ENUM:
                fail("results.consistency_checks[%d].match 非法: %r" % (i, item.get("match")))

    for i, s in enumerate(res["sources"]):
        for f in ("source_id", "locator", "locator_type", "quote"):
            if not s.get(f):
                fail("sources[%d] 缺少 %s" % (i, f))
    for i, u in enumerate(res["uncertainty"]):
        for f in ("item", "reason", "action_required"):
            if not u.get(f):
                fail("uncertainty[%d] 缺少 %s" % (i, f))

    meta = dict(draft.get("metadata") or {})
    meta.setdefault("skill_name", a.skill_name)
    meta.setdefault("skill_version", a.version)
    meta.setdefault("generated_at", dt.datetime.now().astimezone().isoformat(timespec="seconds"))
    meta.setdefault("model", "")
    meta.setdefault("runtime", "")
    res["metadata"] = meta

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote %s status=%s citations=%d refs=%d dedup=%d checks=%d sources=%d uncertainty=%d"
          % (a.out, res["status"], len(results["citations"]), len(results["reference_list"]),
             len(results["dedup"]), len(results["consistency_checks"]),
             len(res["sources"]), len(res["uncertainty"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
