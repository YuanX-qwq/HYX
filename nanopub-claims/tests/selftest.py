#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — fixture 自测（零第三方依赖、无网络、确定性）。

用法:
  python3 tests/selftest.py [--workdir DIR]

覆盖：段落切分与偏移、候选切分、引文定位、最小证据片段、证据绑定、
机械核验、Q001-Q013 质量检查、三种导出形态与确定性。
"""

import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import claimlib as cl  # noqa: E402
from claimlib import (candidates_from_paragraphs, locate_quote, minimal_span,  # noqa: E402
                      norm_ws, paragraphs_from_pages, qc_assertion_set, same_text,
                      split_sentences, to_csv, to_trig)

PAGES = [
    {"page": 1, "text": "化合物 A 在 25 °C 下抑制酶 B 的活性，使反应速率下降 40%。同时，化合物 A 对酶 C 没有明显影响。\n\n在 pH 7.4 条件下，化合物 A 的半衰期为 12.5 h。"},
    {"page": 2, "text": "我们由此推断，化合物 A 可能通过变构机制发挥作用。"},
]

SOURCE = {
    "source_id": "fixture-2026",
    "title": "Synthetic Paper for Nanopublication Selftest",
    "authors": ["A. Author", "B. Author"],
    "year": 2026,
    "venue": "Synthetic Journal",
    "doi": None,
    "version": "v1 (synthetic fixture)",
    "retrieved_from": "selftest.py inline fixture",
    "file_sha256": None,
    "license": "CC0",
}

VOCAB = {
    "predicates": [
        {"id": "inhibits"}, {"id": "decreases"}, {"id": "equals"},
        {"id": "other"}, {"id": "increases"}, {"id": "activates"},
        {"id": "correlates_with"}, {"id": "causes"}, {"id": "caused_by"},
        {"id": "is_part_of"}, {"id": "has_part"}, {"id": "expresses"},
        {"id": "expressed_by"}, {"id": "binds"}, {"id": "bound_by"}, {"id": "predicts"},
    ]
}


def build_assertions(paras):
    """模拟 agent 的语义填充结果（含 3 条故意注入缺陷的断言用于测试质检）。"""
    def ev(quote):
        return [{"quote": quote, "page": None, "paragraph_id": None, "char_start": None,
                 "char_end": None, "support": "full", "relation_to_assertion": "direct", "note": None}]

    return [
        {"id": "a001", "text": "化合物 A 在 25 °C 下抑制酶 B 的活性。",
         "subject": {"name": "化合物 A", "type": "compound"},
         "relation": {"predicate": "inhibits", "direction": "down"},
         "object": {"name": "酶 B", "type": "protein"},
         "qualifiers": {"temperature": "25 °C"},
         "polarity": "positive", "modality": "observed", "asserted_by": "author",
         "evidence": ev("化合物 A 在 25 °C 下抑制酶 B 的活性"),
         "provenance_ref": "src-001",
         "confidence": {"level": "high", "basis": "explicit-statement"}},

        {"id": "a002", "text": "化合物 A 使反应速率下降 40%。",
         "subject": {"name": "化合物 A", "type": "compound"},
         "relation": {"predicate": "decreases", "direction": "down"},
         "object": {"name": "反应速率", "type": "metric", "unit": "%"},
         "qualifiers": {"temperature": "25 °C"},
         "polarity": "positive", "modality": "observed", "asserted_by": "author",
         "evidence": ev("化合物 A 在 25 °C 下抑制酶 B 的活性，使反应速率下降 40%"),
         "provenance_ref": "src-001",
         "confidence": {"level": "high", "basis": "explicit-statement"}},

        {"id": "a003", "text": "化合物 A 对酶 C 没有明显影响。",
         "subject": {"name": "化合物 A", "type": "compound"},
         "relation": {"predicate": "other", "free_text": "no significant effect", "direction": "none"},
         "object": {"name": "酶 C", "type": "protein"},
         "qualifiers": {},
         "polarity": "negative", "modality": "observed", "asserted_by": "author",
         "evidence": ev("化合物 A 对酶 C 没有明显影响"),
         "provenance_ref": "src-001",
         "confidence": {"level": "high", "basis": "explicit-statement"}},

        {"id": "a004", "text": "在 pH 7.4 条件下，化合物 A 的半衰期为 12.5 h。",
         "subject": {"name": "化合物 A", "type": "compound"},
         "relation": {"predicate": "equals", "direction": "none"},
         "object": {"name": "半衰期", "type": "metric", "value": 12.5, "unit": "h"},
         "qualifiers": {"ph": "7.4"},
         "polarity": "positive", "modality": "observed", "asserted_by": "author",
         "evidence": ev("在 pH 7.4 条件下，化合物 A 的半衰期为 12.5 h"),
         "provenance_ref": "src-001",
         "confidence": {"level": "high", "basis": "explicit-statement"}},

        {"id": "a005", "text": "化合物 A 可能通过变构机制发挥作用，并且抑制所有酶。",
         "subject": {"name": "化合物 A", "type": "compound"},
         "relation": {"predicate": "inhibits", "direction": "down"},
         "object": {"name": "所有酶", "type": "protein"},
         "qualifiers": {},
         "polarity": "positive", "modality": "hypothesized", "asserted_by": "reader",
         "evidence": ev("可能通过变构机制发挥作用"),
         "provenance_ref": "src-001",
         "confidence": {"level": "low", "basis": "cross-section-inference"}},

        {"id": "a006", "text": "化合物 A 在 25 °C 下抑制酶 B 的活性。",
         "subject": {"name": "化合物 A", "type": "compound"},
         "relation": {"predicate": "inhibits", "direction": "down"},
         "object": {"name": "酶 B", "type": "protein"},
         "qualifiers": {"temperature": "25 °C"},
         "polarity": "positive", "modality": "observed", "asserted_by": "author",
         "evidence": ev("化合物 A 在 25 °C 下抑制酶 B 的活性"),
         "provenance_ref": "src-001",
         "confidence": {"level": "high", "basis": "explicit-statement"}},

        {"id": "a007", "text": "化合物 A 使反应速率增加 40%。",
         "subject": {"name": "化合物 A", "type": "compound"},
         "relation": {"predicate": "increases", "direction": "up"},
         "object": {"name": "反应速率", "type": "metric"},
         "qualifiers": {},
         "polarity": "positive", "modality": "observed", "asserted_by": "author",
         "evidence": ev("使反应速率下降 40%"),
         "provenance_ref": "src-001",
         "confidence": {"level": "high", "basis": "explicit-statement"}},
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args()
    work = args.workdir or tempfile.mkdtemp(prefix="nanopub-selftest-")
    os.makedirs(work, exist_ok=True)

    results = []

    def check(name, cond, detail=""):
        results.append({"name": name, "pass": bool(cond), "detail": detail})

    # 1) 段落切分
    paras = paragraphs_from_pages(PAGES)
    check("paragraph_count", len(paras) == 3, f"paragraphs={len(paras)}")
    check("paragraph_ids", [p["id"] for p in paras] == ["p1b1", "p1b2", "p2b1"],
          str([p["id"] for p in paras]))
    check("paragraph_offsets", all(PAGES[0]["text"][p["char_start"]:p["char_end"]] == p["text"]
                                  for p in paras if p["page"] == 1) and
          all(PAGES[1]["text"][p["char_start"]:p["char_end"]] == p["text"]
              for p in paras if p["page"] == 2), "char offsets 与页面文本切片一致")

    # 2) 句切分
    sents = split_sentences(paras[0]["text"])
    check("sentence_split", len(sents) == 2, f"sentences={len(sents)}")
    check("sentence_offsets", all(paras[0]["text"][s:e] == t for s, e, t in sents), "句偏移正确")

    # 3) 候选切分
    cands = candidates_from_paragraphs(paras)
    check("candidate_count", len(cands) >= 4, f"candidates={len(cands)}")
    check("candidate_offsets", all(c["text"] in paras_by_id(paras, c["paragraph_id"])["text"]
                                   for c in cands), "候选文本来自所属段落")
    check("candidate_page", all(c["page"] == paras_by_id(paras, c["paragraph_id"])["page"]
                                for c in cands), "候选页码正确")

    # 4) 引文定位
    span = locate_quote(paras[0]["text"], "化合物 A 在 25 °C 下抑制酶 B 的活性")
    check("quote_locate", span is not None and
          norm_ws(paras[0]["text"][span[0]:span[1]]) == "化合物 A 在 25 °C 下抑制酶 B 的活性",
          str(span))
    check("quote_whitespace_tolerant",
          locate_quote(paras[0]["text"], "化合物A在25°C下抑制酶B的活性") is not None,
          "空白差异仍可定位")
    check("quote_not_invented", locate_quote(paras[0]["text"], "化合物 D 抑制酶 Z 的活性") is None,
          "编造引文必须定位失败")

    # 5) 最小证据片段
    ms = minimal_span(paras[0]["text"], ["化合物 A", "下降 40%"])
    check("minimal_span", ms is not None and (ms[1] - ms[0]) < len(paras[0]["text"]),
          f"span={ms} 全长={len(paras[0]['text'])}")
    check("minimal_span_missing_token", minimal_span(paras[0]["text"], ["化合物 A", "下降 99%"]) is None,
          "缺 token 时返回 None")

    # 6) 证据绑定 + 机械核验
    assertions = build_assertions(paras)
    for a in assertions:
        for ev in a["evidence"]:
            quotespan = None
            for p in paras:
                s = locate_quote(p["text"], ev["quote"])
                if s:
                    ev.update({"page": p["page"], "paragraph_id": p["id"],
                               "char_start": s[0], "char_end": s[1]})
                    quotespan = s
                    break
    check("bind_all", all(ev.get("paragraph_id") for a in assertions for ev in a["evidence"]),
          "全部引文绑定到段落")
    check("bind_offsets_consistent",
          all(same_text(paras_by_id(paras, ev["paragraph_id"])["text"][ev["char_start"]:ev["char_end"]],
                        ev["quote"]) for a in assertions for ev in a["evidence"]),
          "偏移切出的文本与引文一致")

    verified = 0
    for a in assertions:
        for ev in a["evidence"]:
            p = paras_by_id(paras, ev["paragraph_id"])
            if same_text(p["text"][ev["char_start"]:ev["char_end"]], ev["quote"]):
                verified += 1
    check("verify_mechanically", verified == sum(len(a["evidence"]) for a in assertions),
          f"verified={verified}")

    # 7) 质量检查
    vocab_map = {p["id"]: p for p in VOCAB["predicates"]}
    summary = qc_assertion_set(assertions, paras, SOURCE, vocab_map)
    by_id = {a["id"]: a["qc"] for a in assertions}
    check("qc_clean_pass", by_id["a001"]["status"] == "pass" and by_id["a002"]["status"] == "pass"
          and by_id["a003"]["status"] == "pass" and by_id["a004"]["status"] == "pass",
          str({k: by_id[k]["status"] for k in ("a001", "a002", "a003", "a004")}))
    check("qc_broad_flag", any(i["code"] == "Q001" for i in by_id["a005"]["issues"]),
          "多关系/全称量词被标记")
    check("qc_evidence_insufficient", any(i["code"] == "Q004" for i in by_id["a005"]["issues"]),
          "证据缺主体被标记")
    check("qc_modality_flag", any(i["code"] == "Q012" for i in by_id["a005"]["issues"]),
          "推论性断言用直接证据被标记")
    check("qc_direction_mismatch", any(i["code"] == "Q007" for i in by_id["a007"]["issues"]),
          "关系方向与证据相反被标记")
    check("qc_duplicate", any(i["code"] == "Q013" for i in by_id["a006"]["issues"]),
          "重复断言被标记")
    check("qc_summary_counts", summary["assertion_count"] == len(assertions) and
          summary["status_counts"]["fail"] >= 2, str(summary["status_counts"]))

    # 8) 来源缺失检测
    bare = dict(SOURCE)
    bare.pop("authors")
    bad = qc_assertion_set([dict(assertions[0])], paras, bare, vocab_map)
    check("qc_provenance_missing", bad["issue_counts"].get("Q006", 0) >= 1,
          "缺 authors 触发 Q006")

    # 9) 导出形态 + 确定性
    csv_text = to_csv(assertions)
    check("csv_header", csv_text.splitlines()[0].count(",") == 18, "CSV 19 列")
    check("csv_rows", len(csv_text.splitlines()) == len(assertions) + 1,
          f"rows={len(csv_text.splitlines())}")
    trig = to_trig(assertions, SOURCE)
    check("trig_prefixes", "nanopub.org/nschema" in trig and "prov:" in trig, "TriG 前缀齐全")
    check("trig_assertions", all(f"sub:{a['id']}" in trig for a in assertions), "每条断言进入 assertion 子图")
    check("trig_evidence", all(f"sub:ev_{a['id']}" in trig for a in assertions), "证据节点齐全")
    check("determinism", to_trig(assertions, SOURCE) == trig and to_csv(assertions) == csv_text,
          "重复序列化逐字节一致")

    # 10) 落盘
    cl.write_json(os.path.join(work, "paragraphs.json"),
                  {"page_count": 2, "text_sha256": "fixture", "paragraphs": paras})
    cl.write_json(os.path.join(work, "assertions.json"),
                  {"case_id": "selftest", "status": "partial", "source": SOURCE,
                   "assertions": assertions, "qc_summary": summary})
    check("write_outputs", os.path.exists(os.path.join(work, "paragraphs.json")) and
          os.path.exists(os.path.join(work, "assertions.json")), work)

    # 11) 官方 result.json 契约（results.nanopubs / quality_flags）
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "serres", os.path.join(ROOT, "scripts", "serialize_result.py"))
    sr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sr)

    pub_src = {"source_id": SOURCE["source_id"], "authors": SOURCE["authors"],
               "year": SOURCE["year"], "doi": SOURCE.get("doi"), "version": SOURCE.get("version")}
    pubs = [sr.to_nanopub(a, pub_src) for a in assertions]
    check("nanopub_required_keys",
          all({"assertion", "subject", "predicate", "object", "conditions", "evidence",
               "source_metadata", "confidence", "status"} == set(p) for p in pubs))
    check("nanopub_evidence_bindable",
          all(p["evidence"]["source_id"] and p["evidence"]["locator"]
              and p["evidence"]["quote"] and p["evidence"]["evidence_type"] for p in pubs))
    check("nanopub_source_metadata_complete",
          all(p["source_metadata"]["authors"] and p["source_metadata"]["year"]
              and p["source_metadata"]["version"] and p["source_metadata"]["doi_or_id"] for p in pubs))
    check("nanopub_status_mapped", all(p["status"] in ("checked", "flagged", "rejected", "unverified")
                                       for p in pubs), str({p["status"] for p in pubs}))
    check("quality_flags_is_list", isinstance(sr.to_flags(assertions), list))

    draft = {"case_id": "selftest", "status": "partial", "source": pub_src,
             "assertions": assertions, "change_log": [{"step": "export", "detail": "selftest"}]}
    result = {"case_id": "selftest", "task_id": "product-arena-09-0e8befd4",
              "status": "success", "results": {"nanopubs": pubs, "quality_flags": []},
              "sources": [{"source_id": SOURCE["source_id"], "locator": "paragraph p1b1",
                           "quote": assertions[0]["evidence"][0]["quote"], "note": "x"}],
              "uncertainty": [{"item": "x", "reason": "y", "action_required": "z"}],
              "changes": [{"step": "1", "action": "a", "note": "n"}],
              "artifacts": [], "metadata": {"skill_name": "nanopublication-extraction"}}
    check("contract_accepts_good_result", sr.validate(result) == [], str(sr.validate(result))[:200])
    broken = json.loads(json.dumps(result))
    broken["results"]["nanopubs"][0]["evidence"]["quote"] = ""
    check("contract_rejects_empty_quote", bool(sr.validate(broken)))
    broken2 = json.loads(json.dumps(result))
    broken2["results"]["extra_key"] = 1
    check("contract_rejects_extra_results_key", any("契约外字段" in e for e in sr.validate(broken2)))

    failed = [r for r in results if not r["pass"]]
    print(json.dumps({"total": len(results), "passed": len(results) - len(failed),
                      "failed": len(failed), "results": results}, ensure_ascii=False, indent=1))
    return 0 if not failed else 1


def paras_by_id(paras, pid):
    return next(p for p in paras if p["id"] == pid)


if __name__ == "__main__":
    sys.exit(main())
