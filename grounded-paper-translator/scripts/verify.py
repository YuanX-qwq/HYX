#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify.py -- mechanical fidelity checks for a bilingual translation.

This is the core of the skill: every paragraph is compared against its source
with deterministic rules; nothing is judged by style or by asking a model again.
Checks (each produces pass/warn/fail):

  coverage        every pid in scope has exactly one non-empty translation
  numbers         the multiset of numeric tokens is preserved
  units           unit / percent tokens are preserved
  citations       [12] style and (Author, 2019) style references survive
  cross_refs      Figure/Table/Eq/Section/Ref numbers survive with 图/表/式/节 markers
  symbols         Greek letters and math symbols are not lost
  negation        negation is not dropped or invented
  hedging         modal / approximating words are not hardened
  glossary        locked terms use the locked Chinese term in every paragraph
  length          translation length ratio stays inside a plausible band
  sentences       sentence count does not collapse (omission signal)
  untranslated    Latin-letter leakage / copied source is flagged
  placeholder     [待确认]/TODO markers must be declared as uncertainty

Usage
-----
  python3 verify.py --segments work/segments.json \
      --translations work/translations.jsonl \
      --glossary work/glossary.json --scope work/scope.json \
      --out work/verify_report.json [--case /input/case.json]

Exit code 0 when there is no FAIL, 1 when at least one FAIL exists, 2 on
malformed input.  The report is written either way.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

GREEK = "αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ"
MATH_SYMBOLS = "∑∏∫√±×÷≈≠≤≥∂∇∞→←↔⇒⇔°µμ·†‡∗⟨⟩"
NEG_EN = re.compile(r"\b(not|no|never|without|cannot|can't|don't|doesn't|didn't|isn't|"
                    r"aren't|wasn't|weren't|fail(?:s|ed)?|lack(?:s|ed)?|absent|none|"
                    r"neither|nor|unable|impossible|free of|excluded)\b", re.I)
NEG_ZH = re.compile(r"(无法|不能|不会|不是|不得|没有|未能|并不|不存在|缺乏|禁止|否定|否|勿|"
                    r"不(?!同|仅|但|过|断|论|得|少|久|如|妨)|"
                    r"非(?!常|凡|线|晶|平衡|对角|弹性|铁|微|相|均)|"
                    r"无(?!法|论|疑|数|穷|需|限|序|关|规))")
HEDGE_EN = re.compile(r"\b(may|might|could|suggest(?:s|ed)?|indicat(?:e|es|ed)|appears?|"
                      r"likely|presumably|approximately|roughly|nearly|almost|"
                      r"tend(?:s|ed)?|seems?|possibly|perhaps|potentially)\b", re.I)
HEDGE_ZH = re.compile(r"(可能|或许|也许|表明|提示|似乎|大约|约|近似|几乎|倾向|潜在|推测|大概|未必|"
                      r"可以|能够|能否)")
NUM = re.compile(r"(?<![\w.])[-−–]?\d+(?:[.,]\d+)*(?:\s?[×x]\s?10\s?\^?\s?[-−]?\d+)?"
                 r"|(?<![\w.])\d+(?:\.\d+)?\s?%")
CITE_BRACKET = re.compile(r"\[[\d,\s\-–—]+\]")
CITE_PAREN = re.compile(r"\([A-Z][A-Za-z.\-]+(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z.\-]+))?,?\s*"
                        r"(?:19|20)\d{2}[a-z]?\)")
XREF = re.compile(r"\b(Fig(?:ure)?s?|Tab(?:le)?s?|Eq(?:uation)?s?|Sec(?:tion)?s?|"
                  r"Ref(?:erence)?s?|Appendix|Suppl(?:ementary)?)\s*\.?\s*[\(\[]?(\d+[A-Za-z]?)\)?\]?", re.I)
XREF_MAP = {"fig": "图", "figs": "图", "figure": "图", "figures": "图",
            "tab": "表", "tabs": "表", "table": "表", "tables": "表",
            "eq": "式", "eqs": "式", "equation": "式", "equations": "式",
            "sec": "节", "secs": "节", "section": "节", "sections": "节",
            "ref": "文献", "refs": "文献", "reference": "文献", "references": "文献",
            "appendix": "附录", "suppl": "补充", "supplementary": "补充"}
UNIT = re.compile(r"(?<![A-Za-z])(%|°C|eV|meV|keV|Å|nm|µm|μm|mm|cm|km|ms|ns|ps|fs|Hz|"
                  r"kHz|MHz|GHz|THz|Oe|mbar|kPa|MPa|GPa|mol|mM|µM|μM|nM|µL|μL|mL|dL|"
                  r"kW|MW|mV|kV|mA|µA|μA|Ω|kJ|kcal|cal|kDa|rpm|mg|µg|μg|ng|kg)(?![A-Za-z])")
PLACEHOLDER = re.compile(r"(待确认|待定|TODO|TBD|\?\?\?|\[?无法确定\]?|\[?不确定\])")
LATIN = re.compile(r"[A-Za-z]")


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_translations(path):
    """Accept JSONL ({pid, zh}) or JSON (list or {pid: str|{zh}})."""
    trans = {}
    with open(path, encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return trans
    if raw[0] == "[":
        for item in json.loads(raw):
            pid = item.get("pid") or item.get("id")
            if pid:
                trans[pid] = item
        return trans
    if raw[0] == "{":
        try:
            obj = json.loads(raw)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            if "translations" in obj and isinstance(obj["translations"], list):
                for item in obj["translations"]:
                    trans[item["pid"]] = item
                return trans
            for pid, v in obj.items():
                if isinstance(v, str):
                    trans[pid] = {"pid": pid, "zh": v}
                elif isinstance(v, dict):
                    d = dict(v)
                    d.setdefault("pid", pid)
                    trans[pid] = d
            return trans
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        pid = item.get("pid") or item.get("id")
        if pid:
            trans[pid] = item
    return trans


def norm_num(t):
    t = t.replace("−", "-").replace("–", "-")
    t = t.replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    t = re.sub(r"^\+", "", t)
    t = re.sub(r"\^(-?\d+)", r"\1", t)
    return t


def numbers(text):
    out = []
    for m in NUM.finditer(text or ""):
        out.append(norm_num(m.group(0)))
    return Counter(out)


def zh_sent_count(text):
    return max(1, len(re.findall(r"[。！？；!?;]", text or "")))


def src_sent_count(seg):
    s = seg.get("sentences") or []
    return max(1, len(s))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", required=True)
    ap.add_argument("--translations", required=True)
    ap.add_argument("--glossary", default=None)
    ap.add_argument("--scope", default=None)
    ap.add_argument("--case", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    try:
        doc = load_json(a.segments)
        trans = load_translations(a.translations)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "input-error: %s" % e}, ensure_ascii=False))
        return 2
    segs = {s["pid"]: s for s in doc.get("segments", [])}
    gloss = load_json(a.glossary)["terms"] if a.glossary and os.path.exists(a.glossary) else []
    scope = load_json(a.scope) if a.scope and os.path.exists(a.scope) else None
    scope_pids = scope["pids"] if scope else [p for p, s in segs.items()
                                              if s["kind"] in ("title", "abstract", "heading",
                                                               "body", "caption", "table", "footnote")]
    case_id = None
    if a.case and os.path.exists(a.case):
        try:
            case_id = load_json(a.case).get("case_id")
        except Exception:
            case_id = None

    issues = []
    per_seg = defaultdict(list)

    def add(pid, check, severity, detail, source=None, target=None):
        it = {"pid": pid, "check": check, "severity": severity, "detail": detail,
              "source": (source or "")[:300], "target": (target or "")[:300]}
        issues.append(it)
        per_seg[pid].append(it)

    # ---------------------------------------------------------------- coverage
    missing, empty, extra = [], [], []
    for pid in scope_pids:
        t = trans.get(pid)
        if not t or not str(t.get("zh") or "").strip():
            missing.append(pid)
        elif pid not in segs:
            extra.append(pid)
    for pid in trans:
        if pid not in segs:
            extra.append(pid)
    translated = [p for p in scope_pids if trans.get(p) and str(trans[p].get("zh") or "").strip()]
    coverage_rate = len(translated) / max(1, len(scope_pids))

    # ------------------------------------------------------------- per segment
    glossary_hits = {i: 0 for i in range(len(gloss))}
    glossary_ok = {i: 0 for i in range(len(gloss))}
    glossary_detail = defaultdict(list)

    for pid in translated:
        seg = segs.get(pid)
        if not seg:
            continue
        src = seg.get("text") or ""
        zh = str(trans[pid].get("zh") or "").strip()
        note = " ".join(str(x) for x in (trans[pid].get("uncertainty") or []) if x) if isinstance(
            trans[pid].get("uncertainty"), list) else str(trans[pid].get("uncertainty") or "")
        note = note + " " + str(trans[pid].get("notes") or "")

        if zh == src:
            add(pid, "untranslated", "fail", "translation identical to source")
        # numbers
        cn, tn = numbers(src), numbers(zh)
        miss_nums = cn - tn
        if miss_nums:
            add(pid, "numbers", "fail",
                "numbers missing: %s" % ", ".join(sorted(miss_nums.elements())[:12]),
                src, zh)
        # units
        cu, tu = Counter(m.group(0) for m in UNIT.finditer(src)), Counter(m.group(0) for m in UNIT.finditer(zh))
        if cu - tu:
            add(pid, "units", "warn", "unit tokens missing: %s" % ", ".join(sorted((cu - tu).elements())[:8]),
                src, zh)
        # citations
        cc, tc = Counter(CITE_BRACKET.findall(src)), Counter(CITE_BRACKET.findall(zh))
        lost = [c for c in (cc - tc).elements()]
        if lost:
            add(pid, "citations", "fail", "citation markers missing: %s" % ", ".join(lost[:8]), src, zh)
        cp, tp = Counter(CITE_PAREN.findall(src)), Counter(CITE_PAREN.findall(zh))
        if cp - tp:
            add(pid, "citations", "warn", "author-year citations changed: %s" %
                ", ".join(sorted((cp - tp).elements())[:5]), src, zh)
        # cross references
        for m in XREF.finditer(src):
            kind = m.group(1).lower().rstrip(".")
            num = m.group(2)
            marker = XREF_MAP.get(kind, "")
            if not marker:
                continue
            forward = re.search(re.escape(marker) + r"\s*\[?\(?\s*" + re.escape(num), zh)
            backward = re.search(r"第?\s*" + re.escape(num) + r"\s*[\)\]]?\s*" + re.escape(marker), zh)
            if not (forward or backward):
                add(pid, "cross_refs", "fail",
                    "reference %s %s not rendered as %s%s" % (m.group(1), num, marker, num), src, zh)
        # symbols
        sym_src = Counter(c for c in src if c in GREEK + MATH_SYMBOLS)
        sym_tgt = Counter(c for c in zh if c in GREEK + MATH_SYMBOLS)
        if sym_src - sym_tgt:
            add(pid, "symbols", "warn", "symbols missing: %s" %
                " ".join(sorted((sym_src - sym_tgt).elements())[:10]), src, zh)
        # negation
        ne, nz = len(NEG_EN.findall(src)), len(NEG_ZH.findall(zh))
        if ne and not nz:
            add(pid, "negation", "fail",
                "source has %d negation cue(s) (%s) but translation has none" %
                (ne, ", ".join(sorted(set(m.group(0).lower() for m in NEG_EN.finditer(src)))[:5])),
                src, zh)
        elif nz and not ne and len(zh) > 20:
            add(pid, "negation", "warn", "translation adds negation not present in source", src, zh)
        # hedging
        he, hz = len(HEDGE_EN.findall(src)), len(HEDGE_ZH.findall(zh))
        if he and not hz:
            add(pid, "hedging", "warn", "modal/approximating words may be hardened", src, zh)
        # length / sentences
        sw = max(1, len(src.split()))
        ratio = len(zh) / sw
        if ratio < 0.7:
            add(pid, "length", "fail", "translation suspiciously short (ratio %.2f)" % ratio, src, zh)
        elif ratio > 3.8:
            add(pid, "length", "warn", "translation unusually long (ratio %.2f)" % ratio, src, zh)
        ss, zs = src_sent_count(seg), zh_sent_count(zh)
        if zs < max(1, int(0.55 * ss)):
            add(pid, "sentences", "warn",
                "sentence count dropped: source %d -> target %d" % (ss, zs), src, zh)
        # latin leakage
        if len(zh) > 30:
            lat = len(LATIN.findall(zh)) / max(1, len(zh))
            if lat > 0.55:
                add(pid, "untranslated", "warn",
                    "high Latin-letter ratio (%.2f) - check for untranslated text" % lat, src, zh)
        # placeholders
        ph = PLACEHOLDER.findall(zh)
        if ph and not note.strip():
            add(pid, "placeholder", "warn",
                "uncertainty marker %s used but no uncertainty note recorded" % ph[0], src, zh)

        # glossary
        for i, g in enumerate(gloss):
            en, zt = g["term_en"], g["term_zh"]
            words = [re.escape(w) for w in en.split()]
            pat = r"(?<![A-Za-z])" + r"[-\s]+".join(words) + r"(?![A-Za-z])"
            if not re.search(pat, src, re.I):
                continue
            glossary_hits[i] += 1
            variants = [zt] + list(g.get("variants") or [])
            if any(v and v in zh for v in variants):
                glossary_ok[i] += 1
            else:
                glossary_detail[i].append(pid)
                add(pid, "glossary", "fail",
                    "locked term '%s' must be rendered as '%s'" % (en, zt), src, zh)

    # ------------------------------------------------------------- glossary agg
    term_rows = []
    for i, g in enumerate(gloss):
        hits, ok = glossary_hits[i], glossary_ok[i]
        rate = (ok / hits) if hits else 1.0
        term_rows.append({"term_en": g["term_en"], "term_zh": g["term_zh"],
                          "occurrences": hits, "compliant": ok, "consistency": round(rate, 3),
                          "violating_pids": glossary_detail[i][:20]})
    g_rate = (sum(r["compliant"] for r in term_rows) / max(1, sum(r["occurrences"] for r in term_rows))
              if term_rows else 1.0)

    fails = [i for i in issues if i["severity"] == "fail"]
    warns = [i for i in issues if i["severity"] == "warn"]
    checks = Counter(i["check"] for i in issues)
    human_review = []
    for i in fails[:60]:
        human_review.append("%s [%s] %s: %s" % (i["pid"], i["check"], i["detail"], i["target"][:80]))

    status = "pass"
    if coverage_rate < 1.0:
        status = "incomplete"
    if fails:
        status = "issues"

    report = {
        "schema": "translation-verify/v1",
        "case_id": case_id,
        "status": status,
        "coverage": {"scope": len(scope_pids), "translated": len(translated),
                     "missing": missing, "empty": empty, "extra": sorted(set(extra)),
                     "rate": round(coverage_rate, 4)},
        "metrics": {
            "glossary_consistency": round(g_rate, 4),
            "fail_count": len(fails), "warn_count": len(warns),
            "checked_segments": len(translated),
            "avg_length_ratio": round(sum(len(str(trans[p].get("zh") or "")) /
                                          max(1, len(segs[p]["text"].split()))
                                          for p in translated) / max(1, len(translated)), 3),
        },
        "glossary_terms": term_rows,
        "issue_counts": dict(checks),
        "issues": issues,
        "human_review": human_review,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps({"ok": not fails, "status": status,
                      "coverage": report["coverage"]["rate"],
                      "fails": len(fails), "warns": len(warns),
                      "issue_counts": dict(checks),
                      "glossary_consistency": g_rate,
                      "out": os.path.abspath(a.out)}, ensure_ascii=False))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
