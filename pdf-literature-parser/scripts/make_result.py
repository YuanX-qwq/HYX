#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_result.py — 组装 /app/output/result.json

契约:
  1. 读取 /input/case.json（含 case_id 与 output_contract 字段模板）。
  2. 合并 answers.json（Agent 写的答案与证据引用）。
  3. 逐条机械核验证据引文（quote 是否在 document.json 中逐字命中）。
  4. 写 result.json：保留 output_contract 全部字段 + status/evidence/uncertainty/change_log。

用法:
  python3 make_result.py \
    --case /input/case.json \
    --answers /app/work/answers.json \
    --document /app/work/document.json \
    --probe /app/work/probe.json \
    --verify-report /app/work/verify_report.json \
    --out /app/output/result.json \
    [--change-log /app/work/change_log.json] \
    [--contract-result-field result]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdftool import locate_quote  # noqa: E402


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_one(document, ev):
    quote = (ev or {}).get("quote") or (ev or {}).get("text") or ""
    block_id = (ev or {}).get("block_id") or (ev or {}).get("block")
    hits = locate_quote(document, quote) if quote else []
    if quote and hits:
        if block_id:
            ok = any(h.get("block_id") == block_id for h in hits)
            return ("verified" if ok else "mismatch", hits)
        return ("verified", hits)
    if not quote:
        return ("no-quote", [])
    return ("unverified", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--document", required=True)
    ap.add_argument("--probe", default=None)
    ap.add_argument("--verify-report", default=None)
    ap.add_argument("--change-log", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--contract-result-field", default="result",
                    help="output_contract 中承载答案的字段名，默认 result")
    a = ap.parse_args()

    case = load(a.case)
    answers = load(a.answers)
    document = load(a.document)

    case_id = case.get("case_id") or case.get("id") or answers.get("case_id") or "unknown"
    contract = case.get("output_contract") or {}
    if not isinstance(contract, dict):
        contract = {}

    result = {}
    # 保留契约全部字段
    for k, v in contract.items():
        result[k] = v if v is not None else None

    payload = answers.get(a.contract_result_field) or answers.get("answers") or answers
    result[a.contract_result_field] = payload

    # 核验
    verify = []
    n_ok = 0

    def walk(node, path):
        nonlocal n_ok
        if isinstance(node, dict):
            for k in ("evidence", "evidences", "sources"):
                v = node.get(k)
                if isinstance(v, list):
                    for i, e in enumerate(v):
                        st, hits = _check_one(document, e)
                        if st == "verified":
                            n_ok += 1
                        e.setdefault("verification", st)
                        verify.append({"path": "%s.%s[%d]" % (path, k, i),
                                       "status": st,
                                       "quote": str((e or {}).get("quote", ""))[:200],
                                       "block_id": (e or {}).get("block_id"),
                                       "hit_pages": sorted(set(h.get("page") for h in hits))})
                elif isinstance(v, dict):
                    st, hits = _check_one(document, v)
                    if st == "verified":
                        n_ok += 1
                    v.setdefault("verification", st)
                    verify.append({"path": "%s.%s" % (path, k), "status": st,
                                   "quote": str(v.get("quote", ""))[:200],
                                   "hit_pages": sorted(set(h.get("page") for h in hits))})
            for k, v in node.items():
                if k not in ("evidence", "evidences", "sources"):
                    walk(v, path + "." + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (path, i))

    walk(payload, a.contract_result_field)

    # 状态与不确定性
    status = answers.get("status") or "success"
    uncertainty = list(answers.get("uncertainty") or [])
    unreported = list(answers.get("unreported") or [])
    for v in verify:
        if v["status"] != "verified":
            uncertainty.append({
                "kind": "evidence-unverified",
                "path": v["path"],
                "detail": "证据未通过机械核验: %s" % v["status"]})
    if n_ok == 0 and verify:
        status = "partial"

    change_log = []
    if a.change_log and os.path.exists(a.change_log):
        change_log = load(a.change_log)

    result.setdefault("case_id", case_id)
    result["status"] = status
    result["evidence_check"] = {
        "checked": len(verify), "verified": n_ok,
        "items": verify}
    result["uncertainty"] = uncertainty
    result["unreported"] = unreported
    result["sources"] = {
        "document_model": "/app/output/document.json",
        "probe": a.probe or None,
        "document_sha256": document.get("source", {}).get("sha256"),
        "pages": document.get("source", {}).get("pages"),
    }
    result["change_log"] = change_log

    if a.verify_report:
        try:
            vr = load(a.verify_report)
            result["verify_report"] = vr
        except Exception:
            pass

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps({
        "ok": True, "case_id": case_id, "status": status,
        "evidence_checked": len(verify), "evidence_verified": n_ok,
        "uncertainty": len(uncertainty),
        "out": os.path.abspath(a.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
