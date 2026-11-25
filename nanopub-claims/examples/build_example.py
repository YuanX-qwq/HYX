#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_example.py — 从合成文档生成 20 条断言样例（示例，synthetic）。

用途：给出"输入 -> 断言 -> 证据 -> 质检 -> 三态导出"的完整可运行示例，
供他人复用时对照；**不是任何正式案例的结果**。

运行：
  python3 examples/build_example.py
产出（都在 examples/ 下）：
  sample_pages.json           合成页面文本（2 页 / 10 段 / 20 句）
  sample_assertions.json      20 条断言（含证据绑定与质检结论）
  output/assertion_set.example.json / assertions.example.csv / nanopub.example.trig
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from claimlib import (locate_quote, paragraphs_from_pages, qc_assertion_set,  # noqa: E402
                      read_json, read_json as _rj, sha256_text, to_csv, to_trig, write_json)  # noqa: F401

SOURCE = {
    "source_id": "sha256:synthetic-example-0001",
    "title": "Synthetic Study of Potassium Sensing in Strain K-12 (example)",
    "authors": ["A. Example", "B. Example"],
    "year": 2026,
    "venue": "Synthetic Journal (example)",
    "doi": None,
    "version": "example-v1",
    "retrieved_from": "examples/build_example.py (synthetic, not a real paper)",
    "file_sha256": None,
    "license": "CC0-1.0",
}

# 20 句：每句一个可判断的关系；subject / object 都是句中逐字出现的字符串
SPECS = [
    # (sentence, subject, subject_type, predicate, free_text, object, object_type, value, unit, qualifiers)
    ("Strain K-12 reached a maximum growth rate of 0.42 per hour at 30 °C.",
     "Strain K-12", "organism", "equals", None, "maximum growth rate", "metric", 0.42, "per hour", {"temperature": "30 °C"}),
    ("At 37 °C, the maximum growth rate of strain K-12 dropped to 0.28 per hour.",
     "strain K-12", "organism", "decreases", None, "maximum growth rate", "metric", 0.28, "per hour", {"temperature": "37 °C"}),
    ("Ammonium supplementation raised the biomass yield of strain K-12 by 18 percent.",
     "Ammonium supplementation", "condition", "increases", None, "biomass yield", "metric", None, None, {}),
    ("Nitrate supplementation left the biomass yield of strain K-12 unchanged.",
     "Nitrate supplementation", "condition", "other", "left unchanged", "biomass yield", "metric", None, None, {}),
    ("Strain K-12 tolerated NaCl concentrations up to 4.5 percent (w/v).",
     "Strain K-12", "organism", "other", "tolerated up to", "NaCl concentrations", "condition", 4.5, "percent (w/v)", {}),
    ("Above 4.5 percent NaCl, growth of strain K-12 ceased completely.",
     "strain K-12", "organism", "decreases", None, "growth", "process", None, None, {"nacl": "above 4.5 percent"}),
    ("The genome of strain K-12 carries 4318 protein-coding genes.",
     "genome", "other", "has_part", None, "protein-coding genes", "other", 4318, "genes", {}),
    ("Gene kdpA showed 2.1-fold higher expression under low potassium.",
     "Gene kdpA", "gene", "increases", None, "expression", "process", 2.1, "fold", {"condition": "low potassium"}),
    ("Low potassium conditions activated the kdp operon within 15 minutes.",
     "Low potassium conditions", "condition", "activates", None, "kdp operon", "gene", None, None, {"duration": "15 minutes"}),
    ("The kdp operon encodes three subunits, KdpA, KdpB and KdpC.",
     "kdp operon", "gene", "has_part", None, "three subunits", "protein", None, None, {}),
    ("KdpA binds potassium with a dissociation constant of 12 micromolar.",
     "KdpA", "protein", "binds", None, "potassium", "compound", None, None, {"kd": "12 micromolar"}),
    ("Deletion of kdpA reduced growth under low potassium by 34 percent.",
     "Deletion of kdpA", "process", "decreases", None, "growth", "process", 34, "percent", {"condition": "low potassium"}),
    ("Complementation with wild-type kdpA restored growth to 96 percent of the control level.",
     "Complementation with wild-type kdpA", "process", "other", "restored", "growth", "process", 96, "percent of the control", {}),
    ("Mutant strain K-12 delta-kdpA produced colonies 40 percent smaller than the wild type.",
     "Mutant strain K-12 delta-kdpA", "organism", "decreases", None, "colonies", "other", 40, "percent", {}),
    ("Transcription of kdpA peaked at 0.8 transcripts per cell during stationary phase.",
     "Transcription of kdpA", "process", "other", "peaked at", "transcripts", "metric", 0.8, "per cell", {"phase": "stationary"}),
    ("Potassium starvation increased kdpA promoter activity 5.6-fold.",
     "Potassium starvation", "condition", "increases", None, "kdpA promoter activity", "metric", 5.6, "fold", {}),
    ("The kdp operon is conserved across 27 tested isolates.",
     "kdp operon", "gene", "other", "is conserved across", "27 tested isolates", "dataset", None, None, {}),
    ("Isolates lacking the kdp operon showed 22 percent slower growth at low potassium.",
     "Isolates lacking the kdp operon", "organism", "decreases", None, "growth", "process", 22, "percent", {"condition": "low potassium"}),
    ("The measured potassium affinity of KdpA was 12 micromolar in three independent assays.",
     "potassium affinity of KdpA", "metric", "equals", None, "12 micromolar", "metric", 12, "micromolar", {"assays": "3"}),
    ("Adding 50 millimolar potassium fully reversed the starvation response within 10 minutes.",
     "potassium", "compound", "other", "fully reversed", "starvation response", "process", 50, "millimolar", {"duration": "10 minutes"}),
]


def build_pages():
    """10 段 / 每段 2 句 / 2 页。"""
    sents = [s[0] for s in SPECS]
    blocks = [" ".join(sents[i:i + 2]) for i in range(0, len(sents), 2)]
    page1 = "\n\n".join(blocks[:5])
    page2 = "\n\n".join(blocks[5:])
    return [{"page": 1, "text": page1}, {"page": 2, "text": page2}]


def main():
    pages = build_pages()
    write_json(os.path.join(HERE, "sample_pages.json"), pages)
    paras = paragraphs_from_pages(pages)

    assertions = []
    for i, spec in enumerate(SPECS, 1):
        (sentence, s_name, s_type, pred, free, o_name, o_type, value, unit, quals) = spec
        ev = {"quote": sentence, "page": None, "paragraph_id": None, "char_start": None,
              "char_end": None, "bbox": None, "support": "full",
              "relation_to_assertion": "direct", "note": None}
        # 绑定到段落与字符偏移
        for p in paras:
            span = locate_quote(p["text"], sentence)
            if span:
                ev.update({"page": p["page"], "paragraph_id": p["id"],
                           "char_start": span[0], "char_end": span[1]})
                break
        obj = {"name": o_name, "type": o_type}
        if value is not None:
            obj["value"] = value
        if unit is not None:
            obj["unit"] = unit
        rel = {"predicate": pred, "direction": "none"}
        if free:
            rel["free_text"] = free
        assertions.append({
            "id": f"a{i:03d}",
            "text": sentence,
            "subject": {"name": s_name, "type": s_type},
            "relation": rel,
            "object": obj,
            "qualifiers": quals,
            "polarity": "positive",
            "modality": "observed",
            "asserted_by": "author",
            "evidence": [ev],
            "provenance_ref": SOURCE["source_id"],
            "confidence": {"level": "high", "basis": "explicit-statement", "note": "synthetic example"},
        })

    vocab = read_json(os.path.join(ROOT, "vocab", "predicates.json"))
    vocab_map = {p["id"]: p for p in vocab["predicates"]}
    summary = qc_assertion_set(assertions, paras, SOURCE, vocab_map)

    payload = {
        "schema_version": "nanopub-claims/1.0",
        "case_id": "example-synthetic-001",
        "status": "success",
        "source": SOURCE,
        "document": {"page_count": 2, "paragraph_ids": [p["id"] for p in paras],
                     "text_sha256": sha256_text("".join(p["text"] for p in paras))},
        "assertions": assertions,
        "unreported": [],
        "uncertainty": [],
        "qc_summary": summary,
        "change_log": [{"step": "build_example", "detail": "synthetic example generated deterministically"}],
    }
    write_json(os.path.join(HERE, "sample_assertions.json"), payload)

    out_dir = os.path.join(HERE, "output")
    os.makedirs(out_dir, exist_ok=True)
    write_json(os.path.join(out_dir, "assertion_set.example.json"), payload)
    with open(os.path.join(out_dir, "assertions.example.csv"), "w", encoding="utf-8", newline="") as fh:
        fh.write(to_csv(assertions))
    with open(os.path.join(out_dir, "nanopub.example.trig"), "w", encoding="utf-8") as fh:
        fh.write(to_trig(assertions, SOURCE))

    print(json.dumps({"assertions": len(assertions), "paragraphs": len(paras),
                      "qc": summary["status_counts"], "issue_counts": summary["issue_counts"],
                      "out_dir": out_dir}, ensure_ascii=False))
    return 0 if summary["status_counts"]["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
