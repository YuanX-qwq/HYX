#!/usr/bin/env python3
"""生成示例产物：稿件、文献库、case、草稿与契约 result.json（全部标注为示例）。"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))

import case_data as d  # noqa: E402
import cite  # noqa: E402

(HERE / "manuscript.md").write_text(d.manuscript, encoding="utf-8")
(HERE / "library.bib").write_text(d.library_bib.lstrip(), encoding="utf-8")
(HERE / "case.json").write_text(json.dumps(d.case, ensure_ascii=False, indent=2), encoding="utf-8")

recs = cite.parse_library(d.library_bib)
res = cite.audit(d.manuscript, recs, style=d.case["target_style"])

uncertainty = [{"item": "正文引用 [6] 无对应条目", "reason": "文献库只有 %d 条记录" % len(res["reference_list"]),
                "action_required": "补录条目或改编号，需作者确认"}]
for v in res["verify"]:
    if v["status"] != "verified_shape":
        uncertainty.append({"item": "条目 %s 待核验" % v["key"],
                            "reason": "; ".join(f["detail"] for f in v["flags"]),
                            "action_required": "按 DOI 解析或数据库检索核验后再引用"})
for g in res["citation_gaps"]:
    uncertainty.append({"item": "缺引用的论断：%s" % g["sentence"][:40],
                        "reason": g["reason"], "action_required": "确认是否需补引并选择文献"})

draft = {
    "status": "partial",
    "results": {k: res[k] for k in ("citations", "reference_list", "dedup",
                                    "consistency_checks", "format_notes")},
    "sources": [
        {"source_id": "manuscript", "locator": "paragraph 1", "locator_type": "paragraph",
         "quote": "在 25 °C 条件下，掺杂样品的产率提升到 42%", "note": "正文断言原文"},
        {"source_id": "library.bib", "locator": "entry wang2021doping", "locator_type": "record",
         "quote": "doi = {10.1016/j.jcat.2021.03.014}", "note": "DOI 比对依据"},
        {"source_id": "library.bib", "locator": "entry fake2022ghost", "locator_type": "record",
         "quote": "doi = {doi:10.9999/fake.2022.001}", "note": "DOI 形态非法，判为编造候选"},
    ],
    "uncertainty": uncertainty,
    "changes": [
        {"step": "1", "action": "读取 manuscript.md 与 library.bib", "note": "确认目标规范与文献库格式 bibtex"},
        {"step": "2", "action": "解析并渲染 %d 条文献" % len(res["reference_list"]), "note": "GB/T 7714-2015 字段顺序"},
        {"step": "3", "action": "去重合并 %d 组" % len(res["dedup"]), "note": "DOI 相同 / 预印本与正式版同题"},
        {"step": "4", "action": "按正文首次出现重排编号", "note": "编号连续化并检出 dangling 与未被引条目"},
        {"step": "5", "action": "逐句核验论断与文献", "note": "%d 条判定，weak/mismatch 已标注" % len(res["consistency_checks"])},
    ],
    "artifacts": [],
    "metadata": {"model": "doubao-work-agent", "runtime": "python3.13", "example_only": True},
}

(HERE / "draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
(HERE / "audit.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
(HERE / "manuscript_revised.md").write_text(res["manuscript_revised"], encoding="utf-8")

subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                "--input", str(HERE / "case.json"), "--draft", str(HERE / "draft.json"),
                "--out", str(HERE / "example_result.json"),
                "--skill-name", "reference-citation-management",
                "--runtime", "python3.13"], check=True)
print("examples:", sorted(p.name for p in HERE.iterdir() if p.is_file()))
print("stats:", json.dumps(res["stats"], ensure_ascii=False))
