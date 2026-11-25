#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py -- deterministic pipeline tests, including negative cases.

Runs the whole chain on a synthetic paper (text backend) and asserts that every
verifier rule actually fires when it should:

  T01 segment.py builds stable paragraph ids and kinds
  T02 paragraph reconstruction joins a hyphenated word across a line break
  T03 sentence splitter keeps abbreviations together
  T04 glossary lock accepts a clean table
  T05 glossary lock rejects duplicate term_en
  T06 glossary lock rejects two terms sharing one Chinese name
  T07 a faithful translation passes verify.py with FAIL=0
  T08 dropped number is reported as FAIL (numbers)
  T09 lost negation is reported as FAIL (negation)
  T10 term drift is reported as FAIL (glossary)
  T11 missing paragraph is reported by coverage
  T12 changed citation marker is reported as FAIL (citations)
  T13 changed figure number is reported as FAIL (cross_refs)
  T14 copied source is reported as FAIL (untranslated)
  T15 assemble.py marks an incomplete bundle partial and lists the missing pid
  T16 assemble.py marks a clean bundle success
  T17 numeric normalisation keeps 2,000 and 2.5 distinct
  T18 unit token check does not fire on words containing "cal"

Usage:
  python3 tests/selftest.py --workdir /tmp/selftest            # synthetic only
  python3 tests/selftest.py --workdir /tmp/selftest --real-pdf paper.pdf
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)

import layout  # noqa: E402
import segment  # noqa: E402
import verify  # noqa: E402

FAILED = []
PASSED = []


def check(name, cond, detail=""):
    if cond:
        PASSED.append(name)
        print("PASS %s %s" % (name, detail))
    else:
        FAILED.append(name)
        print("FAIL %s %s" % (name, detail))


def run(cmd, expect=0):
    p = subprocess.run([sys.executable, "-X", "utf8"] + cmd,
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != expect:
        print(p.stdout[-2000:])
        print(p.stderr[-2000:])
    return p


PAPER = """Machine learning phases of matter

Neural networks can identify phases and phase transitions in condensed matter systems. A standard feed-forward neural network is trained on raw state configurations sampled with Monte Carlo.

Condensed matter physics studies the collective behavior of complex assemblies of electrons [1]. The state space grows exponentially with the number of particles, so numerical simulations are typically employed [2, 3]. This framework does not provide the same quantitative understanding as a direct measurement of the order parameter.

We consider a two-dimensional square ice Hamiltonian with N = 2 x 16 x 16 spins. The network distinguishes the states with 99% accuracy, as shown in Figure 3(A). The neural network is trained on a test set of 1 x 104 configurations at T = 0 and T = 30.
"""

GOOD = [
    {"pid": "P0001", "zh": "物质的机器学习相", "notes": "标题"},
    {"pid": "P0002", "zh": "神经网络能够识别凝聚态体系中的相与相变。标准前馈神经网络在由蒙特卡洛采样的原始状态构型上训练。",
     "notes": "abstract"},
    {"pid": "P0003", "zh": "凝聚态物理研究电子等复杂集合体的集体行为[1]。状态空间随粒子数呈指数增长，因此通常采用数值模拟[2, 3]。该框架并不能提供与直接测量序参量同等的定量理解。",
     "notes": "body"},
    {"pid": "P0004", "zh": "我们考虑一个含 N = 2 x 16 x 16 个自旋的二维方冰哈密顿量。该网络以 99% 的准确率区分这些态，如图 3(A) 所示。该神经网络在 T = 0 与 T = 30 下由 1 x 104 个构型组成的测试集上训练。",
     "notes": "body"},
]

GLOSSARY = """term_en,term_zh,category,variants,note
neural network,神经网络,method,,
order parameter,序参量,concept,,
square ice,方冰,model,,
"""


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--real-pdf", default=None)
    a = ap.parse_args(argv)
    W = os.path.abspath(a.workdir)
    if os.path.isdir(W):
        shutil.rmtree(W)
    os.makedirs(W)
    paper = os.path.join(W, "paper.txt")
    with open(paper, "w", encoding="utf-8") as f:
        f.write(PAPER)

    # ---------------------------------------------------------------- T01/T04
    seg = os.path.join(W, "segments.json")
    p = run([os.path.join(SCRIPTS, "segment.py"), "--pdf", paper, "--out", seg,
             "--md", os.path.join(W, "segments.md"),
             "--todo", os.path.join(W, "todo.jsonl"), "--scope", os.path.join(W, "scope.json")])
    doc = json.load(open(seg, encoding="utf-8")) if p.returncode == 0 else {"segments": []}
    pids = [s["pid"] for s in doc["segments"]]
    check("T01-segment", p.returncode == 0 and pids == ["P0001", "P0002", "P0003", "P0004"],
          "pids=%s" % pids)
    kinds = [s["kind"] for s in doc["segments"]]
    check("T01-kinds", kinds[:2] == ["title", "abstract"], "kinds=%s" % kinds)

    # ---------------------------------------------------------------- T02/T03
    wl = {"dimensionality", "condensed", "matter"}
    joined = layout._join_line("the curse of dimension-", "ality is real", wl, 12.0)
    check("T02-hyphen-join", "dimensionality" in joined and "dimension-" not in joined, joined)
    kept = layout._join_line("condensed-", "matter physics", {"condensed-matter"}, 12.0)
    check("T02-hyphen-keep", "condensed- matter" not in kept, kept)
    sents = segment.split_sentences("We use Eq. (2), e.g. the first one. Then we stop.")
    check("T03-sentences", len(sents) == 2, "n=%d" % len(sents))

    # ---------------------------------------------------------------- T04/T05/T06
    gp = os.path.join(W, "glossary.csv")
    with open(gp, "w", encoding="utf-8") as f:
        f.write(GLOSSARY)
    lock = os.path.join(W, "glossary.json")
    p = run([os.path.join(SCRIPTS, "gloss.py"), "lock", "--glossary", gp,
             "--segments", seg, "--out", lock])
    lg = json.load(open(lock, encoding="utf-8")) if p.returncode == 0 else {}
    check("T04-lock", p.returncode == 0 and lg.get("locked") is True and len(lg["terms"]) == 3)

    dup = os.path.join(W, "glossary.dup.csv")
    with open(dup, "w", encoding="utf-8") as f:
        f.write(GLOSSARY + "neural network,神经网,method,,\n")
    p = run([os.path.join(SCRIPTS, "gloss.py"), "lock", "--glossary", dup,
             "--segments", seg, "--out", os.path.join(W, "g2.json")], expect=1)
    check("T05-lock-duplicate", p.returncode == 1)

    same = os.path.join(W, "glossary.same.csv")
    with open(same, "w", encoding="utf-8") as f:
        f.write(GLOSSARY + "phase transition,神经网络,concept,,\n")
    p = run([os.path.join(SCRIPTS, "gloss.py"), "lock", "--glossary", same,
             "--segments", seg, "--out", os.path.join(W, "g3.json")], expect=1)
    check("T06-lock-shared-zh", p.returncode == 1)

    # ---------------------------------------------------------------- T07
    tr = os.path.join(W, "translations.jsonl")
    write_jsonl(tr, GOOD)
    rep = os.path.join(W, "verify.json")
    p = run([os.path.join(SCRIPTS, "verify.py"), "--segments", seg, "--translations", tr,
             "--glossary", lock, "--scope", os.path.join(W, "scope.json"), "--out", rep])
    r = json.load(open(rep, encoding="utf-8"))
    check("T07-clean-pass", p.returncode == 0 and r["metrics"]["fail_count"] == 0
          and r["coverage"]["rate"] == 1.0, json.dumps(r["issue_counts"], ensure_ascii=False))

    def mutate(fn, name, check_name, severity="fail"):
        rows = [dict(x) for x in GOOD]
        fn(rows)
        path = os.path.join(W, name + ".jsonl")
        write_jsonl(path, rows)
        out = os.path.join(W, name + ".verify.json")
        run([os.path.join(SCRIPTS, "verify.py"), "--segments", seg, "--translations", path,
             "--glossary", lock, "--scope", os.path.join(W, "scope.json"), "--out", out],
            expect=1)
        rr = json.load(open(out, encoding="utf-8"))
        hit = [i for i in rr["issues"] if i["check"] == check_name and i["severity"] == severity]
        check(name, bool(hit), hit[0]["detail"] if hit else "no issue")
        return rr

    def drop_number(rows):
        rows[3]["zh"] = rows[3]["zh"].replace("99%", "100%")
    mutate(drop_number, "T08-drop-number", "numbers")

    def drop_negation(rows):
        rows[2]["zh"] = rows[2]["zh"].replace("并不能提供", "能提供")
    mutate(drop_negation, "T09-lost-negation", "negation")

    def drift_term(rows):
        rows[2]["zh"] = rows[2]["zh"].replace("序参量", "有序参数")
    mutate(drift_term, "T10-term-drift", "glossary")

    def change_citation(rows):
        rows[2]["zh"] = rows[2]["zh"].replace("[2, 3]", "[2, 4]")
    mutate(change_citation, "T12-citation", "citations")

    def change_figure(rows):
        rows[3]["zh"] = rows[3]["zh"].replace("图 3(A)", "图 4(A)")
    mutate(change_figure, "T13-cross-ref", "cross_refs")

    def copy_source(rows):
        rows[3]["zh"] = doc["segments"][3]["text"]
    mutate(copy_source, "T14-copied", "untranslated")

    # ---------------------------------------------------------------- T11/T15
    partial_tr = os.path.join(W, "partial.jsonl")
    write_jsonl(partial_tr, GOOD[:3])
    rep2 = os.path.join(W, "verify.partial.json")
    run([os.path.join(SCRIPTS, "verify.py"), "--segments", seg, "--translations", partial_tr,
         "--glossary", lock, "--scope", os.path.join(W, "scope.json"), "--out", rep2], expect=1)
    r2 = json.load(open(rep2, encoding="utf-8"))
    check("T11-missing-paragraph", r2["coverage"]["missing"] == ["P0004"],
          str(r2["coverage"]["missing"]))

    outdir = os.path.join(W, "out-partial")
    run([os.path.join(SCRIPTS, "assemble.py"), "--segments", seg, "--translations", partial_tr,
         "--glossary", lock, "--scope", os.path.join(W, "scope.json"), "--verify", rep2,
         "--out-dir", outdir])
    res = json.load(open(os.path.join(outdir, "result.json"), encoding="utf-8"))
    check("T15-partial-status", res["status"] == "partial"
          and any(u.get("pid") == "P0004" for u in res["uncertainty"]), res["status"])

    # ---------------------------------------------------------------- T16
    outdir2 = os.path.join(W, "out-ok")
    run([os.path.join(SCRIPTS, "assemble.py"), "--segments", seg, "--translations", tr,
         "--glossary", lock, "--scope", os.path.join(W, "scope.json"), "--verify", rep,
         "--out-dir", outdir2])
    res2 = json.load(open(os.path.join(outdir2, "result.json"), encoding="utf-8"))
    check("T16-success-status", res2["status"] == "success"
          and len(res2["result"]["bilingual_paragraphs"]) == 4
          and os.path.exists(os.path.join(outdir2, "bilingual.md")), res2["status"])

    # ---------------------------------------------------------------- T17/T18
    check("T17-number-norm", verify.norm_num("2,000") == "2000" and verify.norm_num("2.5") == "2.5")
    units = verify.UNIT.findall("physical chemical local")
    check("T18-unit-boundary", units == [], str(units))

    # ---------------------------------------------------------------- real PDF
    if a.real_pdf and os.path.exists(a.real_pdf):
        out = os.path.join(W, "real-segments.json")
        p = run([os.path.join(SCRIPTS, "segment.py"), "--pdf", a.real_pdf, "--out", out])
        rd = json.load(open(out, encoding="utf-8")) if p.returncode == 0 else {"stats": {}}
        st = rd.get("stats", {})
        ok = st.get("segments", 0) > 5 and st.get("translatable", 0) > 0
        check("T20-real-pdf", ok, json.dumps(st, ensure_ascii=False))

    print("\n%d passed, %d failed" % (len(PASSED), len(FAILED)))
    if FAILED:
        print("FAILED: " + ", ".join(FAILED))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
