#!/usr/bin/env python3
"""latex-writing-compilation 自测（仅标准库，不依赖 TeX 引擎）。

覆盖：结构扫描、宏包缺失、标签/引用/文献对应、宽表估算、三线表、浮动体、
补丁改稿、模板必填项、log 解析、序列化契约的语义校验。
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

S = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(S / "scripts"))
import latexkit as lk  # noqa: E402

DRAFT = S / "examples" / "draft"
PATCHES = S / "examples" / "patches.json"
TPL = S / "templates" / "template_required.json"
CASE = S / "examples" / "case.json"
TMP = Path(tempfile.mkdtemp(prefix="lxkit-"))


def t(name, fn):
    try:
        ok = bool(fn())
    except Exception as e:  # noqa: BLE001
        ok = False
        print("  exception: %r" % e)
    print(("PASS " if ok else "FAIL ") + name)
    return ok


def main():
    results = []
    info = lk.scan(DRAFT)
    lint_res = lk.lint(DRAFT)
    codes = [d["code"] for d in lint_res["diagnostics"]]

    results.append(t("scan_main_file", lambda: info["main"] == "main.tex"))
    results.append(t("scan_documentclass", lambda: info["documentclass"] == "article"))
    results.append(t("scan_sources_count", lambda: len([s for s in info["sources"] if s["role"] == "section"]) == 5))
    results.append(t("scan_bib_role", lambda: any(s["path"] == "refs.bib" and s["role"] == "bibliography"
                                                 for s in info["sources"])))
    results.append(t("scan_input_graph", lambda: len(info["graph"].get("main.tex", [])) == 5))
    results.append(t("scan_packages_amsmath", lambda: "amsmath" in info["packages"]))
    results.append(t("scan_missing_booktabs", lambda: "booktabs" in info["missing_packages"]))
    results.append(t("scan_missing_only_booktabs", lambda: info["missing_packages"] == ["booktabs"]))
    results.append(t("scan_env_pkg_tikz_ok", lambda: "tikz" in info["packages"]))
    results.append(t("scan_bib_keys", lambda: sorted(info["bib_keys"]) == ["liu2021polymer", "wang2020scaffold", "zhang2022gnn"]))
    results.append(t("scan_cites_include_bad_key", lambda: "zhang2023gnn" in {c["key"] for c in info["cites"]}))

    results.append(t("lint_has_errors", lambda: lint_res["counts"]["error"] >= 4))
    results.append(t("lint_missing_package_code", lambda: "MISSING_PACKAGE" in codes))
    results.append(t("lint_package_fix_names_pkg", lambda: any("booktabs" in d["fix"] for d in lint_res["diagnostics"]
                                                             if d["code"] == "MISSING_PACKAGE")))
    results.append(t("lint_undefined_eqref", lambda: any(d["code"] == "UNDEFINED_REF" and "eq:attention" in d["message"]
                                                       for d in lint_res["diagnostics"])))
    results.append(t("lint_undefined_tableref", lambda: any(d["code"] == "UNDEFINED_REF" and "tab:metrics" in d["message"]
                                                          for d in lint_res["diagnostics"])))
    results.append(t("lint_missing_bib_key", lambda: any(d["code"] == "MISSING_BIB_KEY" and "zhang2023gnn" in d["message"]
                                                       for d in lint_res["diagnostics"])))
    results.append(t("lint_wide_table", lambda: any(d["code"] == "WIDE_TABLE" and d["severity"] == "error"
                                                   for d in lint_res["diagnostics"])))
    results.append(t("lint_float_placement", lambda: "FLOAT_PLACEMENT" in codes))
    results.append(t("lint_float_not_referenced", lambda: any(d["code"] == "FLOAT_NOT_REFERENCED" and "fig:pipeline" in d["message"]
                                                             for d in lint_res["diagnostics"])))
    results.append(t("lint_booktabs_present_no_warn", lambda: "NOT_THREE_LINE" not in codes))
    results.append(t("lint_no_uncited_bib", lambda: "UNCITED_BIB" not in codes))
    results.append(t("lint_every_diag_has_fix", lambda: all(d["fix"] for d in lint_res["diagnostics"])))

    table_block = (DRAFT / "sections" / "experiments.tex").read_text(encoding="utf-8")
    tb = lk.parse_table(table_block[table_block.index("\\begin{table}"):])
    results.append(t("parse_table_cols", lambda: tb["n_cols"] == 7 and tb["booktabs"] is True))
    results.append(t("estimate_width_over_textwidth", lambda: lk.estimate_width_pt(
        table_block[table_block.index("\\begin{table}"):], tb) > 453.0))

    fixed = TMP / "fixed"
    app = lk.apply_patches(DRAFT, PATCHES, fixed)
    results.append(t("apply_all_patches", lambda: app["ok"] and len(app["applied"]) == 8 and not app["failed"]))
    ftxt = (fixed / "main.tex").read_text(encoding="utf-8")
    results.append(t("apply_added_booktabs", lambda: "\\usepackage{booktabs}" in ftxt))
    results.append(t("apply_added_tabularx", lambda: "\\usepackage{tabularx}" in ftxt))
    exp = (fixed / "sections" / "experiments.tex").read_text(encoding="utf-8")
    results.append(t("apply_table_to_tabularx", lambda: "\\begin{tabularx}" in exp and "\\end{tabularx}" in exp))
    results.append(t("apply_ref_fixed", lambda: "tab:metrics" not in exp and "tab:main-res" in exp))
    results.append(t("apply_cite_fixed", lambda: "zhang2023gnn" not in
                     (fixed / "sections" / "method.tex").read_text(encoding="utf-8")))
    results.append(t("apply_eqref_fixed", lambda: "eq:attention" not in
                     (fixed / "sections" / "intro.tex").read_text(encoding="utf-8")))
    results.append(t("apply_float_tbp", lambda: "\\begin{figure}[tbp]" in
                     (fixed / "sections" / "method.tex").read_text(encoding="utf-8")))
    results.append(t("apply_added_tikz_lib", lambda: "\\usetikzlibrary{positioning}" in ftxt))

    lint_fixed = lk.lint(fixed)
    results.append(t("fixed_lint_zero_errors", lambda: lint_fixed["counts"]["error"] == 0))
    results.append(t("fixed_no_missing_package", lambda: not any(d["code"] == "MISSING_PACKAGE"
                                                                for d in lint_fixed["diagnostics"])))
    results.append(t("fixed_no_wide_table", lambda: not any(d["code"] == "WIDE_TABLE"
                                                           for d in lint_fixed["diagnostics"])))
    results.append(t("fixed_no_float_placement", lambda: not any(d["code"] == "FLOAT_PLACEMENT"
                                                                for d in lint_fixed["diagnostics"])))

    chk = lk.check(fixed, str(TPL))
    results.append(t("check_required_fields_all", lambda: len(chk["required_fields"]) == 8 and not chk["missing_fields"]))
    results.append(t("check_layout_ok_static", lambda: chk["layout_ok"] is True))
    chk_bad = lk.check(DRAFT, str(TPL))
    results.append(t("check_draft_not_layout_ok", lambda: chk_bad["layout_ok"] is False
                     and any("error" in n for n in chk_bad["notes"])))

    log = ("./main.tex:3: Undefined control sequence.\n"
           "l.3 \\toprule\n"
           "! LaTeX Error: File `foo.sty' not found.\n"
           "Overfull \\hbox (18.7pt too wide) in alignment at lines 21--24\n"
           "Reference `tab:metrics' on page 3 undefined on input line 12.\n")
    errors, over = lk.parse_log(log, DRAFT, "main.tex")
    results.append(t("parse_log_errors", lambda: errors and errors[0]["file"] == "main.tex"
                     and errors[0]["line"] == 3 and errors[0]["fix"]))
    results.append(t("parse_log_overfull", lambda: over and abs(over[0]["too_wide_pt"] - 18.7) < 1e-6
                     and over[0]["line"] == 21))
    results.append(t("fix_rule_package", lambda: "宏包" in lk.fix_for("Undefined control sequence.", "", [], 0)))
    results.append(t("fix_rule_tikz_lib", lambda: "positioning" in lk.fix_for(
        "Package PGF Math Error: Unknown function `of' (in 'of in')", "", [], 0)))
    results.append(t("fix_rule_citation", lambda: "文献键" in lk.fix_for("Citation `a' undefined", "", [], 0)))

    b = lk.build(fixed, "pdflatex_does_not_exist")
    results.append(t("build_degrades_honestly", lambda: b["status"] == "engine_unavailable" and b["passes"] == 0
                     and b["bibtex_runs"] == 0 and b["converged"] is False))

    # 序列化契约
    case = json.loads(CASE.read_text(encoding="utf-8"))
    seq = S / "scripts" / "serialize_result.py"
    struct = lk.scan(fixed)
    res_results = lk.assemble(str(CASE), struct, lint_fixed, b,
                              json.loads(TPL.read_text(encoding="utf-8")))
    draft_obj = {"case_id": case["case_id"], "task_id": case["task_id"], "status": "partial",
                 "results": res_results, "sources": [{"source_id": "draft", "locator": "sections/experiments.tex:31",
                                                      "locator_type": "line", "quote": "Table~\\ref{tab:metrics}",
                                                      "note": "direct evidence"}],
                 "uncertainty": [{"item": "compile evidence", "reason": "no TeX engine on this host",
                                  "action_required": "rerun on an image with TeX Live"}],
                 "changes": [{"step": "1", "action": "lint+apply+build", "note": "7 patches"}],
                 "artifacts": []}
    dpath = TMP / "draft.json"
    dpath.write_text(json.dumps(draft_obj, ensure_ascii=False), encoding="utf-8")
    outp = TMP / "result.json"
    r = subprocess.run([sys.executable, str(seq), "--input", str(CASE), "--draft", str(dpath),
                        "--out", str(outp), "--skill-name", "latex-writing-compilation"],
                       capture_output=True, text=True)
    key = ["case_id", "task_id", "status", "results", "sources", "uncertainty", "changes", "artifacts", "metadata"]
    results.append(t("serialize_ok", lambda: r.returncode == 0 and outp.exists()))
    results.append(t("serialize_nine_fields", lambda: all(k in json.loads(outp.read_text(encoding="utf-8")) for k in key)))
    results.append(t("serialize_case_id_preserved", lambda: json.loads(outp.read_text(encoding="utf-8"))["case_id"] == case["case_id"]))

    bad = dict(draft_obj)
    bad["status"] = "success"
    bad["results"] = dict(res_results)
    bad["results"]["build"] = dict(res_results["build"])
    bad["results"]["build"]["status"] = "engine_unavailable"
    dpath2 = TMP / "bad.json"
    dpath2.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    r2 = subprocess.run([sys.executable, str(seq), "--input", str(CASE), "--draft", str(dpath2),
                         "--out", str(TMP / "bad_result.json")], capture_output=True, text=True)
    results.append(t("serialize_rejects_fake_success", lambda: r2.returncode != 0 and "build.status" in r2.stderr))

    bad2 = dict(draft_obj)
    bad2["case_id"] = "REWRITTEN-ID"
    dpath3 = TMP / "bad2.json"
    dpath3.write_text(json.dumps(bad2, ensure_ascii=False), encoding="utf-8")
    r3 = subprocess.run([sys.executable, str(seq), "--input", str(CASE), "--draft", str(dpath3),
                         "--out", str(TMP / "bad2_result.json")], capture_output=True, text=True)
    results.append(t("serialize_rejects_case_id_rewrite", lambda: r3.returncode != 0 and "case_id" in r3.stderr))

    bad3 = json.loads(json.dumps(draft_obj))
    bad3["sources"] = [{"source_id": "x", "locator": "y", "quote": ""}]
    dpath4 = TMP / "bad3.json"
    dpath4.write_text(json.dumps(bad3, ensure_ascii=False), encoding="utf-8")
    r4 = subprocess.run([sys.executable, str(seq), "--input", str(CASE), "--draft", str(dpath4),
                         "--out", str(TMP / "bad3_result.json")], capture_output=True, text=True)
    results.append(t("serialize_rejects_empty_quote", lambda: r4.returncode != 0 and "quote" in r4.stderr))

    total = len(results)
    print("%d/%d assertions passed" % (sum(results), total))
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
