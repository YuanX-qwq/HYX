#!/usr/bin/env python3
"""intro-related-work-writing · 引言与相关工作写作引擎（纯标准库）。

把"写引言/相关工作"拆成可机械核对的两层：
  证据层  parse → group → gap → contrib → coverage
  表达层  由 Agent 依据证据层写正文，脚本只做结构化与核对

子命令：
  parse     文献库（BibTeX/RIS/纯文本）→ 结构化记录
  group     按问题/方法/评价三个维度分组，抽每条工作的结论、适用条件、局限
  gap       从多条已引工作的共同/冲突局限推导研究空白（≥2 条证据才算成立）
  contrib   贡献条目与本文图表/结果编号对照，定位不上或对不上即告警
  coverage  正文引用覆盖审计（事实句无引用、关键工作未引、近期进展未引）
  assemble  汇总以上证据，产出 result 草稿
"""

import argparse
import json
import re
import sys
from pathlib import Path

CUE_LIMIT = re.compile(
    r"(however|but |limited|only |restrict|cannot|fail|lack|suffer|difficult|unable|"
    r"not (?:support|apply|generaliz)|out of scope|仅|只能|无法|未能|不足|缺少|局限|"
    r"难以|不适用|受限于)", re.I)
CUE_COND = re.compile(
    r"(under\b|when\b|in the presence|at (?:[0-9]|1 bar|room temperature)"
    r"|for [0-9]|with [0-9]|条件下|当.{0,8}时|在.{0,6}下)", re.I)
FACT_CUE = re.compile(
    r"(\d|%|outperform|improve|achiev|reach|first|state[ds]?|report|show|demonstrat|"
    r"超过|达到|首次|表明|显示|证明|提升|下降)", re.I)
CITE_RE = re.compile(r"\[([^\[\]]{1,120})\]")

DIM_LEX = {
    "problem": ["problem", "task", "setting", "scenario", "benchmark", "dataset", "domain",
                "application", "question answering", "detection", "classification",
                "任务", "问题", "场景", "数据集", "设定"],
    "method": ["method", "model", "architecture", "algorithm", "approach", "training",
               "fine-tun", "prompt", "retrieval", "graph", "transformer", "rule",
               "方法", "模型", "算法", "架构", "训练", "提示"],
    "evaluation": ["evaluat", "metric", "baseline", "ablation", "measure", "experiment",
                   "accuracy", "f1", "precision", "recall",
                   "评价", "指标", "实验", "基线", "对比", "准确率"],
}
STOP = set("""a an the of and or in on for with to from by as at is are was were be been this
that these those we our it its their they study paper work results show using used based more less
than between among during after before under over into not no can could may might also such which
however only limited""".split())


# ------------------------------------------------------------------ 通用
def words(text):
    out = set()
    for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text or ""):
        w = w.lower()
        if w not in STOP:
            out.add(w)
    for run in re.findall(r"[\u4e00-\u9fff]+", text or ""):
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


def jaccard(a, b):
    return 0.0 if not a or not b else len(a & b) / len(a | b)


def first_sentence(text):
    if not text:
        return ""
    m = re.split(r"(?<=[。！？.!?])\s+", text.strip())
    return (m[0] if m else "").strip()


def pick_sentence(text, cue, grab=2):
    sents = re.split(r"(?<=[。！？.!?])\s+", text or "")
    for s in sents:
        if cue.search(s):
            out = s.strip()
            if grab > 1:
                idx = sents.index(s)
                for nxt in sents[idx + 1: idx + grab]:
                    out += " " + nxt.strip()
            return out.strip()
    return ""


def sentences_with_pos(text):
    out = []
    for m in re.finditer(r"[^。！？!?\n]+(?:[。！？!?]|\.\s|$)", text or ""):
        t = m.group(0)
        if t.strip():
            out.append({"start": m.start(), "text": t})
    return out


# --------------------------------------------------------------- 文献解析
FIELD_START = re.compile(r"(\w+)\s*=\s*")


def _record_body(text, start):
    """从字段起点做括号配平，返回该条记录的体。"""
    depth, i = 1, start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return text[start:]


def _read_value(body, pos):
    """读一个字段值：{...} / "..." / 裸值，返回 (value, 结束位置)。"""
    while pos < len(body) and body[pos] in ", \n\r\t":
        pos += 1
    if pos >= len(body):
        return "", pos
    ch = body[pos]
    if ch == "{":
        depth, i = 1, pos + 1
        while i < len(body):
            if body[i] == "{":
                depth += 1
            elif body[i] == "}":
                depth -= 1
                if depth == 0:
                    return body[pos + 1:i], i + 1
            i += 1
        return body[pos + 1:], len(body)
    if ch == '"':
        i = pos + 1
        while i < len(body):
            if body[i] == '"' and body[i - 1] != "\\":
                return body[pos + 1:i], i + 1
            i += 1
        return body[pos + 1:], len(body)
    m = re.match(r"[^,\n}]+", body[pos:])
    return (m.group(0).strip() if m else ""), pos + (len(m.group(0)) if m else 0)


def parse_bib(text):
    recs = []
    for m in re.finditer(r"@(\w+)\s*\{([^,]+),", text):
        kind, key = m.group(1).lower(), m.group(2).strip()
        body = _record_body(text, m.end())
        fields, pos = {}, 0
        while True:
            fm = FIELD_START.search(body, pos)
            if not fm:
                break
            val, pos = _read_value(body, fm.end())
            fields[fm.group(1).lower()] = re.sub(r"[{}]", "", val).strip()
        recs.append(build_record(kind, key, fields))
    return recs


def parse_ris(text):
    recs, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])\s{0,3}-\s*(.*)$", line)
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur = {"kind": val.lower(), "key": "", "AU": [], "TI": "", "AB": "", "PY": "",
                   "JO": "", "DO": ""}
        elif cur is None:
            continue
        elif tag == "ER":
            if cur:
                recs.append(build_record(cur["kind"], cur.get("ID") or "ris%d" % (len(recs) + 1), {
                    "author": " and ".join(cur["AU"]), "title": cur["TI"], "abstract": cur["AB"],
                    "year": cur["PY"][:4], "journal": cur["JO"], "doi": cur["DO"]}))
            cur = None
        elif tag in ("AU", "A1"):
            cur["AU"].append(val)
        elif tag in ("TI", "T1"):
            cur["TI"] = val
        elif tag in ("AB", "N2"):
            cur["AB"] = val
        elif tag in ("PY", "Y1"):
            cur["PY"] = val
        elif tag in ("JO", "T2", "JF"):
            cur["JO"] = val
        elif tag == "DO":
            cur["DO"] = val
        elif tag == "ID":
            cur["ID"] = val
    return recs


def parse_txt(text):
    recs, i = [], 0
    for line in text.splitlines():
        m = re.match(r"^\s*(?:\[\d+\]|\d+\.)\s*(.+)$", line)
        if not m:
            continue
        i += 1
        raw = m.group(1).strip()
        year = re.search(r"(?:19|20)\d{2}", raw)
        recs.append(build_record("article", "txt%d" % i, {
            "title": re.split(r"\.\s+", raw)[0], "abstract": raw,
            "year": year.group(0) if year else "", "journal": "", "doi": ""}))
    return recs


def build_record(kind, key, f):
    title = re.sub(r"[{}]", "", f.get("title") or "").strip()
    abstract = re.sub(r"[{}]", "", f.get("abstract") or f.get("note") or "").strip()
    authors = [a.strip() for a in re.split(r"\s+and\s+", f.get("author") or "") if a.strip()]
    year = str(f.get("year") or "")
    year = re.findall(r"(?:19|20)\d{2}", year)
    rec = {"key": key.strip(), "type": kind, "title": title, "abstract": abstract,
           "authors": authors, "year": year[0] if year else "",
           "venue": (f.get("journal") or f.get("booktitle") or f.get("publisher") or "").strip(),
           "doi": (f.get("doi") or "").strip(),
           "limitation": pick_sentence(abstract, CUE_LIMIT) if abstract else "",
           "conditions": pick_sentence(abstract, CUE_COND) if abstract else "",
           "conclusion": first_sentence(abstract) or title}
    return rec


def load_library(path):
    text = Path(path).read_text(encoding="utf-8")
    if text.lstrip().startswith("@") or path.lower().endswith(".bib"):
        return parse_bib(text)
    if re.search(r"^TY  - ", text, re.M):
        return parse_ris(text)
    return parse_txt(text)


# ------------------------------------------------------------------- 分组
def group_records(recs):
    groups, unclassified = [], []
    buckets = {d: [] for d in DIM_LEX}
    for r in recs:
        blob = (r["title"] + " " + r["abstract"]).lower()
        scores = {d: sum(1 for w in lex if w in blob) for d, lex in DIM_LEX.items()}
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            unclassified.append(r["key"])
            buckets["method"].append(r)
        else:
            buckets[best].append(r)
    for dim, items in buckets.items():
        if not items:
            continue
        works = []
        for r in items:
            works.append({"ref": r["key"], "conclusion": r["conclusion"][:300],
                          "conditions": r["conditions"][:200], "limitation": r["limitation"][:220],
                          "title": r["title"][:200], "year": r["year"],
                          "evidence_strength": "direct" if r["abstract"] else "title_only"})
        top = sorted({w for r in items for w in words(r["title"])}, key=str)[:6]
        groups.append({"group": "%s-dimension" % dim, "dimension": dim,
                       "works": works, "terms": top})
    return {"groups": groups, "unclassified": unclassified, "total": len(recs)}


# --------------------------------------------------------------------- 空白
def derive_gap(groups, min_support=2):
    lims = []
    for g in groups["groups"]:
        for w in g["works"]:
            if w["limitation"]:
                lims.append({"ref": w["ref"], "text": w["limitation"],
                             "tokens": words(w["limitation"])})
    cands = []
    used = set()
    for i, a in enumerate(lims):
        if i in used:
            continue
        members = [a]
        for j, b in enumerate(lims):
            if j <= i or j in used:
                continue
            s = jaccard(a["tokens"], b["tokens"])
            if s >= 0.25:
                members.append(b)
                used.add(j)
        used.add(i)
        cands.append({"refs": [m["ref"] for m in members],
                      "quotes": [m["text"][:160] for m in members],
                      "support": len(members),
                      "similarity": round(jaccard(a["tokens"], members[-1]["tokens"]), 3)})
    strong = [c for c in cands if c["support"] >= min_support]
    weak = [c for c in cands if c["support"] < min_support]
    if strong:
        best = max(strong, key=lambda c: c["support"])
        return {"gap": "多篇已引工作在相同条件下受限：" + best["quotes"][0][:150],
                "evidence": "; ".join("%s: %s" % (r, q) for r, q in zip(best["refs"], best["quotes"]))[:600],
                "refs": best["refs"], "support": best["support"], "strength": "supported",
                "weak_candidates": weak}
    if weak:
        return {"gap": "单一工作的局限尚不足以支撑研究空白：%s" % weak[0]["quotes"][0][:120],
                "evidence": "; ".join("%s: %s" % (r, q) for r, q in zip(weak[0]["refs"], weak[0]["quotes"])),
                "refs": weak[0]["refs"], "support": 1, "strength": "insufficient",
                "weak_candidates": weak}
    return {"gap": "", "evidence": "", "refs": [], "support": 0, "strength": "no_evidence",
            "weak_candidates": []}


# --------------------------------------------------------------------- 贡献
def contrib_audit(contribs, paper, records):
    index = {}
    for f in paper.get("figures") or []:
        index["fig:%s" % f.get("id")] = f.get("caption", "")
    for t in paper.get("tables") or []:
        index["tab:%s" % t.get("id")] = t.get("caption", "")
    for r in paper.get("results") or []:
        index["res:%s" % r.get("id")] = " ".join(str(r.get(k, "")) for k in ("name", "value", "unit", "note"))
    by_key = {r["key"]: r for r in records}
    out = []
    for c in contribs or []:
        loc = c.get("evidence_locator") or ""
        claim = c.get("claim") or ""
        if loc.startswith("ref:"):
            rec = by_key.get(loc[4:])
            ok = bool(rec) and jaccard(words(claim), words(rec["title"] + " " + rec["conclusion"])) >= 0.2
            out.append({"claim": claim, "evidence_locator": loc,
                        "status": "ok" if ok else "locator_unresolved",
                        "detail": "" if ok else "引用的文献记录不存在或与论断无词元重合"})
            continue
        cap = index.get(loc)
        if cap is None:
            out.append({"claim": claim, "evidence_locator": loc, "status": "locator_missing",
                        "detail": "本文材料中找不到该图表/结果编号"})
            continue
        score = jaccard(words(claim), words(cap))
        out.append({"claim": claim, "evidence_locator": loc,
                    "status": "ok" if score >= 0.15 else "locator_mismatch",
                    "detail": "词元重合 %.2f（阈值 0.15）" % score})
    return out


# --------------------------------------------------------------------- 覆盖
def coverage_audit(text, records, key_works=None, recent_window=3):
    years = [int(r["year"]) for r in records if r["year"].isdigit()]
    max_year = max(years) if years else 0
    recent = [r["key"] for r in records if r["year"].isdigit() and max_year - int(r["year"]) <= recent_window]
    rec_keys = [r["key"] for r in records]
    cited = set()
    for m in CITE_RE.finditer(text or ""):
        for part in re.split(r"[,;，；]", m.group(1)):
            cited.add(part.strip())
    uncited_sents = []
    for s in sentences_with_pos(text):
        t = s["text"].strip()
        if not FACT_CUE.search(t):
            continue
        if CITE_RE.search(t):
            continue
        uncited_sents.append({"text": t[:180], "offset": s["start"]})
    keys = key_works if key_works is not None else rec_keys[: max(1, len(rec_keys) // 2)]
    missing_key = [k for k in keys if k not in cited]
    missing_recent = [k for k in recent if k not in cited]
    unknown = sorted(c for c in cited if c and c not in rec_keys)
    return {"key_works": keys, "recent_works": recent, "missing": missing_key + missing_recent,
            "uncited_sentences": uncited_sents, "unknown_citations": unknown,
            "cited_count": len([c for c in cited if c in rec_keys]), "sentence_count": len(sentences_with_pos(text))}


# --------------------------------------------------------------------- 汇总
def assemble(recs, groups, gap, contribs, cov, case):
    years = [int(r["year"]) for r in recs if r["year"].isdigit()]
    venues = sorted({r["venue"] for r in recs if r["venue"]})
    dims = [g["dimension"] for g in groups["groups"]]
    good_contribs = [c for c in contribs if c.get("status", "ok") == "ok"]
    bad_contribs = [c for c in contribs if c.get("status", "ok") != "ok"]
    clean = (gap["strength"] == "supported" and not cov["missing"]
             and not cov["uncited_sentences"] and not cov["unknown_citations"] and not bad_contribs)
    background = {
        "thread": "研究脉络：%s–%s 年，%d 条已引工作，主要发表渠道 %s" % (
            min(years) if years else "?", max(years) if years else "?", len(recs),
            "、".join(venues[:3]) if venues else "未记录"),
        "problem": "问题设定（%s）：%s" % (
            dims[0] if dims else "未分组",
            groups["groups"][0]["works"][0]["conclusion"][:150] if groups["groups"] else ""),
        "constraints": "技术约束：%s" % ("；".join(
            w["conditions"] for g in groups["groups"] for w in g["works"] if w["conditions"])[:300] or "文献未报告明确条件"),
        "open_issue": gap["gap"] or "已引文献的局限不足以推出明确空白，需补充材料",
    }
    return {"case_id": case.get("case_id", ""), "task_id": case.get("task_id", ""),
            "status": "success" if clean else "partial",
            "results": {"background": background,
                        "related_work": [{"group": g["group"], "dimension": g["dimension"],
                                          "works": [{k: w[k] for k in ("ref", "conclusion", "conditions", "limitation")}
                                                    for w in g["works"]]} for g in groups["groups"]],
                        "gap": {"gap": gap["gap"], "evidence": gap["evidence"], "how_paper_fills": ""},
                        "contributions": [{"claim": c["claim"], "evidence_locator": c["evidence_locator"]}
                                          for c in good_contribs],
                        "citations_coverage": {"key_works": cov["key_works"], "recent_works": cov["recent_works"],
                                              "missing": cov["missing"]}},
            "sources": [{"source_id": r["key"], "locator": "library record: %s" % r["key"],
                         "locator_type": "bibliography_record",
                         "quote": (r["abstract"] or r["title"])[:160],
                         "note": "conclusion/conditions/limitation 均从该记录抽取"} for r in recs],
            "uncertainty": ([{"item": "未归类文献 %s" % groups["unclassified"],
                              "reason": "题名与摘要中未命中任何维度词表", "action_required": "人工指定分组维度"}]
                            if groups["unclassified"] else []) +
                           ([{"item": "研究空白证据不足（支持条目 %d）" % gap["support"],
                              "reason": "共同局限的支撑工作少于 2 条", "action_required": "补充文献或改写为单篇局限陈述"}]
                            if gap["strength"] != "supported" else []) +
                           ([{"item": "正文无引用的论断 %d 句" % len(cov["uncited_sentences"]),
                              "reason": "事实句缺少引用标记", "action_required": "补引用或标为作者判断"}]
                            if cov["uncited_sentences"] else []) +
                           ([{"item": "正文引用了库外条目 %s" % cov["unknown_citations"],
                              "reason": "引用键在文献库中不存在", "action_required": "核对键名或补条目"}]
                            if cov["unknown_citations"] else []) +
                           ([{"item": "贡献条目 %d 条定位不上或对不上：%s" % (
                               len(bad_contribs), "; ".join(c["evidence_locator"] for c in bad_contribs)),
                              "reason": "本文材料中缺少该图表/结果编号，或论断与图表说明无词元重合",
                              "action_required": "补图表/结果，或改写贡献并重新对照"}]
                            if bad_contribs else []),
            "changes": [{"step": "1", "action": "解析文献库", "note": "%d 条记录" % len(recs)},
                        {"step": "2", "action": "按维度分组", "note": "分组 %d 个：%s" % (len(dims), "、".join(dims))},
                        {"step": "3", "action": "推导研究空白", "note": "%s（支持 %d 条）" % (gap["strength"], gap["support"])},
                        {"step": "4", "action": "贡献与图表结果对照", "note": "核对 %d 条" % len(contribs)},
                        {"step": "5", "action": "引用覆盖审计", "note": "缺失 %d 项，无引用事实句 %d 句" % (len(cov["missing"]), len(cov["uncited_sentences"]))}],
            "artifacts": []}


def main(argv=None):
    ap = argparse.ArgumentParser(description="intro & related work writing engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse"); p.add_argument("--library", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("group"); p.add_argument("--records", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("gap"); p.add_argument("--groups", required=True); p.add_argument("--out", required=True)
    p = sub.add_parser("contrib"); p.add_argument("--paper", required=True); p.add_argument("--contribs", required=True)
    p.add_argument("--library", default=""); p.add_argument("--out", required=True)
    p = sub.add_parser("coverage"); p.add_argument("--text", required=True); p.add_argument("--library", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("assemble"); p.add_argument("--case", required=True); p.add_argument("--library", required=True)
    p.add_argument("--intro", default=""); p.add_argument("--paper", default=""); p.add_argument("--out", required=True)

    a = ap.parse_args(argv)

    def write(path, obj):
        Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    if a.cmd == "parse":
        recs = load_library(a.library)
        write(a.out, recs)
        print("records=%d with_abstract=%d" % (len(recs), sum(1 for r in recs if r["abstract"])))
        return 0
    if a.cmd == "group":
        g = group_records(json.loads(Path(a.records).read_text(encoding="utf-8")))
        write(a.out, g)
        print("groups=%d unclassified=%d" % (len(g["groups"]), len(g["unclassified"])))
        return 0
    if a.cmd == "gap":
        gap = derive_gap(json.loads(Path(a.groups).read_text(encoding="utf-8")))
        write(a.out, gap)
        print("gap_strength=%s support=%d" % (gap["strength"], gap["support"]))
        return 0
    if a.cmd == "contrib":
        paper = json.loads(Path(a.paper).read_text(encoding="utf-8")) if Path(a.paper).exists() else {}
        contribs = json.loads(Path(a.contribs).read_text(encoding="utf-8"))
        if isinstance(contribs, dict):
            contribs = contribs.get("contributions") or (contribs.get("results") or {}).get("contributions") or []
        recs = load_library(a.library) if a.library else []
        res = contrib_audit(contribs, paper, recs)
        write(a.out, res)
        print("checked=%d ok=%d issues=%d" % (len(res), sum(1 for c in res if c["status"] == "ok"),
                                              sum(1 for c in res if c["status"] != "ok")))
        return 0
    if a.cmd == "coverage":
        recs = load_library(a.library)
        cov = coverage_audit(Path(a.text).read_text(encoding="utf-8"), recs)
        write(a.out, cov)
        print("cited=%d missing=%d uncited_sentences=%d unknown=%d"
              % (cov["cited_count"], len(cov["missing"]), len(cov["uncited_sentences"]), len(cov["unknown_citations"])))
        return 0
    if a.cmd == "assemble":
        case = json.loads(Path(a.case).read_text(encoding="utf-8")) if Path(a.case).exists() else {}
        recs = load_library(a.library)
        groups = group_records(recs)
        gap = derive_gap(groups)
        paper = json.loads(Path(a.paper).read_text(encoding="utf-8")) if a.paper and Path(a.paper).exists() else {}
        contribs = [{"claim": c, "evidence_locator": l} for c, l in
                    [(x.get("claim"), x.get("evidence_locator")) for x in (paper.get("contributions") or [])]]
        contribs = contrib_audit(contribs, paper, recs)
        cov = coverage_audit(Path(a_intro).read_text(encoding="utf-8") if (a_intro := a.intro) else "",
                             recs)
        draft = assemble(recs, groups, gap, contribs, cov, case)
        write(a.out, draft)
        print("status=%s groups=%d gap=%s contributions=%d missing_cites=%d"
              % (draft["status"], len(draft["results"]["related_work"]), gap["strength"],
                 len(draft["results"]["contributions"]), len(cov["missing"])))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
