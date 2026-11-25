#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""academic-language-polishing 自测：22 项断言，全部基于合成文本。"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
import polish_check as pc  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))


ORIG = ("We use 5 ml catalyst suspension in 25 °C to test the activity, and the yield is 42%. "
        "The result prove that the doping is always effective [12]. See Fig. 2 for the profile.")
REV = ("We used 5 mL of the catalyst suspension at 25 °C to test the activity, and the yield was 42%. "
       "The results suggest that doping is effective [12]. See Fig. 2 for the profile.")
GOOD_REVS = [
    {"span": "s1", "original": "We use 5 ml catalyst suspension", "revised": "We used 5 mL of the catalyst suspension",
     "type": "grammar", "reason": "时态/单位书写", "preserves_meaning": True},
    {"span": "s1", "original": "in 25 °C", "revised": "at 25 °C", "type": "collocation",
     "reason": "温度介词", "preserves_meaning": True},
    {"span": "s2", "original": "The result prove that the doping is always effective",
     "revised": "The results suggest that doping is effective", "type": "register",
     "reason": "去除绝对化", "preserves_meaning": True},
]


def main():
    rep = pc.check_text(ORIG, REV, [], GOOD_REVS)
    check("clean_pair_not_fail", rep["verdict"] != "FAIL", rep["verdict"])
    check("numbers_preserved", rep["counts"]["numbers"] >= 4)
    check("unit_case_tolerated", not any(i["kind"] == "unit" for i in rep["issues"]))
    check("citations_preserved", not any(i["kind"] == "citation" for i in rep["issues"]))
    check("xref_preserved", not any(i["kind"] == "xref" for i in rep["issues"]))
    check("revision_records_valid", not any(i["kind"] == "revision" and i["severity"] == "fail" for i in rep["issues"]))

    bad = pc.check_text(ORIG, REV.replace("42%", "43%"), [], GOOD_REVS)
    check("number_change_detected", any(i["kind"] == "number" and i["severity"] == "fail" for i in bad["issues"]), str(bad["issues"])[:160])

    bad2 = pc.check_text(ORIG, REV.replace("[12]", "[13]"), [], GOOD_REVS)
    check("citation_change_detected", any(i["kind"] == "citation" and i["severity"] == "fail" for i in bad2["issues"]))

    bad3 = pc.check_text(ORIG, REV.replace("See Fig. 2", "See Fig. 3"), [], GOOD_REVS)
    check("xref_change_detected", any(i["kind"] == "xref" and i["severity"] == "fail" for i in bad3["issues"]))

    neg_orig = "The sample was not stable after 10 h."
    neg_rev = "The sample was stable after 10 h."
    bad4 = pc.check_text(neg_orig, neg_rev, [], [])
    check("negation_drop_detected", any(i["kind"] == "negation" and i["severity"] == "fail" for i in bad4["issues"]))

    hedged = "The additive may improve the yield."
    strengthened = "The additive proves that it improves the yield."
    bad5 = pc.check_text(hedged, strengthened, [], [])
    check("strengthening_detected", any(i["kind"] == "hedge" and i["severity"] == "fail" for i in bad5["issues"]))

    weakened = pc.check_text("The additive may improve the yield.", "The additive improves the yield.", [], [])
    check("hedge_drop_warned", any(i["kind"] == "hedge" and i["severity"] == "warn" for i in weakened["issues"]))

    cond = pc.check_text("If the pH is below 5, the yield drops.", "The yield drops.", [], [])
    check("condition_drop_detected", any(i["kind"] == "condition" and i["severity"] == "fail" for i in cond["issues"]))

    quant = pc.check_text("All samples showed the same phase.", "Some samples showed the same phase.", [], [])
    check("quantifier_change_detected", any(i["kind"] == "quantifier" and i["severity"] == "fail" for i in quant["issues"]))

    bad_rev = [{"span": "s1", "original": "这句话不在原文里", "revised": "x", "type": "grammar",
                "reason": "r", "preserves_meaning": True}]
    badrec = pc.check_text(ORIG, REV, [], bad_rev)
    check("revision_original_must_exist", any(i["kind"] == "revision" and "不在原文" in i["detail"] for i in badrec["issues"]))

    miss = [dict(GOOD_REVS[0])]
    miss[0].pop("preserves_meaning")
    badrec2 = pc.check_text(ORIG, REV, [], miss)
    check("revision_requires_preserves_meaning", any("preserves_meaning" in i["detail"] for i in badrec2["issues"]))

    gl = [{"concept": "catalyst", "canonical": "catalyst", "variants": ["catalyser"]}]
    inconsistent = pc.check_text("catalyst", "catalyser", gl, [])
    check("glossary_variant_warned", any(i["kind"] == "term" for i in inconsistent["issues"]))

    noabbr = pc.check_text("We used XRD to check the phase.", "We used XRD to check the phase.", [], [])
    check("abbr_expansion_warned", any(i["kind"] == "abbr" for i in noabbr["issues"]))

    tmp = Path(tempfile.mkdtemp(prefix="polish_selftest_"))
    (tmp / "o.txt").write_text(ORIG, encoding="utf-8")
    (tmp / "r.txt").write_text(REV, encoding="utf-8")
    (tmp / "revs.json").write_text(json.dumps(GOOD_REVS), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "polish_check.py"),
                        "--original", str(tmp / "o.txt"), "--revised", str(tmp / "r.txt"),
                        "--revisions", str(tmp / "revs.json"), "--out", str(tmp / "check.json")],
                       capture_output=True, text=True)
    check("cli_check_runs", r.returncode == 0 and (tmp / "check.json").exists(), r.stderr[-120:])

    case = tmp / "case.json"
    case.write_text(json.dumps({"case_id": "T-001", "task_id": "product-arena-02-7051d92d"}), encoding="utf-8")
    draft = tmp / "draft.json"
    draft.write_text(json.dumps({
        "status": "success",
        "results": {"revised_text": REV, "revisions": GOOD_REVS, "glossary": [], "register_notes": ["journal"],
                    "unresolved": []},
        "sources": [{"source_id": "s", "locator": "p1", "locator_type": "paragraph", "quote": "We use 5 ml", "note": "n"}],
        "uncertainty": [{"item": "x", "reason": "y", "action_required": "z"}],
        "changes": [{"step": "1", "action": "a", "note": "b"}],
        "artifacts": []}), encoding="utf-8")
    out = tmp / "result.json"
    r2 = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                         "--case", str(case), "--draft", str(draft), "--out", str(out)],
                        capture_output=True, text=True)
    check("serializer_runs", r2.returncode == 0 and out.exists(), r2.stderr[-160:])
    res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    check("contract_top_fields",
          set(res) == {"case_id", "task_id", "status", "results", "sources", "uncertainty",
                       "changes", "artifacts", "metadata"})
    check("case_id_passthrough", res.get("case_id") == "T-001")
    check("status_enum", res.get("status") in {"success", "partial", "undetermined", "refused"})

    bad_status = tmp / "bad.json"
    bad_status.write_text(json.dumps({"status": "done", "results": {"revised_text": REV, "revisions": GOOD_REVS,
                                                                    "glossary": [], "register_notes": [], "unresolved": []},
                                      "sources": [], "uncertainty": [], "changes": [], "artifacts": []}), encoding="utf-8")
    r3 = subprocess.run([sys.executable, str(ROOT / "scripts" / "serialize_result.py"),
                         "--case", str(case), "--draft", str(bad_status), "--out", str(tmp / "x.json")],
                        capture_output=True, text=True)
    check("serializer_rejects_bad_status", r3.returncode == 1 and "status 非法" in r3.stderr)

    print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} assertions passed")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
