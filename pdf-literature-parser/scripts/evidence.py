#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evidence.py — 证据检索与核验（“核得回”）

三个子命令:
  locate   在 document.json 中检索引文原文，返回页码/块/区块/bbox/上下文
  check    检查 answers.json 里每一条 evidence 的 quote 是否能在文档模型中找到
  verify   对 result.json 做最终核验：逐条证据 -> verified/unverified，写核验报告

用法:
  python3 evidence.py locate --document /app/work/document.json --quote "the text"
  python3 evidence.py check   --document /app/work/document.json --answers /app/work/answers.json --out /app/work/quote_check.json
  python3 evidence.py verify  --document /app/work/document.json --result /app/output/result.json --out /app/work/verify_report.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdftool import locate_quote, norm_for_search  # noqa: E402


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_locate(a):
    document = load(a.document)
    hits = locate_quote(document, a.quote)
    print(json.dumps({"quote": a.quote, "hits": hits, "count": len(hits)},
                     ensure_ascii=False, indent=1))


def _check_evidence(document, ev):
    """ev: {quote?, block_id?, page?} -> {status, hits, detail}"""
    if not isinstance(ev, dict):
        return {"status": "malformed", "hits": [], "detail": "evidence 不是对象"}
    quote = ev.get("quote") or ev.get("text") or ""
    block_id = ev.get("block_id") or ev.get("block")
    page = ev.get("page")
    hits = locate_quote(document, quote) if quote else []
    # 块 id 校验
    bid_ok = None
    if block_id:
        found = False
        for p in document.get("pages", []):
            for b in p.get("blocks", []):
                if b.get("id") == block_id:
                    found = True
                    break
        bid_ok = found
    else:
        bid_ok = True  # 未指定则仅按引文核验
    if quote and hits and bid_ok is not False:
        if block_id:
            matched = [h for h in hits if h.get("block_id") == block_id]
            if matched:
                return {"status": "verified", "hits": matched,
                        "detail": "引文在指定块内逐字命中"}
            return {"status": "mismatch", "hits": hits,
                    "detail": "引文存在于文档，但不在指定块 %s" % block_id}
        return {"status": "verified", "hits": hits, "detail": "引文逐字命中"}
    if quote and not hits:
        return {"status": "unverified", "hits": [],
                "detail": "引文在文档模型中未找到（可能跨块截断或文本被改写）"}
    if not quote:
        return {"status": "no-quote", "hits": [],
                "detail": "证据未提供引文，无法机械核验"}
    return {"status": "unverified", "hits": hits, "detail": "核验条件不满足"}


def _iter_evidences(answers):
    """递归收集 answers 中的 evidence 条目。"""
    out = []

    def walk(node, path):
        if isinstance(node, dict):
            for k in ("evidence", "evidences", "sources", "source"):
                v = node.get(k)
                if isinstance(v, list):
                    for i, e in enumerate(v):
                        out.append((e, path + [k, str(i)]))
                elif isinstance(v, dict):
                    out.append((v, path + [k]))
            for k, v in node.items():
                walk(v, path + [k])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [str(i)])

    walk(answers, ["answers"])
    return out


def cmd_check(a):
    document = load(a.document)
    answers = load(a.answers)
    evs = _iter_evidences(answers)
    report = {"total": len(evs), "verified": 0, "unverified": 0,
              "mismatch": 0, "malformed": 0, "no_quote": 0, "items": []}
    for ev, path in evs:
        r = _check_evidence(document, ev)
        report["items"].append({
            "path": ".".join(path), "quote": str(ev.get("quote", ""))[:160],
            "status": r["status"], "detail": r["detail"],
            "hits": r["hits"][:5]})
        key = {"verified": "verified", "unverified": "unverified",
               "mismatch": "mismatch", "malformed": "malformed",
               "no-quote": "no_quote"}.get(r["status"], "unverified")
        if key in report:
            report[key] += 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps({"total": report["total"], "verified": report["verified"],
                      "unverified": report["unverified"],
                      "mismatch": report["mismatch"],
                      "no_quote": report["no_quote"],
                      "out": os.path.abspath(a.out)}, ensure_ascii=False))


def cmd_verify(a):
    document = load(a.document)
    result = load(a.result)
    evs = _iter_evidences(result.get("result", result))
    report = {"total": len(evs), "verified": 0, "unverified": 0, "items": []}
    for ev, path in evs:
        r = _check_evidence(document, ev)
        report["items"].append({"path": ".".join(path), "status": r["status"],
                                "detail": r["detail"]})
        if r["status"] == "verified":
            report["verified"] += 1
        else:
            report["unverified"] += 1
    report["verdict"] = "all-verified" if report["unverified"] == 0 else "has-unverified"
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("locate")
    p1.add_argument("--document", required=True)
    p1.add_argument("--quote", required=True)
    p1.set_defaults(fn=cmd_locate)

    p2 = sub.add_parser("check")
    p2.add_argument("--document", required=True)
    p2.add_argument("--answers", required=True)
    p2.add_argument("--out", required=True)
    p2.set_defaults(fn=cmd_check)

    p3 = sub.add_parser("verify")
    p3.add_argument("--document", required=True)
    p3.add_argument("--result", required=True)
    p3.add_argument("--out", required=True)
    p3.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
