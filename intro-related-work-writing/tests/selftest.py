#!/usr/bin/env python3
"""intro-related-work-writing 自测：24 项断言，覆盖证据层与契约层，含负例。"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import introkit as ik  # noqa: E402

LIB = r"""
@article{smith2020,
  author = {Smith, John and Tanaka, Ken},
  title = {A benchmark dataset for gas uptake prediction},
  journal = {Journal of Materials Data}, year = {2020},
  doi = {10.1000/a},
  abstract = {We define the task of uptake prediction with a benchmark dataset. However, these models are limited to single-component adsorption.}
}
@article{li2021,
  author = {Li, Mei},
  title = {Graph neural network models for adsorption isotherms},
  journal = {Computational Materials Science}, year = {2021},
  abstract = {We propose a graph neural network model. Under humid conditions it is stable. However, these models are limited to single-component adsorption.}
}
@article{zhao2019,
  author = {Zhao, Lin},
  title = {High-throughput experiments for multicomponent separation},
  journal = {Separation Science}, year = {2019},
  abstract = {High-throughput experiments measure selectivity for 40 frameworks. The evaluation metric is selectivity at 1 bar.}
}
@article{kim2024,
  author = {Kim, Dae},
  title = {Generative flow models for framework discovery},
  journal = {Nature Materials Letters}, year = {2024},
  abstract = {A generative flow model proposes structures. The approach cannot enforce synthesizability.}
}
"""

RIS = """TY  - JOUR
ID  - ris1
AU  - Park, Min
TI  - A model for flexible frameworks
PY  - 2022
JO  - Physical Chemistry Letters
AB  - A model of flexibility. However, it is limited to single-component systems.
ER  -
"""

PASSED = []


def run(name, fn):
    try:
        ok = bool(fn())
        err = ""
    except Exception as exc:  # noqa: BLE001
        ok, err = False, "%s: %s" % (type(exc).__name__, exc)
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + err) if err else ""))
    PASSED.append(ok)


# ------------------------------------------------------------------ 证据层
recs = ik.parse_bib(LIB)


def t_parse_count():
    return len(recs) == 4 and len({r["key"] for r in recs}) == 4


def t_authors():
    return recs[0]["authors"][0] == "Smith, John" and len(recs[0]["authors"]) == 2


def t_year():
    return recs[0]["year"] == "2020" and recs[3]["year"] == "2024"


def t_ris():
    r = ik.parse_ris(RIS)
    return len(r) == 1 and r[0]["key"] == "ris1" and r[0]["limitation"].startswith("However")


def t_conclusion():
    return recs[0]["conclusion"].startswith("We define the task")


def t_limitation():
    return "single-component" in recs[0]["limitation"] and "single-component" in recs[1]["limitation"]


def t_conditions():
    return "humid" in recs[1]["conditions"].lower()


groups = ik.group_records(recs)


def t_groups_dims():
    return len(groups["groups"]) >= 2


def t_groups_fields():
    return all({"group", "dimension", "works", "terms"} <= set(g) for g in groups["groups"])


def t_works_fields():
    return all({"ref", "conclusion", "conditions", "limitation"} <= set(w)
               for g in groups["groups"] for w in g["works"])


def t_every_record_placed():
    placed = {w["ref"] for g in groups["groups"] for w in g["works"]}
    return placed == {r["key"] for r in recs}


gap = ik.derive_gap(groups)


def t_gap_supported():
    return gap["strength"] == "supported" and gap["support"] >= 2


def t_gap_evidence_refs():
    return all(ref in gap["evidence"] for ref in gap["refs"])


def t_gap_no_evidence_case():
    g2 = ik.derive_gap({"groups": [{"group": "m", "dimension": "method",
                                    "works": [{"ref": "k", "limitation": ""}]}], "unclassified": []})
    return g2["strength"] == "no_evidence" and g2["gap"] == ""


def t_gap_single_insufficient():
    g3 = ik.derive_gap({"groups": [{"group": "m", "dimension": "method",
                                    "works": [{"ref": "k", "limitation": "only single-component"}]}],
                        "unclassified": []})
    return g3["strength"] == "insufficient" and g3["support"] == 1


# ------------------------------------------------------------------ 覆盖层
TEXT = ("多组分分离依赖单组分外推[smith2020]。图网络在 8 个框架上训练[li2021]。"
        "本文模型在 12 个框架上取得 MAE 0.08。生成模型无法保证可合成性[kim2024]。"
        "已有工作未处理该设定[ghost2025]。")
cov = ik.coverage_audit(TEXT, recs)


def t_coverage_uncited():
    return len(cov["uncited_sentences"]) == 1 and "0.08" in cov["uncited_sentences"][0]["text"]


def t_coverage_cited_not_flagged():
    return not any("单组分外推" in s["text"] for s in cov["uncited_sentences"])


def t_coverage_unknown():
    return cov["unknown_citations"] == ["ghost2025"]


def t_coverage_recent():
    return "kim2024" in cov["recent_works"] and "smith2020" not in cov["recent_works"]


def t_coverage_missing_key():
    return cov["missing"], len(cov["missing"]) >= 1


# ------------------------------------------------------------------ 贡献层
paper = {"figures": [{"id": "1", "caption": "Schematic of the dual-network framework"}],
         "tables": [{"id": "2", "caption": "Comparison of selectivity across 12 frameworks"}],
         "results": [{"id": "R1", "name": "selectivity MAE", "value": "0.08", "unit": "-"}]}
contribs = [{"claim": "A dual-network framework for adsorption prediction", "evidence_locator": "fig:1"},
            {"claim": "Selectivity MAE of 0.08 on held-out frameworks", "evidence_locator": "res:R1"},
            {"claim": "Outperforms all baselines", "evidence_locator": "tab:9"}]
cres = ik.contrib_audit(contribs, paper, recs)


def t_contrib_ok():
    return cres[0]["status"] == "ok" and cres[1]["status"] == "ok"


def t_contrib_missing_locator():
    return cres[2]["status"] == "locator_missing"


def t_contrib_ref_locator():
    r = ik.contrib_audit([{"claim": "benchmark dataset for uptake prediction", "evidence_locator": "ref:smith2020"}],
                         paper, recs)
    return r[0]["status"] == "ok"


# ------------------------------------------------------------------ 汇总与契约
def t_assemble_shape():
    case = {"case_id": "T-01", "task_id": "t"}
    d = ik.assemble(recs, groups, gap, cres, cov, case)
    return (d["case_id"] == "T-01" and set(d["results"]) == {"background", "related_work", "gap",
                                                             "contributions", "citations_coverage"}
            and len(d["sources"]) == len(recs))


def t_assemble_uncertainty():
    d = ik.assemble(recs, groups, gap, cres, cov, {"case_id": "T-01"})
    items = " ".join(u["item"] for u in d["uncertainty"])
    return "无引用" in items and "库外" in items


def main():
    for fn in (t_parse_count, t_authors, t_year, t_ris, t_conclusion, t_limitation, t_conditions,
               t_groups_dims, t_groups_fields, t_works_fields, t_every_record_placed,
               t_gap_supported, t_gap_evidence_refs, t_gap_no_evidence_case, t_gap_single_insufficient,
               t_coverage_uncited, t_coverage_cited_not_flagged, t_coverage_unknown,
               t_coverage_recent, t_coverage_missing_key, t_contrib_ok, t_contrib_missing_locator,
               t_contrib_ref_locator, t_assemble_shape, t_assemble_uncertainty):
        run(fn.__name__, fn)

    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        (td / "case.json").write_text(json.dumps({"case_id": "T-CASE-01", "task_id": "t"}), encoding="utf-8")
        draft = ik.assemble(recs, groups, gap, cres, cov, {"case_id": "T-CASE-01", "task_id": "t"})
        (td / "draft.json").write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                            "--input", str(td / "case.json"), "--draft", str(td / "draft.json"),
                            "--out", str(td / "out.json")], capture_output=True, text=True)
        run("serializer_runs", lambda: p.returncode == 0)
        doc = json.loads((td / "out.json").read_text(encoding="utf-8")) if p.returncode == 0 else {}
        run("contract_nine_fields", lambda: set(doc) == {
            "case_id", "task_id", "status", "results", "sources", "uncertainty",
            "changes", "artifacts", "metadata"})
        run("case_id_passthrough", lambda: doc.get("case_id") == "T-CASE-01" and doc["task_id"] == "t")

        bad = dict(draft)
        r = dict(draft["results"])
        r["background"] = {"thread": "x"}
        bad["results"] = r
        (td / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        p2 = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                             "--input", str(td / "case.json"), "--draft", str(td / "bad.json"),
                             "--out", str(td / "out2.json")], capture_output=True, text=True)
        run("rejects_missing_background_field", lambda: p2.returncode == 1 and "background" in p2.stderr)

        bad2 = dict(draft)
        bad2["status"] = "done"
        (td / "bad2.json").write_text(json.dumps(bad2), encoding="utf-8")
        p3 = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                             "--input", str(td / "case.json"), "--draft", str(td / "bad2.json"),
                             "--out", str(td / "out3.json")], capture_output=True, text=True)
        run("rejects_bad_status", lambda: p3.returncode == 1 and "status" in p3.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        out = td / "draft.json"
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "introkit.py"), "assemble",
                            "--case", str(ROOT / "examples" / "case.json"),
                            "--library", str(ROOT / "examples" / "library.bib"),
                            "--intro", str(ROOT / "examples" / "intro.md"),
                            "--out", str(out)], capture_output=True, text=True)
        run("cli_assemble_runs", lambda: p.returncode == 0 and out.exists())

    print("%d/%d assertions passed" % (sum(PASSED), len(PASSED)))
    return 0 if all(PASSED) else 1


if __name__ == "__main__":
    sys.exit(main())
