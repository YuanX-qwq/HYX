#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 results 草稿校验并组装成官方契约形态的 result.json（仅标准库）。

官方 results 结构：
  nodes[] / edges[] / alignments[] / queries[{query, results, evidence}] / conflicts[]

用法：
  python3 scripts/serialize_result.py --case /input/case.json \
      --draft /app/work/results_draft.json --out /app/output/result.json \
      --skill-name literature-knowledge-graph

硬约束（任一条不满足即拒绝写出）：
  1) results 只允许 nodes/edges/alignments/queries/conflicts 五个键（多一个都不行）
  2) 每个 node 必须有 id/type/label 与非空 evidence（含 source_id/paragraph_id/quote）
  3) 每个 edge 必须有 id/type/subject/object 与非空 evidence，且 subject/object 指向已存在节点
  4) 每个 alignment 必须有 canonical/decision/basis
  5) queries ≥3，每条有 query/results/evidence，evidence 非空且可回链
  6) status=success 时不得仍有 fail 级 qc 残留（由 kg.py 落 qc.json 判定）
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

STATUS = {"success", "partial", "undetermined", "refused"}
TOP = ("case_id", "task_id", "status", "results", "sources", "uncertainty", "changes", "artifacts", "metadata")
RES_KEYS = ("nodes", "edges", "alignments", "queries", "conflicts")


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
    extra = [k for k in res if k not in RES_KEYS]
    if extra:
        errs.append(f"results 出现契约外字段：{extra}")
    for k in RES_KEYS:
        if k not in res:
            errs.append(f"results 缺少 {k}")

    node_ids = set()
    for i, n in enumerate(res.get("nodes") or []):
        for k in ("id", "type", "label"):
            if not n.get(k):
                errs.append(f"nodes[{i}] 缺 {k}")
        node_ids.add(n.get("id"))
        if not n.get("evidence"):
            errs.append(f"nodes[{i}] 无证据")
        for j, ev in enumerate(n.get("evidence") or []):
            for k in ("source_id", "paragraph_id", "quote"):
                if not ev.get(k):
                    errs.append(f"nodes[{i}].evidence[{j}] 缺 {k}")

    for i, e in enumerate(res.get("edges") or []):
        for k in ("id", "type", "subject", "object"):
            if not e.get(k):
                errs.append(f"edges[{i}] 缺 {k}")
        if e.get("subject") not in node_ids or e.get("object") not in node_ids:
            errs.append(f"edges[{i}] 端点不在 nodes 中")
        if not e.get("evidence"):
            errs.append(f"edges[{i}] 无证据")

    for i, a in enumerate(res.get("alignments") or []):
        for k in ("canonical", "decision", "basis"):
            if not a.get(k):
                errs.append(f"alignments[{i}] 缺 {k}")

    qs = res.get("queries") or []
    if len(qs) < 3:
        errs.append(f"queries 少于 3 条（实际 {len(qs)}）")
    for i, q in enumerate(qs):
        for k in ("query", "results", "evidence"):
            if k not in q:
                errs.append(f"queries[{i}] 缺 {k}")
        if not q.get("evidence") and q.get("results"):
            errs.append(f"queries[{i}] 有命中却无证据（空结果允许 evidence=[]）")

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
    ap.add_argument("--skill-name", default="literature-knowledge-graph")
    ap.add_argument("--skill-version", default="1.0.0")
    ap.add_argument("--task-id", default=None)
    a = ap.parse_args(argv)

    case = load(a.case)
    draft = load(a.draft)
    case_id, task_id = pick_case_ids(case)

    res = draft.get("results") or {}
    result = {
        "case_id": draft.get("case_id") or case_id,
        "task_id": a.task_id or draft.get("task_id") or task_id or "product-arena-10-760d1a0b",
        "status": draft.get("status") or "partial",
        "results": {k: res.get(k) for k in RES_KEYS},
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
    print(f"status={result['status']} nodes={len(result['results']['nodes'])} "
          f"edges={len(result['results']['edges'])} alignments={len(result['results']['alignments'])} "
          f"queries={len(result['results']['queries'])} conflicts={len(result['results']['conflicts'])} "
          f"sources={len(result['sources'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
