#!/usr/bin/env python3
"""把 results 草稿序列化为符合 output_contract 的 result.json，并做必填/枚举校验。

用法：
  python3 scripts/serialize_result.py --input /input/case.json --draft /app/work/results_draft.json \
      --out /app/output/result.json --skill-name intro-related-work-writing
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

TOP = ["case_id", "task_id", "status", "results", "sources", "uncertainty",
       "changes", "artifacts", "metadata"]
STATUS = {"success", "partial", "undetermined", "refused"}
BACKGROUND = ["thread", "problem", "constraints", "open_issue"]
GAP = ["gap", "evidence", "how_paper_fills"]
WORK = ["ref", "conclusion", "conditions", "limitation"]
COVERAGE = ["key_works", "recent_works", "missing"]


def fail(msg):
    print("FAIL: " + msg, file=sys.stderr)
    raise SystemExit(1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="")
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skill-name", default="intro-related-work-writing")
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--strict-gap", action="store_true",
                    help="研究空白 evidence 为空时直接拒绝（默认只要求 status!=success）")
    a = ap.parse_args(argv)

    draft = json.loads(Path(a.draft).read_text(encoding="utf-8"))
    case = {}
    if a.input and Path(a.input).exists():
        try:
            case = json.loads(Path(a.input).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            case = {}

    oll = {k: draft.get(k) for k in TOP}
    res = dict(oll)
    res["case_id"] = draft.get("case_id") or case.get("case_id", "")
    res["task_id"] = draft.get("task_id") or case.get("task_id", "")
    res["status"] = draft.get("status") or "partial"
    for k in ("sources", "uncertainty", "changes", "artifacts"):
        res[k] = draft.get(k) or []

    missing = [k for k in TOP if k not in draft and k not in res]
    if missing:
        fail("缺少顶层字段: %s" % missing)
    if res["status"] not in STATUS:
        fail("status 非法: %r（允许 %s）" % (res["status"], sorted(STATUS)))
    if not res["case_id"]:
        fail("case_id 为空；必须原样写入 case.json 的 case_id")

    results = draft.get("results") or {k: draft[k] for k in
                                      ("background", "related_work", "gap", "contributions", "citations_coverage")
                                      if k in draft}
    if not results:
        fail("results 为空：需要 background / related_work / gap / contributions / citations_coverage")

    bg = results.get("background")
    if not isinstance(bg, dict):
        fail("results.background 必须是对象")
    for f in BACKGROUND:
        if f not in bg:
            fail("results.background 缺少字段 %s" % f)

    rw = results.get("related_work")
    if not isinstance(rw, list) or not rw:
        fail("results.related_work 必须是非空数组（按维度分组）")
    dims = set()
    for i, g in enumerate(rw):
        for f in ("group", "dimension", "works"):
            if f not in g:
                fail("results.related_work[%d] 缺少字段 %s" % (i, f))
        dims.add(g["dimension"])
        if not isinstance(g["works"], list) or not g["works"]:
            fail("results.related_work[%d].works 必须是非空数组" % i)
        for j, w in enumerate(g["works"]):
            for f in WORK:
                if f not in w:
                    fail("results.related_work[%d].works[%d] 缺少字段 %s" % (i, j, f))
            if not w["ref"]:
                fail("results.related_work[%d].works[%d].ref 为空" % (i, j))
    if len(dims) < 2:
        fail("相关工作至少要覆盖 2 个比较维度，当前只有 %s" % sorted(dims))

    gap = results.get("gap")
    if not isinstance(gap, dict):
        fail("results.gap 必须是对象")
    for f in GAP:
        if f not in gap:
            fail("results.gap 缺少字段 %s" % f)
    if (a.strict_gap or res["status"] == "success") and not gap.get("evidence"):
        fail("研究空白 evidence 为空，无法回链到已引文献；请补证据或把 status 降为 partial")

    contribs = results.get("contributions")
    if not isinstance(contribs, list):
        fail("results.contributions 必须是数组")
    for i, c in enumerate(contribs):
        for f in ("claim", "evidence_locator"):
            if f not in c:
                fail("results.contributions[%d] 缺少字段 %s" % (i, f))
        if not c["claim"]:
            fail("results.contributions[%d].claim 为空" % i)

    cov = results.get("citations_coverage")
    if not isinstance(cov, dict):
        fail("results.citations_coverage 必须是对象")
    for f in COVERAGE:
        if f not in cov:
            fail("results.citations_coverage 缺少字段 %s" % f)
        if not isinstance(cov[f], list):
            fail("results.citations_coverage.%s 必须是数组" % f)

    for i, s in enumerate(res["sources"]):
        for f in ("source_id", "locator", "locator_type", "quote"):
            if not s.get(f):
                fail("sources[%d] 缺少 %s" % (i, f))
    for i, u in enumerate(res["uncertainty"]):
        for f in ("item", "reason", "action_required"):
            if not u.get(f):
                fail("uncertainty[%d] 缺少 %s" % (i, f))

    res["results"] = results
    meta = dict(draft.get("metadata") or {})
    meta.setdefault("skill_name", a.skill_name)
    meta.setdefault("skill_version", a.version)
    meta.setdefault("generated_at", dt.datetime.now().astimezone().isoformat(timespec="seconds"))
    meta.setdefault("model", "")
    meta.setdefault("runtime", "")
    res["metadata"] = meta

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote %s status=%s dims=%d works=%d contributions=%d missing_cites=%d sources=%d uncertainty=%d"
          % (a.out, res["status"], len(dims), sum(len(g["works"]) for g in rw),
             len(contribs), len(cov["missing"]), len(res["sources"]), len(res["uncertainty"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
