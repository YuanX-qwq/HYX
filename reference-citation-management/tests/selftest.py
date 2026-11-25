#!/usr/bin/env python3
"""自测：解析 / 渲染 / 编号重排 / 去重 / 核验 / 论断匹配 / 契约序列化。"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import cite  # noqa: E402

BIB = """
@article{a1, author = {Wang, Li and Zhang, Hui and Chen, Ming}, title = {Doping effects on catalysis},
 journal = {Journal of Catalysis}, year = {2021}, volume = {398}, number = {2}, pages = {112--121},
 doi = {10.1016/j.jcat.2021.03.014}}
@article{a1pre, author = {Wang, Li}, title = {Doping effects on catalysis},
 journal = {arXiv preprint arXiv:2101.04567}, year = {2021}, doi = {10.48550/arXiv.2101.04567}}
@article{a1dup, author = {Wang, Li}, title = {Doping Effects on Catalysis},
 journal = {Journal of Catalysis}, year = {2021}, volume = {398}, pages = {112--121},
 doi = {10.1016/J.JCAT.2021.03.014}}
@article{b1, author = {Zhao, Yan}, title = {Doping effects on catalysis},
 journal = {Other Journal}, year = {2018}, pages = {1--9}, doi = {10.1016/j.other.2018.01.001}}
"""

RIS = """TY  - JOUR
AU  - Wang, Li
TI  - Doping effects on catalysis
JO  - Journal of Catalysis
PY  - 2021
VL  - 398
IS  - 2
SP  - 112
EP  - 121
DO  - 10.1016/j.jcat.2021.03.014
ER  -
"""

ENDNOTE = """%0 Journal Article
%A Wang, Li
%T Doping effects on catalysis
%J Journal of Catalysis
%D 2021
%V 398
%N 2
%P 112-121
%R 10.1016/j.jcat.2021.03.014
"""

CNKI = "王立, 张辉. 掺杂对氧化物催化性能的影响[J]. 催化学报, 2021, 42(3): 112-121. DOI: 10.1016/j.jcat.2021.03.014."

MS = "掺杂提升催化活性[2]，产率 42%[1]。X 射线衍射表明晶格常数减小[3]。该结论未见报道[7]。"

RESULT_KEYS = ("citations", "reference_list", "dedup", "consistency_checks", "format_notes")
DRAFT = {
    "citations": [{"claim_span": "x[1]", "ref_keys": ["k1"],
                   "placement": "sentence-end", "style": "GB/T 7714-2015"}],
    "reference_list": [{"key": "k1", "metadata": "m", "doi": "10.1/x",
                        "source": "k1", "status": "verified_shape"}],
    "dedup": [{"merged_keys": "k1, k2", "basis": "R-DOI", "kept_key": "k1"}],
    "consistency_checks": [{"claim": "c", "ref_key": "k1", "match": "strong", "evidence": "e"}],
    "format_notes": {"target_style": "GB/T 7714-2015", "converted_from": "bibtex",
                     "kept_fields": ["DOI"]},
}

PASSED = []


def run(name, fn):
    try:
        ok = bool(fn())
        err = ""
    except Exception as exc:  # noqa: BLE001
        ok, err = False, "%s: %s" % (type(exc).__name__, exc)
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + err) if err else ""))
    PASSED.append(ok)


def t_format():
    return (cite.detect_format(BIB) == "bibtex" and cite.detect_format(RIS) == "ris"
            and cite.detect_format(ENDNOTE) == "endnote" and cite.detect_format(CNKI) == "cnki")


def t_bib_fields():
    r = cite.parse_library(BIB)[0]
    return (r["authors"][0] == "Wang, Li" and r["volume"] == "398"
            and r["pages"] == "112-121" and r["doi"] == "10.1016/j.jcat.2021.03.014")


def t_ris():
    r = cite.parse_library(RIS)[0]
    return r["pages"] == "112-121" and r["issue"] == "2"


def t_endnote():
    return cite.parse_library(ENDNOTE)[0]["title"] == "Doping effects on catalysis"


def t_cnki():
    r = cite.parse_library(CNKI)[0]
    return r["volume"] == "42" and r["issue"] == "3" and r["pages"] == "112-121"


def t_gbt():
    s = cite.render(cite.parse_library(BIB)[0], "gbt")
    return "[J]. " in s and "398(2): 112-121" in s and s.startswith("WANG L")


def t_apa():
    return "https://doi.org/10.1016/j.jcat.2021.03.014" in cite.render(cite.parse_library(BIB)[0], "apa")


def t_etal():
    return cite.gbt_authors(["A, B", "C, D", "E, F", "G, H"], False).endswith("et al.")


def t_renumber():
    text = cite.renumber("甲[3]乙[1]丙[2]", 3)[0]
    return text.startswith("甲[1]") and "丙[3]" in text


def t_compress():
    return cite.compress([1, 2, 3, 5]) == "1-3,5"


def t_dangling():
    return any(i["kind"] == "dangling_intext" for i in cite.renumber(MS, 3)[2])


def t_uncited():
    return any(i["kind"] == "uncited_reference" for i in cite.renumber("甲[1]", 3)[2])


def t_nonnumeric():
    return any(i["kind"] == "non_numeric_marker"
               for i in cite.renumber("结果一致（Wang, 2021）。", 2)[2])


def t_dedup_merge():
    merged, groups, _ = cite.dedup_records(cite.parse_library(BIB)[0:3])
    return len(merged) == 1 and len(merged[0]["merged_from"]) == 3


def t_false_merge():
    a = {"authors": ["Wang, Li"], "title": "Doping effects on catalysis", "year": "2021"}
    b = {"authors": ["Zhao, Yan"], "title": "Doping effects on catalysis", "year": "2018"}
    return cite.merge_basis(a, b) is None


def t_preprint():
    merged, _, _ = cite.dedup_records(cite.parse_library(BIB)[0:2])
    return merged[0]["container"] == "Journal of Catalysis"


def t_doi_flag():
    flags = cite.verify_records([{"key": "x", "doi": "doi:10.9999/fake.1",
                                  "title": "placeholder results", "year": "2022",
                                  "authors": ["S, J"]}])[0]["flags"]
    return any(f["kind"] == "doi_malformed" for f in flags)


def t_placeholder():
    flags = cite.verify_records([{"key": "y", "title": "placeholder results on doping",
                                  "year": "2022", "authors": ["S, J"]}])[0]["flags"]
    return any(f["kind"] == "placeholder_title" for f in flags)


def t_strong():
    verdict, _ = cite.claim_match(
        "Doping improves catalytic activity in oxide catalysts",
        {"title": "Doping-induced lattice contraction and catalytic activity in oxide catalysts"})
    return verdict == "strong"


def t_mismatch():
    verdict, _ = cite.claim_match("The sample colour changed to blue",
                                  {"title": "Hydrothermal stability of doped oxides"})
    return verdict == "mismatch"


def t_bridge():
    return cite.claim_match("X 射线衍射表明晶格常数减小",
                            {"title": "X-ray diffraction study of lattice constants"})[1] > 0


def t_audit_keys():
    res = cite.audit(MS, cite.parse_library(BIB))
    need = set(RESULT_KEYS) | {"citation_gaps", "renumber_issues", "manuscript_revised"}
    return need <= set(res)


def t_gap():
    ms = "本研究考察掺杂影响。此外，掺杂样品的比表面积达到 210 m2/g，明显高于未掺杂样品。"
    return len(cite.audit(ms, cite.parse_library(BIB))["citation_gaps"]) >= 1


def main():
    for fn in (t_format, t_bib_fields, t_ris, t_endnote, t_cnki, t_gbt, t_apa, t_etal,
               t_renumber, t_compress, t_dangling, t_uncited, t_nonnumeric,
               t_dedup_merge, t_false_merge, t_preprint, t_doi_flag, t_placeholder,
               t_strong, t_mismatch, t_bridge, t_audit_keys, t_gap):
        run(fn.__name__, fn)

    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        (td / "case.json").write_text(json.dumps({"case_id": "T-CASE-01", "task_id": "t"}),
                                      encoding="utf-8")
        (td / "draft.json").write_text(json.dumps(DRAFT, ensure_ascii=False), encoding="utf-8")
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                            "--input", str(td / "case.json"), "--draft", str(td / "draft.json"),
                            "--out", str(td / "out.json")], capture_output=True, text=True)
        doc = json.loads((td / "out.json").read_text(encoding="utf-8")) if p.returncode == 0 else {}
        run("serializer_runs", lambda: p.returncode == 0)
        run("contract_nine_fields", lambda: set(doc) == {
            "case_id", "task_id", "status", "results", "sources", "uncertainty",
            "changes", "artifacts", "metadata"})
        run("case_id_passthrough", lambda: doc.get("case_id") == "T-CASE-01" and doc["task_id"] == "t")
        run("ref_keys_flattened", lambda: doc["results"]["citations"][0]["ref_keys"] == "k1")

        bad = dict(DRAFT)
        bad["reference_list"] = [{"key": "k1", "metadata": "m"}]
        (td / "bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        p2 = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                             "--input", str(td / "case.json"), "--draft", str(td / "bad.json"),
                             "--out", str(td / "out2.json")], capture_output=True, text=True)
        run("rejects_missing_field", lambda: p2.returncode == 1 and "缺" in p2.stderr)

    print("%d/%d assertions passed" % (sum(PASSED), len(PASSED)))
    return 0 if all(PASSED) else 1


if __name__ == "__main__":
    sys.exit(main())
