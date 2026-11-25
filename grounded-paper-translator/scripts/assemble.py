#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""assemble.py -- build the deliverable bundle from segments + translations.

Writes into --out-dir:

  result.json      structured result: case_id, status, result{glossary,
                   bilingual_paragraphs, metrics, verification, scope},
                   evidence, uncertainty, sources, change_log
  bilingual.md     paragraph-aligned reading copy (pid / page / source / 中文)
  bilingual.csv    same alignment, one row per paragraph
  glossary.csv     the locked glossary in portable form

Status policy (honest by construction):
  success  -- every pid in scope translated and verify.py reports no FAIL
  partial  -- some pid missing, or verify.py reports FAILs (limits listed)
  failed   -- no translation at all (reason recorded)

Usage
-----
  python3 assemble.py --segments work/segments.json \
      --translations work/translations.jsonl --glossary work/glossary.json \
      --scope work/scope.json --verify work/verify_report.json \
      --case /input/case.json --out-dir /app/output
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys


def load(p, default=None):
    if not p or not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha256(path):
    if not path or not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_translations(path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from verify import load_translations as _lt
    return _lt(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--translations", required=True)
    ap.add_argument("--glossary", default=None)
    ap.add_argument("--scope", default=None)
    ap.add_argument("--verify", default=None)
    ap.add_argument("--case", default=None)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--change-log", default=None)
    ap.add_argument("--extra-status-note", default=None)
    a = ap.parse_args(argv)

    doc = load(a.segments)
    segs = doc["segments"]
    trans = load_translations(a.translations)
    gloss = (load(a.glossary, {}) or {}).get("terms", [])
    scope = load(a.scope, {}) or {}
    ver = load(a.verify, {}) or {}
    case = load(a.case, {}) or {}
    case_id = case.get("case_id") or "unknown-case"

    scope_pids = scope.get("pids") or [s["pid"] for s in segs if s["kind"] in
                                       ("title", "abstract", "heading", "body", "caption",
                                        "table", "footnote")]
    covered = [p for p in scope_pids if trans.get(p) and str(trans[p].get("zh") or "").strip()]
    missing = [p for p in scope_pids if p not in covered]
    coverage = len(covered) / max(1, len(scope_pids))
    fails = (ver.get("metrics") or {}).get("fail_count", 0)

    if not covered:
        status = "failed"
        status_note = "没有任何段落完成翻译；原因见 change_log 与 uncertainty。"
    elif coverage >= 1.0 and not fails:
        status = "success"
        status_note = "范围内全部段落完成翻译，机械核验无 FAIL。"
    else:
        status = "partial"
        bits = []
        if missing:
            bits.append("未译段落 %d 个（%s）" % (len(missing), ", ".join(missing[:8])))
        if fails:
            bits.append("机械核验 FAIL %d 条，见 verification.human_review" % fails)
        status_note = "；".join(bits) + "。"

    bilingual = []
    evidence = []
    for s in segs:
        pid = s["pid"]
        t = trans.get(pid) or {}
        zh = str(t.get("zh") or "").strip()
        if pid not in scope_pids:
            continue
        item = {
            "pid": pid,
            "page": s["page"],
            "page_end": s.get("page_end"),
            "kind": s["kind"],
            "section": s.get("section") or "",
            "source": s["text"],
            "translation": zh,
            "sentences": s.get("sentences", []),
            "status": "translated" if zh else "missing",
        }
        notes = t.get("notes") or t.get("translation_notes")
        if notes:
            item["translation_notes"] = notes if isinstance(notes, list) else [str(notes)]
        if t.get("uncertainty"):
            item["uncertainty"] = t["uncertainty"]
        bilingual.append(item)
        evidence.append({
            "pid": pid, "page": s["page"], "bbox": s.get("bbox"),
            "quote": s["text"][:160],
            "anchor": "p%db?bbox=%s" % (s["page"], ",".join(str(x) for x in (s.get("bbox") or []))),
        })

    title = next((b for b in bilingual if b["kind"] == "title"), None) or None
    abstract = next((b for b in bilingual if b["kind"] == "abstract"), None) or None

    metrics = {
        "paragraphs_in_scope": len(scope_pids),
        "paragraphs_translated": len(covered),
        "coverage": round(coverage, 4),
        "words_in_scope": sum(s["words"] for s in segs if s["pid"] in scope_pids),
        "characters_translated": sum(len(b["translation"]) for b in bilingual),
        "glossary_terms_locked": len(gloss),
        "glossary_consistency": ((ver.get("metrics") or {}).get("glossary_consistency")),
        "verification_fail": fails,
        "verification_warn": ((ver.get("metrics") or {}).get("warn_count")),
    }

    result = {
        "title": ({"source": title["source"], "translation": title["translation"], "pid": title["pid"]}
                  if title else None),
        "abstract": ({"source": abstract["source"], "translation": abstract["translation"],
                      "pid": abstract["pid"]} if abstract else None),
        "glossary": [{"term_en": g["term_en"], "term_zh": g["term_zh"],
                      "category": g.get("category", ""), "variants": g.get("variants", []),
                      "locked": True} for g in gloss],
        "bilingual_paragraphs": bilingual,
        "metrics": metrics,
        "verification": {
            "status": ver.get("status"),
            "coverage": ver.get("coverage"),
            "issue_counts": ver.get("issue_counts", {}),
            "human_review": ver.get("human_review", []),
        },
        "scope": {"mode": scope.get("mode", "full"), "pids": scope_pids,
                  "verbatim_pids": scope.get("verbatim_pids", [])},
    }

    # merge any output_contract fields declared by the case file
    contract = case.get("output_contract") or {}
    unknown = []
    for key in contract:
        if key in result:
            continue
        if key == "translation":
            result["translation"] = {"source_language": "en", "target_language": "zh-CN",
                                     "paragraphs": bilingual}
        else:
            result[key] = None
            unknown.append(key)

    uncertainty = []
    for m in missing:
        uncertainty.append({"pid": m, "kind": "not-translated",
                            "detail": "该段落在声明范围内但未提供译文，需人工接管或补译。"})
    for item in (ver.get("issues") or []):
        if item.get("severity") == "fail":
            uncertainty.append({"pid": item["pid"], "kind": "check-failed",
                                "check": item["check"], "detail": item["detail"]})
    if unknown:
        uncertainty.append({"kind": "contract-field-unmapped",
                            "detail": "案例 output_contract 中以下字段无法由翻译流水线填写：%s" % unknown})
    if a.extra_status_note:
        uncertainty.append({"kind": "status-note", "detail": a.extra_status_note})

    change_log = load(a.change_log, None)
    if not change_log:
        change_log = [
            {"step": "segment", "detail": "解析 %d 页，得到 %d 个段落单元（可译 %d），来源 %s" % (
                doc["source"]["pages"], len(segs), len(scope_pids), doc["source"].get("backend"))},
            {"step": "glossary", "detail": "锁定术语 %d 条" % len(gloss)},
            {"step": "translate", "detail": "完成 %d/%d 段译文" % (len(covered), len(scope_pids))},
            {"step": "verify", "detail": "机械核验 FAIL %s / WARN %s；术语一致率 %s" % (
                fails, metrics["verification_warn"], metrics["glossary_consistency"])},
            {"step": "status", "detail": status_note},
        ]

    sources = {
        "document": os.path.basename(doc["source"]["file"]),
        "document_sha256": doc["source"].get("sha256"),
        "pages": doc["source"]["pages"],
        "backend": doc["source"].get("backend"),
        "segments_file": os.path.basename(a.segments),
        "translations_file": os.path.basename(a.translations),
        "glossary_file": os.path.basename(a.glossary) if a.glossary else None,
        "verify_file": os.path.basename(a.verify) if a.verify else None,
        "case_file": os.path.basename(a.case) if a.case else None,
    }

    out = {
        "schema": "translation-result/v1",
        "case_id": case_id,
        "status": status,
        "status_note": status_note,
        "target_language": "zh-CN",
        "result": result,
        "coverage": {"rate": round(coverage, 4), "missing": missing,
                     "scope": len(scope_pids)},
        "evidence": evidence,
        "uncertainty": uncertainty,
        "unreported": [u["detail"] for u in uncertainty if u.get("kind") == "not-translated"],
        "sources": sources,
        "change_log": change_log,
    }

    os.makedirs(a.out_dir, exist_ok=True)
    rp = os.path.join(a.out_dir, "result.json")
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    md = os.path.join(a.out_dir, "bilingual.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# 双语对照：%s\n\n" % sources["document"])
        f.write("case_id=%s status=%s coverage=%.1f%% terms=%d\n\n" %
                (case_id, status, 100 * coverage, len(gloss)))
        f.write("> 每个段落以 pid 与原文页码锚定；未译段落标注 `[未译]`。\n\n")
        for b in bilingual:
            f.write("## %s · p%s · %s%s\n\n" % (b["pid"], b["page"], b["kind"],
                                               (" · " + b["section"]) if b["section"] else ""))
            f.write("**EN** %s\n\n" % b["source"])
            f.write("**ZH** %s\n\n" % (b["translation"] if b["translation"] else "[未译]"))

    csvp = os.path.join(a.out_dir, "bilingual.csv")
    with open(csvp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pid", "page", "kind", "section", "source", "translation", "status"])
        for b in bilingual:
            w.writerow([b["pid"], b["page"], b["kind"], b["section"], b["source"],
                        b["translation"], b["status"]])

    gp = os.path.join(a.out_dir, "glossary.csv")
    with open(gp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["term_en", "term_zh", "category", "variants", "locked"])
        for g in gloss:
            w.writerow([g["term_en"], g["term_zh"], g.get("category", ""),
                        "|".join(g.get("variants") or []), "yes"])

    print(json.dumps({"ok": True, "status": status, "coverage": round(coverage, 4),
                      "paragraphs": len(bilingual), "terms": len(gloss),
                      "result": os.path.abspath(rp), "bilingual_md": os.path.abspath(md),
                      "bilingual_csv": os.path.abspath(csvp)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
