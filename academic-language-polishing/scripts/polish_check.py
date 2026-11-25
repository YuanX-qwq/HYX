#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""polish_check — 学术润色的机械守恒检查（纯标准库）

检查"改得对不对、有没有改坏"：数值、单位、引用编号、图表指向、否定、限定强度、
条件句、量词、缩写首现、术语变体，以及每条修改记录能否在原文/改文中落位。

用法：
  python3 scripts/polish_check.py --original orig.txt --revised rev.txt \
      [--glossary glossary.json] [--revisions revisions.json] --out check.json

退出码：0 = PASS/WARN，1 = 出现 FAIL（必须回改）。
"""
import argparse
import json
import re
import sys
from pathlib import Path

NUM = re.compile(r"\d+(?:\.\d+)?(?:\s?(?:%|‰|mg|g|kg|ml|l|h|min|s|K|°C|°|eV|nm|µm|μm|MPa|kPa|bar|ppm|ppb|mM|µM|μM|nM|x|×))?", re.I)
CITE = re.compile(r"\[\d+(?:\s*[,\-–]\s*\d+)*\]|\bref\.?\s?\d+|\([A-Z][A-Za-z\-]+(?:\s+et\s+al\.)?,\s?\d{4}\)|（[A-Z][A-Za-z\-]+(?:\s*等)?，?\s?\d{4}）")
XREF = re.compile(r"(?:Fig(?:ure)?\.?|Table|Eq\.?|Equation|Section|Supplementary\s+Fig\.?)\s?\d+[A-Za-z]?|图\s?\d+[A-Za-z]?|表\s?\d+|式\s?\(\d+\)")
NEG = re.compile(r"\b(?:not|never|no|none|neither|nor|cannot|can't|without|fail(?:ed|s)?\s+to)\b|不|未|无|没有|不得|禁止|无法|并非", re.I)
HEDGE = re.compile(r"\b(?:may|might|could|possibly|likely|probably|suggest(?:s|ed)?|indicat(?:e|es|ed)|appear(?:s|ed)?|seem(?:s|ed)?|tend(?:s|ed)?|approximately|about|roughly|relatively|partly|somewhat)\b|可能|或许|提示|表明|倾向于|相对|约|大致", re.I)
STRONG = re.compile(r"\b(?:demonstrat(?:e|es|ed)|prove(?:s|d)?|confirm(?:s|ed)?|establish(?:es|ed)?|always|invariably|significantly|substantially|strongly)\b|证明|证实|显著|必然|一定|完全|强烈|大幅", re.I)
COND = re.compile(r"\b(?:if|unless|when|provided\s+that|in\s+case)\b|若|如果|当|在.{0,8}条件下|除非", re.I)
QUANT = re.compile(r"\b(?:all|most|many|some|few|each|every|none)\b|全部|所有|多数|部分|每个|若干|少数", re.I)
ABBR = re.compile(r"\b[A-Z]{2,6}s?\b")

KIND_ZH = {
    "number": "数值", "unit": "单位", "citation": "引用编号", "xref": "图表/公式指向",
    "negation": "否定", "hedge": "限定强度", "condition": "条件句", "quantifier": "量词",
    "abbr": "缩写首现", "term": "术语一致性", "revision": "修改记录",
}


def norm_numbers(text):
    # 单位大小写（ml vs mL）属可修的书写问题，比较时统一小写
    return sorted({re.sub(r"\s", "", m.group(0)).lower() for m in NUM.finditer(text or "")})


def citation_keys(text):
    out = set()
    for m in CITE.finditer(text or ""):
        out.update(re.findall(r"\d+", m.group(0)))
    return out


def xref_keys(text):
    return {re.sub(r"\s", "", m.group(0)).lower() for m in XREF.finditer(text or "")}


def toks(rx, text):
    return [m.group(0).lower() for m in rx.finditer(text or "")]


def issue(kind, severity, detail, original="", revised=""):
    return {"kind": kind, "kind_zh": KIND_ZH.get(kind, kind), "severity": severity,
            "detail": detail, "original": original, "revised": revised}


def check_text(orig, rev, glossary=None, revisions=None):
    gl = glossary or []
    issues, passed = [], []

    def gate(kind, ok, detail, o="", r="", severity="fail"):
        if ok:
            passed.append({"kind": kind, "detail": detail})
        else:
            issues.append(issue(kind, severity, detail, o, r))

    # 1) 数值与单位一一对应
    on, rn = set(norm_numbers(orig)), set(norm_numbers(rev))
    gate("number", on == rn, f"原 {len(on)} 个数值 / 改 {len(rn)} 个；新增={sorted(rn - on)[:6]} 丢失={sorted(on - rn)[:6]}")
    ou = {x for x in on if re.search(r"[a-z%°µ]", x)}
    ru = {x for x in rn if re.search(r"[a-z%°µ]", x)}
    gate("unit", ou == ru, f"带单位数值不一致：新增={sorted(ru - ou)[:6]} 丢失={sorted(ou - ru)[:6]}")

    # 2) 引用编号与图表指向
    oc, rc = citation_keys(orig), citation_keys(rev)
    gate("citation", oc == rc, f"引用编号集合不同：新增={sorted(rc - oc)} 丢失={sorted(oc - rc)}")
    ox, rx_ = xref_keys(orig), xref_keys(rev)
    gate("xref", ox == rx_, f"图表/公式指向不同：新增={sorted(rx_ - ox)[:4]} 丢失={sorted(ox - rx_)[:4]}")

    # 3) 否定与限定强度
    oneg, rneg = len(toks(NEG, orig)), len(toks(NEG, rev))
    gate("negation", oneg == rneg, f"否定标记 原 {oneg} / 改 {rneg}（减少即可能改变结论方向）")
    oh, rh = toks(HEDGE, orig), toks(HEDGE, rev)
    os_, rs = toks(STRONG, orig), toks(STRONG, rev)
    added_strong = sorted(set(rs) - set(os_))
    gate("hedge", not added_strong,
         f"强化词新增={added_strong}；原文限定词 {len(oh)} / 改文 {len(rh)}（不得把“可能/提示”升级为“证明/必然”）")
    dropped_hedge = sorted(set(oh) - set(rh))
    if dropped_hedge:
        issues.append(issue("hedge", "warn", f"限定词减少={dropped_hedge}，必须在 revisions 中写明理由"))

    # 4) 条件句与量词
    ocond, rcond = len(toks(COND, orig)), len(toks(COND, rev))
    gate("condition", rcond >= ocond, f"条件句 原 {ocond} / 改 {rcond}（减少即丢条件）")
    oq, rq = sorted(set(toks(QUANT, orig))), sorted(set(toks(QUANT, rev)))
    gate("quantifier", oq == rq or not oq, f"量词 原 {oq} / 改 {rq}（all↔some 一类替换会改变外推范围）")

    # 5) 缩写首现
    abbr_bad = []
    for ab in sorted({a for a in ABBR.findall(rev or "")}):
        pos = (rev or "").find(ab)
        head = (rev or "")[:pos]
        if not re.search(r"[（(]" + re.escape(ab) + r"[)）]", head) and not re.search(r"[（(]" + re.escape(ab) + r"[)）]", rev or ""):
            abbr_bad.append(ab)
    gate("abbr", not abbr_bad, f"缩写未见首次展开：{abbr_bad[:6]}", severity="warn")

    # 6) 术语表驱动的全篇一致性
    term_bad = []
    for g in gl:
        canon = g.get("canonical") or g.get("en_form")
        forms = [f for f in [canon] + list(g.get("variants") or []) if f]
        present = [f for f in forms if f in (rev or "")]
        if present and canon and canon not in present:
            term_bad.append({"concept": g.get("concept"), "only_variants": present,
                             "hint": "改回术语表写法"})
        elif len(present) > 1:
            term_bad.append({"concept": g.get("concept"), "multiple_forms": present,
                             "hint": "统一为术语表写法"})
    gate("term", not term_bad, f"术语不一致：{json.dumps(term_bad, ensure_ascii=False)[:220]}", severity="warn")

    # 7) 修改记录可落位 + 覆盖率
    revs = revisions or []
    bad = []
    for i, r in enumerate(revs):
        for k in ("span", "original", "revised", "type", "reason"):
            if not str(r.get(k) or "").strip():
                bad.append({"index": i, "missing": k})
        if r.get("original") and r["original"] not in (orig or ""):
            bad.append({"index": i, "problem": "original 不在原文中", "text": r["original"][:40]})
        if r.get("revised") and r["revised"] not in (rev or ""):
            bad.append({"index": i, "problem": "revised 不在改文中", "text": r["revised"][:40]})
        if "preserves_meaning" not in r:
            bad.append({"index": i, "problem": "缺 preserves_meaning"})
    gate("revision", not bad, f"修改记录问题：{json.dumps(bad, ensure_ascii=False)[:260]}")

    # 8) 覆盖率提示：有改动但没有记录（按句粗判）
    coverage = None
    if revisions:
        o_sent = [s for s in re.split(r"(?<=[。！？.!?])\s*", orig or "") if len(s.strip()) > 8]
        changed = sum(1 for s in o_sent if s.strip() and s.strip() not in (rev or ""))
        coverage = round(min(1.0, len(revisions) / changed), 3) if changed else 1.0
        if changed and coverage < 0.6:
            issues.append(issue("revision", "warn",
                                f"约 {changed} 句发生变化，但只记录 {len(revisions)} 条修改，覆盖率 {coverage}"))

    fails = sum(1 for i in issues if i["severity"] == "fail")
    warns = sum(1 for i in issues if i["severity"] == "warn")
    verdict = "FAIL" if fails else ("WARN" if warns else "PASS")
    return {"verdict": verdict, "fails": fails, "warns": warns,
            "issues": issues, "passed": passed, "coverage": coverage,
            "counts": {"numbers": len(on), "citations": len(oc), "xrefs": len(ox),
                       "negations": oneg, "hedges": len(oh), "conditions": ocond,
                       "revision_records": len(revs)}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="学术润色机械守恒检查")
    ap.add_argument("--original", required=True)
    ap.add_argument("--revised", required=True)
    ap.add_argument("--glossary")
    ap.add_argument("--revisions")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    orig = Path(a.original).read_text(encoding="utf-8")
    rev = Path(a.revised).read_text(encoding="utf-8")
    gl = json.loads(Path(a.glossary).read_text(encoding="utf-8")) if a.glossary else []
    if isinstance(gl, dict):
        gl = gl.get("terms") or gl.get("glossary") or []
    revs = json.loads(Path(a.revisions).read_text(encoding="utf-8")) if a.revisions else []
    if isinstance(revs, dict):
        revs = revs.get("revisions") or (revs.get("results") or {}).get("revisions") or []
    rep = check_text(orig, rev, gl, revs)
    text = json.dumps(rep, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out}")
    print(f"verdict={rep['verdict']} fails={rep['fails']} warns={rep['warns']} "
          f"numbers={rep['counts']['numbers']} revisions={rep['counts']['revision_records']}")
    return 0 if rep["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())

