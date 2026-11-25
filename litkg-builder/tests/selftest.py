#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""litkg 自测：24 项 fixture 断言，全部基于合成语料，不涉及任何真实论文。"""
import json
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import kg  # noqa: E402

FAIL, PASS = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="litkg_selftest_"))
    corpus = kg.discover(ROOT / "examples" / "corpus.synthetic.json")
    ent, rel = kg.load_vocab()

    check("two_papers_loaded", len(corpus["papers"]) == 2, str(len(corpus["papers"])))
    check("source_ids_distinct", [p["source_id"] for p in corpus["papers"]] == ["P1", "P2"])
    check("paragraph_ids_preserved",
          corpus["papers"][0]["paragraphs"][0]["paragraph_id"] == "P1-p001",
          corpus["papers"][0]["paragraphs"][0]["paragraph_id"])
    check("no_synthetic_pids", all(not x["pid_synthetic"] for p in corpus["papers"] for x in p["paragraphs"]))
    check("authors_not_crossed",
          corpus["papers"][0]["title"].startswith("Synthetic Study Alpha")
          and corpus["papers"][1]["title"].startswith("Synthetic Study Beta"))

    text = "Cu-doped TiO2 samples were prepared by impregnation at 25 °C."
    check("locate_exact", kg.locate("Cu-doped TiO2", text) is not None)
    check("locate_whitespace_tolerant", kg.locate("Cu-doped  TiO2   samples", text) is not None)
    check("locate_squashed", kg.locate("Cu-dopedTiO2samples", text) is not None)
    check("locate_absent_none", kg.locate("N-doped ZnO", text) is None)
    check("sentence_split", len(kg.sentences(text)) >= 1)

    cands = [c for p in corpus["papers"] for c in kg.extract_candidates(p)]
    types = {c["type"] for c in cands}
    check("candidates_have_method_material_metric", {"method", "material", "metric"} <= types, str(sorted(types)))
    check("candidate_quotes_in_source",
          all(kg.locate(c["quote"][:100], c["sentence"]) is not None for c in cands))

    graph = kg.build_graph(corpus, ent, rel)
    qcres = kg.qc(graph, corpus)
    check("graph_has_nodes", len(graph["nodes"]) > 0, str(len(graph["nodes"])))
    check("graph_has_edges", len(graph["edges"]) > 0, str(len(graph["edges"])))
    check("every_node_has_evidence", all(n["evidence"] for n in graph["nodes"]))
    check("node_quotes_locatable", all(
        kg.locate(ev["quote"][:100], next(x["text"] for p in corpus["papers"] for x in p["paragraphs"]
                                          if x["paragraph_id"] == ev["paragraph_id"])) is not None
        for n in graph["nodes"] for ev in n["evidence"]))
    check("edge_endpoints_exist",
          all(e["subject"] in {n["id"] for n in graph["nodes"]} and
              e["object"] in {n["id"] for n in graph["nodes"]} for e in graph["edges"]))
    check("no_cross_paper_instance_merge",
          all(len(n["source_ids"]) < 2 for n in graph["nodes"]
              if n["type"] in ("material", "dataset", "model", "metric", "condition")))
    check("merge_records_have_basis", all(m["basis"] and m["rule"] for m in graph["merges"]))
    check("has_not_merged_instance",
          any(m["decision"] == "not_merged" for m in graph["merges"]))

    outperf = [e for e in graph["edges"] if e["type"] == "outperforms"]
    check("outperforms_direction",
          bool(outperf) and all(e["direction"] == "subject_to_object" for e in outperf),
          str([(e["subject_label"], e["object_label"], e["conditions"]) for e in outperf]))
    check("outperforms_condition_recorded", any(e["conditions"] for e in outperf),
          str([e["conditions"] for e in outperf]))
    check("conflict_kept_separate",
          bool(graph["conflicts"]) and all(c["resolution"] in ("kept_separate", "kept_both") for c in graph["conflicts"]))
    check("qc_no_fail", qcres["summary"]["fail"] == 0, str(qcres["summary"]))

    queries = kg.run_queries(graph, qcres, kg.pick_query_terms(graph))
    check("at_least_three_queries", len(queries) >= 3, str(len(queries)))
    check("queries_report_undetermined", all("undetermined" in q for q in queries))

    files = kg.export_all(graph, tmp)
    check("exports_written", all(Path(v).exists() for v in files.values()), str(files))
    ET.parse(tmp / "kg.graphml")
    check("graphml_parses", True)
    check("cypher_has_merge", "MERGE" in (tmp / "kg.cypher").read_text(encoding="utf-8"))

    r = kg.build(ROOT / "examples" / "corpus.synthetic.json", tmp / "run", "demo")
    rj = json.loads((tmp / "run" / "result.json").read_text(encoding="utf-8"))
    check("result_has_contract_fields",
          {"case_id", "task_id", "status", "results", "sources", "uncertainty",
           "changes", "artifacts", "metadata"} <= set(rj))
    check("result_status_enum", rj["status"] in ("success", "partial", "undetermined", "refused"), rj["status"])
    check("result_sources_locator", all(s["locator_type"] == "paragraph" and "paragraph " in s["locator"]
                                        and s["quote"] for s in rj["sources"]) and bool(rj["sources"]))
    check("result_uncertainty_objects",
          all({"item", "reason", "action_required"} <= set(u) for u in rj["uncertainty"]))
    check("deterministic_ids", [n["id"] for n in rj["results"]["graph"]["nodes"]] == [n["id"] for n in graph["nodes"]])

    tampered = json.loads(json.dumps(graph))
    tampered["nodes"][0]["evidence"][0]["quote"] = "这段引文在原段落中并不存在 zzz"
    q2 = kg.qc(tampered, corpus)
    check("qc_detects_bad_quote", any(i["code"] == "K003" for i in q2["issues"]))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} assertions passed")
    if FAIL:
        print("failed:", FAIL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
