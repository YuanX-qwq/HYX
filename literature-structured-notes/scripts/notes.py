#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""notes.py — 按论文自身章节顺序抽取结构化笔记（标准库，无第三方依赖）。

只做机械事：按章节切句、按线索词定位研究问题/数据/方法/发现/局限、抽取可检索知识点，
并给每条笔记绑定原文定位（section + paragraph）。语义判断与改写由 Agent 按 SKILL.md 完成。

用法：
  python3 scripts/notes.py build --case /input/case.json --out /app/work/results_draft.json
  python3 scripts/notes.py render --case /input/case.json --draft /app/work/results_draft.json --out /app/output/result.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

KINDS = [
    ("abstract", r"abstract|摘要"),
    ("intro", r"introduction|background|引言|前言|背景"),
    ("method", r"method|methodology|approach|experimental|材料与方法|方法|实验"),
    ("data", r"data|dataset|materials|samples|数据|材料|样本|数据集"),
    ("result", r"result|finding|结果|发现"),
    ("discussion", r"discussion|讨论"),
    ("conclusion", r"conclusion|summary|结论|小结|总结"),
    ("limitation", r"limitation|shortcoming|局限|不足|限制"),
]

SENT = re.compile(r"(?<=[。！？])\s*|(?<=[.!?])\s+(?=[A-Z0-9\u4e00-\u9fa5])")
QUESTION = re.compile(r"\?|？|whether|whether or not|是否|研究问题|we ask|this study asks", re.I)
METHOD_CUE = re.compile(r"\b(we|authors?)\b.{0,40}\b(used|measured|analy[sz]ed|collected|trained|tested|采用|使用|测量|采集|训练)",
                        re.I)
RESULT_CUE = re.compile(r"\b(increased|decreased|reached|showed|found|improved|higher|lower)\b|提高|降低|达到|显示|发现", re.I)
CONCL_CUE = re.compile(r"\b(conclude|conclusion|indicate|suggest|in summary|therefore)\b|结论|表明|说明|因此|综上", re.I)
LIMIT_CUE = re.compile(r"\b(limitation|limited|only|however|future work|cannot)\b|局限|不足|仅|尚不能", re.I)
DATA_CUE = re.compile(r"\b(dataset|datasets|samples?|cohort|n\s*=|participants?|specimens?)\b|数据集|样品|样本|例", re.I)
TERM = re.compile(r"\b([A-Z][A-Za-z0-9\-]{2,}(?:\s+[A-Z][A-Za-z0-9\-]{1,}){0,2})\b|([\u4e00-\u9fa5]{2,8})")
METRIC = re.compile(r"\d+(?:\.\d+)?\s*(?:%|‰|mg|g|kg|ml|l|h|min|s|°c|k|ev|nm|µm|mmol|umol|mol|ppm|fold|x)\b", re.I)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def fold(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def sents(text):
    out = [fold(x) for x in SENT.split(text or "") if fold(x)]
    return out


def kind_of(title):
    t = (title or "").lower()
    for kind, rx in KINDS:
        if re.search(rx, t, re.I):
            return kind
    return "other"


def parse_case(case):
    """归一成 {meta, sections:[{title, kind, paragraphs:[{id,text}]}]}，保留原始章节顺序。"""
    meta = dict(case.get("paper") or {})
    if isinstance(case.get("source"), dict):
        for k in ("source_id", "title", "authors", "year", "doi"):
            if case["source"].get(k) and not meta.get(k):
                meta[k.replace("doi", "doi_or_id")] = case["source"][k]
    sections = []
    raw = case.get("sections")
    if isinstance(raw, list) and raw:
        for i, s in enumerate(raw, 1):
            title = fold(s.get("title") or s.get("heading") or f"Section {i}")
            pars = s.get("paragraphs") or []
            pps = []
            for j, p in enumerate(pars, 1):
                if isinstance(p, str):
                    pid, text = f"s{i}p{j}", p
                else:
                    pid, text = p.get("id") or p.get("paragraph_id") or f"s{i}p{j}", p.get("text") or ""
                if fold(text):
                    pps.append({"id": pid, "text": fold(text)})
            if pps:
                sections.append({"title": title, "kind": kind_of(title), "paragraphs": pps})
    if not sections:
        pars = (case.get("document") or {}).get("paragraphs") or case.get("paragraphs") or []
        cur = None
        for j, p in enumerate(pars, 1):
            if isinstance(p, str):
                p = {"id": f"p{j}", "text": p}
            sec = fold(p.get("section") or "")
            pid = p.get("id") or p.get("paragraph_id") or f"p{j}"
            if not cur or cur["title"] != (sec or cur["title"]):
                cur = {"title": sec or "Body", "kind": kind_of(sec), "paragraphs": []}
                if sec or not sections:
                    sections.append(cur)
            cur["paragraphs"].append({"id": pid, "text": fold(p.get("text") or "")})
    if not sections:
        raise SystemExit("未识别到任何章节或段落（需 sections/paragraphs 字段）")
    return {"meta": meta, "sections": sections}


def first_match(section_sents, rx, limit=2):
    return [s for s in section_sents if rx.search(s)][:limit]


def build_notes(corpus, case_id=""):
    meta, sections = corpus["meta"], corpus["sections"]
    src_id = meta.get("source_id") or "paper-01"
    all_sents = [(sec["title"], p["id"], s) for sec in sections
                 for p in sec["paragraphs"] for s in sents(p["text"])]
    by_kind = {k: [] for k, _ in KINDS}
    for sec in sections:
        by_kind.setdefault(sec["kind"], [])
        for p in sec["paragraphs"]:
            by_kind[sec["kind"]].append((sec["title"], p["id"], sents(p["text"])))

    def pick(kinds, rx=None, limit=2):
        pool = []
        for k in kinds:
            for title, pid, ss in by_kind.get(k, []):
                for s in ss:
                    if rx is None or rx.search(s):
                        pool.append((title, pid, s))
        return pool[:limit]

    q = pick(["abstract", "intro"], QUESTION, 1) or pick(["abstract", "intro"], None, 1) or all_sents[:1]
    data = pick(["data", "method"], DATA_CUE, 2)
    methods = pick(["method"], METHOD_CUE, 2) or pick(["method"], None, 2)
    findings = pick(["result", "conclusion"], RESULT_CUE, 3) or pick(["result", "conclusion"], None, 2)
    limits = pick(["limitation"], None, 2) or [x for x in all_sents if LIMIT_CUE.search(x[2])][:2]

    def txt(items, maxlen=220):
        return " ".join(s for _, _, s in items)[:maxlen] if items else ""

    def loc(title, pid):
        return f"section {title}, paragraph {pid}"

    card = {
        "research_question": txt(q),
        "data": txt(data),
        "methods": txt(methods),
        "findings": txt(findings),
        "limitations": txt(limits),
    }

    section_notes, missing = [], []
    for sec in sections:
        ss = [s for p in sec["paragraphs"] for s in sents(p["text"])]
        purpose = ss[0] if ss else ""
        method = " ".join(first_match(ss, METHOD_CUE, 1)) or ""
        result = " ".join(first_match(ss, RESULT_CUE, 1)) or ""
        concl = " ".join(first_match(ss, CONCL_CUE, 1)) or ""
        pid = sec["paragraphs"][0]["id"] if sec["paragraphs"] else ""
        note = {"section": sec["title"], "purpose": purpose[:200], "method": method[:200],
                "result": result[:200], "conclusion": concl[:200],
                "source_id": src_id, "locator": loc(sec["title"], pid)}
        section_notes.append(note)

    kps, seen = [], set()
    for sec in sections:
        for p in sec["paragraphs"]:
            for s in sents(p["text"]):
                term = None
                m = METRIC.search(s)
                if m:
                    term = fold(m.group(0))
                else:
                    for cand in TERM.finditer(s):
                        w = cand.group(0)
                        if len(w) >= 3 and w.lower() not in {"the", "and", "this", "that", "however", "results"}:
                            term = w
                            break
                if not term:
                    continue
                key = (sec["title"], term.lower())
                if key in seen:
                    continue
                seen.add(key)
                typ = "metric" if METRIC.search(term) or re.search(r"\d", term) else (
                    "method" if METHOD_CUE.search(s) else "concept")
                kps.append({"term": term, "type": typ, "statement": s[:180], "aliases": "",
                            "source_id": src_id, "locator": loc(sec["title"], p["id"])})

    # sources：每条引文摊平成可回链条目，按出现顺序去重
    sources, skeys = [], set()

    for sec in sections:
        for p in sec["paragraphs"]:
            for s in sents(p["text"]):
                key = (src_id, sec["title"], p["id"], s[:60])
                if key in skeys:
                    continue
                skeys.add(key)
                sources.append({"source_id": src_id, "locator": loc(sec["title"], p["id"]),
                                "locator_type": "paragraph", "quote": s[:300],
                                "note": "direct evidence"})

    gaps = []
    for f, label in (("research_question", "研究问题"), ("data", "数据"), ("methods", "方法条件"),
                     ("findings", "主要发现"), ("limitations", "局限")):
        if not card[f]:
            gaps.append(f"论文卡片 {label} 原文未明确表述")

    status = "success" if not gaps else "partial"

    uncertainty = [{"item": g, "reason": "原文未直接给出，未做补写", "action_required": "回原文对应章节确认或联络作者"}
                   for g in gaps] or [{"item": "图表内数值", "reason": "本次输入为文本层，未读图表像素",
                                       "action_required": "如需图表数值请提供 PDF 或表格转录"}]
    changes = [
        {"step": "1", "action": "读取 case.json / task.md", "note": f"识别 {len(sections)} 个章节，source_id={src_id}"},
        {"step": "2", "action": "按章节顺序切句并标注定位", "note": f"共 {len(all_sents)} 句，定位到 section+paragraph"},
        {"step": "3", "action": "抽取论文卡片五字段", "note": "研究问题/数据/方法/发现/局限；缺项显式记录"},
        {"step": "4", "action": "生成章节笔记与知识点", "note": f"{len(section_notes)} 条章节笔记、{len(kps)} 个知识点"},
        {"step": "5", "action": "绑定来源与自查", "note": f"{len(sources)} 条可回链证据；status={status}"},
    ]
    results = {"paper_card": card, "section_notes": section_notes, "knowledge_points": kps,
               "comparison_fields": ["research_question", "methods", "findings", "limitations"]}
    return {"case_id": str(case_id or ""), "status": status, "results": results,
            "sources": sources, "uncertainty": uncertainty, "changes": changes,
            "artifacts": [], "meta": meta}





def main(argv=None):
    ap = argparse.ArgumentParser(description="结构化笔记构建")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--case", required=True)
    b.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        case = load(args.case)
        draft = build_notes(parse_case(case), str(case.get("case_id") or ""))
        draft.pop("meta", None)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
        print(f"sections={len(draft['results']['section_notes'])} "
              f"knowledge_points={len(draft['results']['knowledge_points'])} "
              f"sources={len(draft['sources'])} status={draft['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
