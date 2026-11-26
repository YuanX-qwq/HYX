#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 assertion_set.json 组装成平台官方 result.json（仅标准库）。

官方 results：
  nanopubs[] / quality_flags[]
nanopub 必填：assertion / subject / predicate / object / conditions / evidence{source_id,locator,quote,evidence_type}
             / source_metadata{authors,year,version,doi_or_id} / confidence / status

用法：
  python3 scripts/serialize_result.py --assertions /app/work/assertion_set.json \
      --case /input/case.json --out /app/output/result.json \
      --task-id <challenge-slug>
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

STATUS = ("checked", "flagged", "rejected", "unverified")
TOP = ("case_id", "task_id", "status", "results", "sources", "uncertainty", "changes", "artifacts", "metadata")
RES_KEYS = ("nanopubs", "quality_flags")
QC2PUB = {"pass": "checked", "warn": "flagged", "fail": "rejected"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def obj_text(o):
    if not isinstance(o, dict):
        return str(o or "")
    name = o.get("name") or ""
    val = o.get("value")
    unit = o.get("unit") or ""
    if val not in (None, ""):
        return f"{name} = {val}{(' ' + unit) if unit else ''}".strip(" =")
    return name


def conditions(a):
    qs = a.get("qualifiers") or {}
    parts = [f"{k}={v}" for k, v in qs.items() if v not in (None, "", [])]
    if a.get("polarity") == "negative":
        parts.append("polarity=negative")
    return "; ".join(parts)


def ev_locator(ev):
    bits = []
    if ev.get("page") not in (None, ""):
        bits.append(f"page {ev['page']}")
    if ev.get("paragraph_id"):
        bits.append(f"paragraph {ev['paragraph_id']}")
    if ev.get("char_start") is not None and ev.get("char_end") is not None:
        bits.append(f"chars {ev['char_start']}-{ev['char_end']}")
    return ", ".join(bits) or "paragraph unknown"


def to_nanopub(a, src):
    ev = (a.get("evidence") or [{}])[0]
    return {
        "assertion": a.get("text", ""),
        "subject": obj_text(a.get("subject")),
        "predicate": (a.get("relation") or {}).get("predicate", ""),
        "object": obj_text(a.get("object")),
        "conditions": conditions(a),
        "evidence": {
            "source_id": src.get("source_id", ""),
            "locator": ev_locator(ev),
            "quote": ev.get("quote", ""),
            "evidence_type": ev.get("relation_to_assertion") or ("direct" if ev.get("support") == "full" else "supporting"),
        },
        "source_metadata": {
            "authors": src.get("authors") or [],
            "year": str(src.get("year") or ""),
            "version": str(src.get("version") or ""),
            "doi_or_id": str(src.get("doi") or src.get("source_id") or ""),
        },
        "confidence": (a.get("confidence") or {}).get("level") or "medium",
        "status": QC2PUB.get((a.get("qc") or {}).get("status"), "unverified"),
    }


def to_flags(assertions):
    out = []
    for a in assertions:
        for i in ((a.get("qc") or {}).get("issues") or []):
            out.append({"assertion_id": a.get("id", ""), "code": i.get("code", ""),
                        "severity": i.get("severity", ""), "detail": i.get("detail", "")})
    return out


def resolve_ids(draft, case):
    case = case or {}
    cid = draft.get("case_id") or case.get("case_id") or case.get("id") or ""
    tid = case.get("task_id") or case.get("challenge_id") or ""
    return str(cid), str(tid)


def validate(result):
    errs = []
    for k in TOP:
        if k not in result:
            errs.append("缺少顶层字段 " + k)
    if result.get("status") not in ("success", "partial", "failed", "refused"):
        errs.append("status 非法：" + str(result.get("status")))
    if not result.get("case_id"):
        errs.append("case_id 为空（必须原样来自 case.json）")
    res = result.get("results") or {}
    extra = [k for k in res if k not in RES_KEYS]
    if extra:
        errs.append("results 出现契约外字段：" + str(extra))
    for k in RES_KEYS:
        if k not in res:
            errs.append("results 缺少 " + k)
    pubs = res.get("nanopubs") or []
    if len(pubs) < 3:
        errs.append("nanopubs 少于 3 条（实际 %d）" % len(pubs))
    for i, p in enumerate(pubs):
        for k in ("assertion", "subject", "predicate", "object"):
            if not p.get(k):
                errs.append("nanopubs[%d] 缺 %s" % (i, k))
        ev = p.get("evidence") or {}
        for k in ("source_id", "locator", "quote"):
            if not ev.get(k):
                errs.append("nanopubs[%d].evidence 缺 %s" % (i, k))
        if len((ev.get("quote") or "").strip()) < 6:
            errs.append("nanopubs[%d].evidence.quote 过短（<6 字符），不足复核" % i)
        sm = p.get("source_metadata") or {}
        for k in ("authors", "year", "version", "doi_or_id"):
            if k not in sm:
                errs.append("nanopubs[%d].source_metadata 缺 %s" % (i, k))
        if not sm.get("authors") or not sm.get("year"):
            errs.append("nanopubs[%d].source_metadata 缺作者或年份" % i)
        if p.get("status") not in STATUS:
            errs.append("nanopubs[%d].status 非法：%s" % (i, p.get("status")))
        if p.get("confidence") not in ("high", "medium", "low"):
            errs.append("nanopubs[%d].confidence 非法：%s" % (i, p.get("confidence")))
        # 断言不得是多句拼接：只看句末标点之后是否还有正文（剔除小数点与结尾句号）
        plain = re.sub(r"(\d)\.(?=\d)", r"\1", (p.get("assertion") or "").strip())
        inner = re.findall(r"[。！？]|[.!?](?=\s+[A-Z0-9\u4e00-\u9fa5])", plain[:-1] if plain else "")
        if inner:
            errs.append("nanopubs[%d] assertion 含多句，未拆成单条断言" % i)
    if not isinstance(res.get("quality_flags"), list):
        errs.append("quality_flags 必须是 list")
    for i, s in enumerate(result.get("sources") or []):
        for k in ("source_id", "locator", "quote"):
            if not s.get(k):
                errs.append("sources[%d] 缺 %s" % (i, k))
    for i, u in enumerate(result.get("uncertainty") or []):
        for k in ("item", "reason", "action_required"):
            if not u.get(k):
                errs.append("uncertainty[%d] 缺 %s" % (i, k))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="nanopub 结果序列化与官方契约校验")
    ap.add_argument("--assertions", required=True, help="assertion_set.json")
    ap.add_argument("--case", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--skill-name", default="nanopublication-extraction")
    ap.add_argument("--skill-version", default="1.0.0")
    a = ap.parse_args(argv)

    draft = load(a.assertions)
    case = load(a.case) if a.case and Path(a.case).exists() else {}
    assertions = draft.get("assertions") or []
    src = draft.get("source") or {}
    case_id, task_id = resolve_ids(draft, case)

    nanopubs = [to_nanopub(x, src) for x in assertions]
    sources, seen = [], set()
    for p in nanopubs:
        ev = p["evidence"]
        key = (ev["source_id"], ev["locator"], ev["quote"][:80])
        if key in seen:
            continue
        seen.add(key)
        sources.append({"source_id": ev["source_id"], "locator": ev["locator"], "locator_type": "paragraph",
                        "quote": ev["quote"], "note": "nanopub evidence, " + ev["evidence_type"]})

    uncertainty = list(draft.get("uncertainty") or [])
    for u in draft.get("unreported") or []:
        uncertainty.append({"item": u.get("item") or str(u), "reason": u.get("reason") or "原文未报告",
                            "action_required": u.get("action_required") or "回到原文或补充材料确认"})
    if not uncertainty:
        uncertainty.append({"item": "未报告的数值/条件", "reason": "材料未给出，未做推断",
                            "action_required": "如需该值请提供补充材料"})

    status = "success"
    flags = to_flags(assertions)
    if any(f["severity"] == "fail" for f in flags):
        status = "partial"
    if not nanopubs:
        status = "failed"
    changes = []
    for i, c in enumerate(draft.get("change_log") or [], 1):
        changes.append({"step": str(i), "action": c.get("step", ""), "note": c.get("detail", "")})
    if not changes:
        changes = [{"step": "1", "action": "读取 case.json / task.md", "note": "确认来源与范围"}]

    result = {
        "case_id": case_id,
        "task_id": a.task_id or task_id or "product-arena-09-0e8befd4",
        "status": status,
        "results": {"nanopubs": nanopubs, "quality_flags": flags},
        "sources": sources,
        "uncertainty": uncertainty,
        "changes": changes,
        "artifacts": draft.get("artifacts") or [],
        "metadata": {"skill_name": a.skill_name, "skill_version": a.skill_version, "model": "",
                     "runtime": "python " + sys.version.split()[0],
                     "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")},
    }
    errs = validate(result)
    if errs:
        print("INVALID: " + "; ".join(errs), file=sys.stderr)
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote " + str(out))
    print("status=%s nanopubs=%d flags=%d sources=%d uncertainty=%d"
          % (result["status"], len(nanopubs), len(flags), len(sources), len(uncertainty)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
