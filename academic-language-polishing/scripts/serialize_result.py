#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把润色草稿组装成官方契约形态的 result.json，并做必填校验。

用法：
  python3 scripts/serialize_result.py \
      --case /input/case.json \
      --draft /app/work/results_draft.json \
      --out /app/output/result.json \
      --skill-name academic-language-polishing

草稿只写主结果即可：
  {"results": {"revised_text": "...", "revisions": [...], "glossary": [...],
               "register_notes": [...], "unresolved": [...]},
   "sources": [...], "uncertainty": [...], "changes": [...], "artifacts": [...]}
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

STATUS = {"success", "partial", "undetermined", "refused"}
TOP = ("case_id", "task_id", "status", "results", "sources", "uncertainty", "changes", "artifacts", "metadata")
RESULT_KEYS = ("revised_text", "revisions", "glossary", "register_notes", "unresolved")
REVISION_KEYS = ("span", "original", "revised", "type", "reason", "preserves_meaning")
REVISION_TYPES = {"grammar", "syntax", "collocation", "punctuation", "terminology", "register",
                  "clarity", "redundancy", "cohesion", "bilingual", "other"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def case_ids(case):
    cid = str(case.get("case_id") or case.get("id") or "")
    tid = str(case.get("task_id") or case.get("challenge_id") or "")
    if not cid:
        for k in ("case", "request", "task"):
            v = case.get(k)
            if isinstance(v, dict) and v.get("case_id"):
                cid, tid = str(v["case_id"]), tid or str(v.get("task_id") or "")
                break
    return cid, tid


def validate(r):
    errs = []
    for k in TOP:
        if k not in r:
            errs.append(f"缺少顶层字段 {k}")
    if r.get("status") not in STATUS:
        errs.append(f"status 非法：{r.get('status')}")
    if not r.get("case_id"):
        errs.append("case_id 为空")
    res = r.get("results") or {}
    for k in RESULT_KEYS:
        if k not in res:
            errs.append(f"results 缺 {k}")
    if not str(res.get("revised_text") or "").strip():
        errs.append("results.revised_text 为空")
    for i, rv in enumerate(res.get("revisions") or []):
        for k in REVISION_KEYS:
            if k not in rv:
                errs.append(f"revisions[{i}] 缺 {k}")
        if rv.get("preserves_meaning") is not True:
            errs.append(f"revisions[{i}].preserves_meaning 必须为 true（不能确认保持原意就不要提交该条）")
        if str(rv.get("type") or "") not in REVISION_TYPES:
            errs.append(f"revisions[{i}].type 不在约定枚举：{rv.get('type')}")
    for i, s in enumerate(r.get("sources") or []):
        for k in ("source_id", "locator", "quote"):
            if not s.get(k):
                errs.append(f"sources[{i}] 缺 {k}")
    for i, u in enumerate(r.get("uncertainty") or []):
        for k in ("item", "reason", "action_required"):
            if not u.get(k):
                errs.append(f"uncertainty[{i}] 缺 {k}")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="润色结果序列化与契约校验")
    ap.add_argument("--case", required=True)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skill-name", default="academic-language-polishing")
    ap.add_argument("--skill-version", default="1.0.0")
    ap.add_argument("--task-id", default=None)
    a = ap.parse_args(argv)

    case, draft = load(a.case), load(a.draft)
    cid, tid = case_ids(case)
    res = dict(draft.get("results") or {})
    for k in RESULT_KEYS:
        res.setdefault(k, "" if k == "revised_text" else [])

    out_obj = {
        "case_id": draft.get("case_id") or cid,
        "task_id": a.task_id or draft.get("task_id") or tid or "product-arena-02-7051d92d",
        "status": draft.get("status") or "partial",
        "results": res,
        "sources": draft.get("sources") or [],
        "uncertainty": draft.get("uncertainty") or [],
        "changes": draft.get("changes") or [],
        "artifacts": draft.get("artifacts") or [],
        "metadata": {"skill_name": a.skill_name, "skill_version": a.skill_version,
                     "model": (draft.get("metadata") or {}).get("model", ""),
                     "runtime": f"python {sys.version.split()[0]}",
                     "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")},
    }
    errs = validate(out_obj)
    if errs:
        print("INVALID: " + "; ".join(errs), file=sys.stderr)
        return 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {a.out}")
    print(f"status={out_obj['status']} revisions={len(res['revisions'])} "
          f"glossary={len(res['glossary'])} chars={len(res['revised_text'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
