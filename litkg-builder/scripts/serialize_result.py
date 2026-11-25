#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 results 草稿组装成官方契约形态的 result.json，并做必填校验。

用法：
  python3 scripts/serialize_result.py \
      --case /input/case.json \
      --draft /app/work/results_draft.json \
      --out /app/output/result.json \
      --skill-name litkg-builder

草稿形态（只写主结果即可，其余字段由本脚本补齐并校验）：
  {"results": {"papers": [...], "graph": {...}, "queries": [...], "qc": {...}},
   "sources": [...], "uncertainty": [...], "changes": [...], "artifacts": [...]}
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

STATUS = {"success", "partial", "undetermined", "refused"}
TOP = ("case_id", "task_id", "status", "results", "sources", "uncertainty", "changes", "artifacts", "metadata")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pick_case_ids(case):
    case_id = str(case.get("case_id") or case.get("id") or "")
    task_id = str(case.get("task_id") or case.get("challenge_id") or "")
    if not case_id:
        for key in ("case", "request", "task"):
            v = case.get(key)
            if isinstance(v, dict) and v.get("case_id"):
                case_id = str(v["case_id"])
                task_id = task_id or str(v.get("task_id") or "")
                break
    return case_id, task_id


def validate(result):
    errs = []
    for k in TOP:
        if k not in result:
            errs.append(f"缺少顶层字段 {k}")
    if result.get("status") not in STATUS:
        errs.append(f"status 非法：{result.get('status')}（只能 {'|'.join(sorted(STATUS))}）")
    if not result.get("case_id"):
        errs.append("case_id 为空（必须原样来自 case.json）")
    res = result.get("results") or {}
    graph = res.get("graph") or {}
    for k in ("nodes", "edges", "merges", "conflicts"):
        if k not in graph:
            errs.append(f"results.graph 缺少 {k}")
    qs = res.get("queries") or []
    if len(qs) < 3:
        errs.append(f"queries 少于 3 条（实际 {len(qs)}）")
    for i, q in enumerate(qs):
        if "undetermined" not in q:
            errs.append(f"queries[{i}] 缺 undetermined")
    for i, s in enumerate(result.get("sources") or []):
        for k in ("source_id", "locator", "quote"):
            if not s.get(k):
                errs.append(f"sources[{i}] 缺 {k}")
    for i, u in enumerate(result.get("uncertainty") or []):
        for k in ("item", "reason", "action_required"):
            if not u.get(k):
                errs.append(f"uncertainty[{i}] 缺 {k}")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="litkg 结果序列化与契约校验")
    ap.add_argument("--case", required=True)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skill-name", default="litkg-builder")
    ap.add_argument("--skill-version", default="1.0.0")
    ap.add_argument("--task-id", default=None)
    a = ap.parse_args(argv)

    case = load(a.case)
    draft = load(a.draft)
    case_id, task_id = pick_case_ids(case)

    result = {
        "case_id": draft.get("case_id") or case_id,
        "task_id": a.task_id or draft.get("task_id") or task_id or "product-arena-10-760d1a0b",
        "status": draft.get("status") or "partial",
        "results": draft.get("results") or {},
        "sources": draft.get("sources") or [],
        "uncertainty": draft.get("uncertainty") or [],
        "changes": draft.get("changes") or [],
        "artifacts": draft.get("artifacts") or [],
        "metadata": {
            "skill_name": a.skill_name,
            "skill_version": a.skill_version,
            "model": draft.get("metadata", {}).get("model", ""),
            "runtime": f"python {sys.version.split()[0]}",
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        },
    }

    errs = validate(result)
    if errs:
        print("INVALID: " + "; ".join(errs), file=sys.stderr)
        return 1

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(f"status={result['status']} nodes={len(result['results']['graph']['nodes'])} "
          f"edges={len(result['results']['graph']['edges'])} queries={len(result['results']['queries'])} "
          f"sources={len(result['sources'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
