#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""litkg — 证据绑定的文献知识图谱构建器（单文件核心）

只做四件机械事：切句/定位、候选实体、候选关系、证据校验与导出。
语义判断（接受/丢弃/类型纠正/合并否决）由 Agent 按 SKILL.md 完成并写回结论。

用法：
  python3 scripts/kg.py build --case /input/case.json --out /app/output
  python3 scripts/kg.py demo  --out ./out
  python3 scripts/kg.py query --kg ./out/kg.json --expr "entity:TiO2"
"""
import argparse
import csv
import json
import re
import sys
import xml.sax.saxutils as sx
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VERSION = "1.0.0"


# ---------------------------------------------------------------- 词汇与常量
def load_vocab():
    ent = json.loads((ROOT / "vocab" / "entity_types.json").read_text(encoding="utf-8"))
    rel = json.loads((ROOT / "vocab" / "relation_types.json").read_text(encoding="utf-8"))
    return ent, rel


TEXT_KEYS = ("text", "content", "body", "plain_text", "paragraph", "full_text", "value")
PID_KEYS = ("paragraph_id", "paragraph-id", "pid", "jats_id", "id", "@id")
SEC_KEYS = ("section", "sec", "section_title", "heading", "section_name")
META_KEYS = ("doi", "title", "authors", "author", "year", "license", "journal", "publisher", "source_hash", "role")

STOP = {
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "we", "our", "they", "their",
    "study", "paper", "work", "result", "results", "fig", "figure", "table", "eq", "section",
    "of", "and", "or", "in", "on", "at", "to", "for", "with", "by", "as", "from", "than",
}


# ---------------------------------------------------------------- 文本工具
def sp(text, start, end):
    return text[start:end]


def squash(s):
    return re.sub(r"\s+", "", s or "")


def fold(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def norm_label(s):
    s = fold(s).lower()
    s = re.sub(r"[\u2018\u2019\u201c\u201d\"'`]", "", s)
    s = re.sub(r"\s*([\-–—/])\s*", r"\1", s)
    s = re.sub(r"[^\w\u4e00-\u9fa5\-\+/%]", "", s)
    return s.strip("-/")


def sentences(text):
    """返回 [(start, end, sentence)]，按中英文句末与换行切分，避开小数点。"""
    out, n = [], len(text)
    start = 0
    i = 0
    while i < n:
        ch = text[i]
        if ch in "。！？\n":
            end = i + 1
            if end > start and text[start:end].strip():
                out.append((start, end, text[start:end]))
            start = end
        elif ch in ".!?" and i > 0 and text[i - 1].isdigit() and i + 1 < n and text[i + 1].isdigit():
            i += 1
            continue
        elif ch in ".!?":
            end = i + 1
            while end < n and text[end] in " \t":
                end += 1
            if text[start:end].strip():
                out.append((start, end, text[start:end]))
            start = end
            i = end
            continue
        i += 1
    if start < n and text[start:].strip():
        out.append((start, n, text[start:]))
    return out


def locate(quote, text):
    """两级匹配：先空白折叠，再去全部空白。返回 (start, end) 或 None。"""
    if not quote or not text:
        return None
    q = fold(quote)
    if q in text:
        i = text.index(q)
        return (i, i + len(q))
    qs = squash(quote)
    if not qs:
        return None
    ts = squash(text)
    i = ts.find(qs)
    if i < 0:
        return None
    # 映射回原文区间
    j, seen = 0, 0
    start = end = None
    for k, ch in enumerate(text):
        if ch.isspace():
            continue
        if seen == i and start is None:
            start = k
        seen += 1
        if seen == i + len(qs):
            end = k + 1
            break
    if start is None or end is None:
        return None
    return (start, end)


# ---------------------------------------------------------------- 语料装载
def _par(raw, fallback_pid):
    text = ""
    for k in TEXT_KEYS:
        if isinstance(raw.get(k), str) and raw[k].strip():
            text = raw[k]
            break
    if not text:
        return None
    pid, synthetic = None, False
    for k in PID_KEYS:
        v = raw.get(k)
        if isinstance(v, (str, int)) and str(v).strip():
            pid = str(v).strip()
            break
    if not pid:
        pid, synthetic = fallback_pid, True
    section = ""
    for k in SEC_KEYS:
        if isinstance(raw.get(k), str) and raw[k].strip():
            section = raw[k].strip()
            break
    return {"paragraph_id": pid, "section": section, "text": text,
            "pid_synthetic": synthetic, "raw_keys": sorted(raw.keys())}


def _pars_in(doc):
    for key in ("paragraphs", "paragraph", "body", "body_paragraphs"):
        v = doc.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for k2 in ("paragraphs", "items", "body"):
                if isinstance(v.get(k2), list):
                    return v[k2]
    if isinstance(doc.get("sections"), list):
        out = []
        for sec in doc["sections"]:
            if isinstance(sec, dict):
                title = sec.get("title") or sec.get("heading") or ""
                for p in (sec.get("paragraphs") or []):
                    if isinstance(p, dict) and title and not any(p.get(k) for k in SEC_KEYS):
                        p = dict(p, section=title)
                    out.append(p)
        return out
    return None


def _doc_from(obj, idx, meta=None):
    meta = dict(meta or {})
    for k in META_KEYS:
        if k in obj and not isinstance(obj[k], (list, dict)):
            meta.setdefault(k, obj[k])
    if isinstance(obj.get("authors"), list):
        meta["authors"] = obj["authors"]
    pars = _pars_in(obj)
    if pars is None:
        return None
    return {"meta": meta, "paragraphs_raw": [p for p in pars if isinstance(p, dict)]}


def discover(src):
    """把任意形态的 case / material JSON 归一成 papers 列表。"""
    warnings = []
    payload = None
    base = None
    p = Path(src)
    if p.is_dir():
        base = p
        payload = {}
        for name in ("case.json", "material.json", "corpus-manifest.json",
                     "primary-material.json", "secondary-material.json"):
            f = p / name
            if f.exists():
                try:
                    payload[name] = json.loads(f.read_text(encoding="utf-8"))
                except Exception as e:  # noqa
                    warnings.append(f"无法解析 {name}: {e}")
        if not payload:
            raise SystemExit(f"目录 {p} 下没有可识别的 JSON")
    else:
        base = p.parent
        payload = {"case.json": json.loads(p.read_text(encoding="utf-8"))}

    docs = []

    def inherit(meta, extra):
        m = dict(meta)
        for k in META_KEYS:
            if k in extra and not isinstance(extra[k], (list, dict)):
                m.setdefault(k, extra[k])
        if isinstance(extra.get("authors"), list):
            m.setdefault("authors", extra["authors"])
        return m

    def walk(obj, meta):
        if isinstance(obj, list):
            for it in obj:
                walk(it, meta)
            return
        if not isinstance(obj, dict):
            return
        d = _doc_from(obj, len(docs), meta)
        if d:
            docs.append(d)
            return
        child = dict(meta)
        for k in META_KEYS:
            if k in obj and not isinstance(obj[k], (list, dict)):
                child[k] = obj[k]
        if isinstance(obj.get("authors"), list):
            child["authors"] = obj["authors"]
        for key, v in obj.items():
            if isinstance(v, (list, dict)):
                walk(v, child)
            elif isinstance(v, str) and v.lower().endswith(".json") and base:
                f = base / v
                if f.exists():
                    try:
                        walk(json.loads(f.read_text(encoding="utf-8")), {})
                    except Exception as e:  # noqa
                        warnings.append(f"无法解析 {v}: {e}")

    walk(payload, {})
    if not docs:
        raise SystemExit("未从输入中识别到任何段落结构（需含 paragraphs/text 字段）")

    papers = []
    for i, d in enumerate(docs, 1):
        sid = f"P{i}"
        meta = d["meta"]
        title = meta.get("title") or ""
        papers.append({
            "source_id": sid,
            "doi": meta.get("doi") or "",
            "title": title,
            "authors": meta.get("authors") or [],
            "year": meta.get("year") or "",
            "license": meta.get("license") or "",
            "role": meta.get("role") or ("primary" if i == 1 else "secondary"),
            "paragraphs": [x for x in (_par(raw, f"{sid}-p{k:03d}")
                                       for k, raw in enumerate(d["paragraphs_raw"], 1)) if x],
        })
    manifest = payload.get("corpus-manifest.json") or payload.get("corpus_manifest") or {}
    return {"papers": papers, "manifest": manifest, "warnings": warnings}


# ---------------------------------------------------------------- 候选实体
def _clean(s):
    s = fold(s).strip(" ,;:()[]{}<>\"'")
    s = re.sub(r"^(?:the|a|an|our|this|these|those|其|该)\s+", "", s, flags=re.I)
    return s.strip()


def _ok(s, minlen=2):
    return bool(s) and len(s) >= minlen and norm_label(s) not in STOP and not norm_label(s).isdigit()


STOP_TOKENS = {
    "and", "or", "with", "using", "used", "by", "of", "the", "a", "an", "at", "under", "in", "on",
    "to", "for", "than", "more", "less", "which", "that", "is", "are", "was", "were", "shows",
    "show", "outperforms", "compared", "as", "from", "this", "these", "those", "its", "their",
    "our", "we", "while", "but", "however", "reaches", "reported", "measured", "onset",
    "examine", "examines", "examine", "reports", "report", "uses", "use", "found", "showed",
}


def head_phrase(s, max_tokens=4):
    """取 cue 之后的名词短语头：遇到功能词即截断。"""
    toks = [t for t in re.split(r"\s+", fold(s)) if t]
    out = []
    for t in toks[:max_tokens]:
        if t.lower().strip(".,;:()") in STOP_TOKENS:
            break
        out.append(t)
        if t.endswith((",", ";", ":")):
            break
    label = _clean(" ".join(out).rstrip(",;:"))
    return label if _ok(label, 3) else None


def tail_phrase(s, max_tokens=3):
    """取实体标记前的名词短语尾（如 “photoreduction using Cu-doped TiO2 samples” → “Cu-doped TiO2”）。"""
    toks = [t for t in re.split(r"\s+", fold(s)) if t]
    out = []
    for t in reversed(toks):
        if t.lower().strip(".,;:()") in STOP_TOKENS or not re.search(r"[A-Za-z\u4e00-\u9fa5]", t):
            break
        out.append(t)
        if len(out) >= max_tokens:
            break
    label = _clean(" ".join(reversed(out)).rstrip(",;:"))
    return label if _ok(label, 3) else None


PATTERNS = [
    ("researcher", re.compile(r"([A-Z][A-Za-z\-]{1,20}(?:\s+[A-Z][A-Za-z\-]{1,20})?)\s+et\s+al\.?")),
    ("researcher", re.compile(r"([\u4e00-\u9fa5]{2,4})(?:等人|等)")),
    ("method", re.compile(r"(?:using|used|by|via|based on|employ\w*|adopt\w*|applied|采用|使用|基于|通过|利用)\s+"
                          r"([A-Za-z0-9][\w\-\+/]{1,24}(?:\s+[A-Za-z0-9][\w\-\+/]{1,18}){0,3})")),
    ("material", re.compile(r"([A-Za-z0-9][\w\-\+\(\)]{1,24}(?:\s+[A-Za-z0-9][\w\-\+\(\)]{1,18}){0,3})\s+"
                            r"(?:samples?|powders?|films?|electrodes?|catalysts?|nanoparticles?|solutions?|"
                            r"references?|systems?|样品|材料|薄膜|电极|催化剂|纳米颗粒)")),
    ("metric", re.compile(r"([0-9]+(?:\.[0-9]+)?\s*%)\s*(?:of\s+)?(?:[a-z]+\s+){0,2}"
                          r"(?:selectivity|yield|efficiency|conversion|rate|产率|效率|选择性|转化率)", re.I)),
    ("metric", re.compile(r"(?:accuracy|precision|recall|f1|auc|rmse|mae|yield|efficiency|selectivity|"
                          r"conversion|rate|产率|效率|选择性|转化率|准确率)[^0-9%]{0,14}"
                          r"([0-9]+(?:\.[0-9]+)?(?:\s*±\s*[0-9.]+)?"
                          r"(?:\s*(?:umol\s*g-1\s*h-1|mmol\s*g-1\s*h-1|mol\s*g-1\s*h-1|g-1\s*h-1|%|‰|umol|mmol|mol|mg|g|kg|ml|l|h|min|s|k|ev|nm|µm|bar|mpa|ppm))*)", re.I)),
    ("task", re.compile(r"(?:task of|benchmarked on|application of|用于|面向|任务)\s*"
                        r"([A-Za-z0-9][\w\-\+ ]{2,28}|[\u4e00-\u9fa5]{2,12})")),
    ("dataset", re.compile(r"(?:dataset|corpus)\s+(?:called\s+|named\s+|名为)?([A-Za-z0-9][\w\-\+ ]{2,28})")),
    ("model", re.compile(r"(?:model|network|classifier)\s+(?:called\s+|named\s+)?([A-Z][\w\-\+]{1,24})")),
    ("condition", re.compile(r"((?:at|under|in the presence of|当|在)\s*[0-9]+(?:\.[0-9]+)?\s*"
                             r"(?:°c|k|mpa|bar|%|h|min|ph\s*[0-9.]+))", re.I)),
]

CONCL_CUE = re.compile(r"(?:(?:we|our results?)\s+(?:conclude|find|show|observe)|results? (?:show|indicate|suggest)|"
                       r"these results|表明|说明|可以认为|因此|综上)", re.I)


def extract_candidates(paper):
    out = []
    for par in paper["paragraphs"]:
        text = par["text"]
        for s, e, sent in sentences(text):
            for typ, rx in PATTERNS:
                for m in rx.finditer(sent):
                    raw = m.group(1)
                    if typ == "material":
                        label = tail_phrase(raw)
                        marker = fold(m.group(0)).split()[-1] if fold(m.group(0)).split() else ""
                        if label and marker and marker.lower().rstrip("s") not in norm_label(label):
                            merged_label = f"{label} {marker}"
                            if merged_label in fold(m.group(0)):
                                label = merged_label
                    elif typ in ("method", "task", "dataset", "model"):
                        label = head_phrase(raw)
                        if typ == "method" and label and label.split()[-1].lower().rstrip("s") in {
                                "sample", "catalyst", "powder", "film", "electrode", "nanoparticle", "solution"}:
                            label = None
                    else:
                        label = _clean(raw)
                    if not label or not _ok(label):
                        continue
                    # 裁剪后的标签必须重新定位真实偏移（以整段匹配为基准），否则关系方向会错
                    off = m.group(0).find(label)
                    if off < 0:
                        continue
                    qs = s + m.start(0) + off
                    qe = qs + len(label)
                    out.append({
                        "type": typ, "label": label, "source_id": paper["source_id"],
                        "paragraph_id": par["paragraph_id"], "section": par["section"],
                        "quote": fold(sent)[:400], "q_start": qs, "q_end": qe,
                        "surface_span": text[qs:qe], "sentence": fold(sent),
                        "attribution": "cited_claim" if ("et al" in sent or "等人" in sent) else "author_claim",
                        "sentence_start": s,
                    })
            if CONCL_CUE.search(sent):
                lab = fold(sent)
                lab = lab[:140] + ("…" if len(lab) > 140 else "")
                out.append({
                    "type": "conclusion", "label": lab, "source_id": paper["source_id"],
                    "paragraph_id": par["paragraph_id"], "section": par["section"],
                    "quote": fold(sent)[:400], "q_start": s, "q_end": e,
                    "surface_span": fold(sent)[:140], "sentence": fold(sent),
                    "attribution": "cited_claim" if ("et al" in sent or "等人" in sent) else "author_claim",
                    "sentence_start": s,
                })
    # 去重：同篇同段同类型同标签只留首个
    seen, uniq = set(), []
    for c in out:
        k = (c["source_id"], c["paragraph_id"], c["type"], norm_label(c["label"]))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)
    return uniq


# ---------------------------------------------------------------- 实体对齐
def _is_instance(node, ent_vocab):
    """按实例标记判断：带样品/批次/数值条件表述的节点不得跨篇合并。"""
    lab = node["label"].lower()
    markers = ent_vocab.get("instance_markers") or []
    if any(mk.lower() in lab for mk in markers):
        return True
    if node["type"] in ("dataset", "model", "metric", "condition", "material"):
        return True
    return False


def cluster_candidates(cands, ent_vocab):
    """同篇同类型同规范标签聚合；跨篇是否合并交由 merge_decision。"""
    groups, order = {}, []
    for c in cands:
        key = (c["type"], norm_label(c["label"]))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)
    return [groups[k] for k in order]


def merge_decision(group, ent_vocab):
    """返回 (merge: bool, basis: str, rule: str)。"""
    types = {c["type"] for c in group}
    if len(types) > 1:
        return False, "实体类型冲突（同名不同类型），不合并", "R-TYPE"
    srcs = {c["source_id"] for c in group}
    labels = {c["label"] for c in group}
    if len(srcs) > 1:
        if len(labels) > 1:
            return False, "跨篇同类型但表述不同，缺同物依据，保留待复核", "R-SURFACE"
        node = {"label": group[0]["label"], "type": group[0]["type"]}
        if _is_instance(node, ent_vocab):
            return False, "跨篇实例级实体（材料/样品/数据集/模型/指标/条件），未做同物判定，不得合并", "R-INSTANCE"
        return True, "跨篇通用类型术语（方法/任务/机构等），按类型+规范形式合并", "R-GENERIC"
    if len(labels) > 1:
        norms = [norm_label(x) for x in labels]
        if any(a in b or b in a for a in norms for b in norms if a != b):
            return True, "同篇异写（规范化后存在包含关系），合并", "R-NORM"
        return False, "同篇不同表述，未证同物，保留待复核", "R-SURFACE"
    return True, "同篇同类型同表述，合并为一个节点", "R-SAME"


# ---------------------------------------------------------------- 关系抽取
CUES = [
    ("outperforms", re.compile(r"outperform\w*|better than|higher than|surpass\w*|优于|高于|超过", re.I), "fwd", True),
    ("compared_with", re.compile(r"compared (?:with|to|against)|relative to|与[^，。]{0,10}相比|对比", re.I), "sym", True),
    ("uses", re.compile(r"using|used|based on|via|employ\w*|adopt\w*|applied|采用|使用|基于|通过|利用", re.I), "fwd", False),
    ("evaluates_on", re.compile(r"evaluated on|tested on|benchmarked on|在[^，。]{0,10}上(?:评测|测试)", re.I), "fwd", False),
    ("measured_by", re.compile(r"measured (?:by|as)|reported (?:as|a|an)|以[^，。]{0,8}(?:衡量|评价)", re.I), "fwd", False),
    ("supports", re.compile(r"support\w*|consistent with|in line with|支持|与[^，。]{0,8}一致", re.I), "fwd", False),
    ("contradicts", re.compile(r"however|in contrast|contrary|contradict\w*|矛盾|相反|不一致", re.I), "fwd", False),
    ("reported_by", re.compile(r"et al\.?|reported by|according to|等人?(?:报道|报告|发现)", re.I), "fwd", False),
]
OBJ_TYPES = {
    "uses": {"method", "material", "condition"},
    "evaluates_on": {"task", "dataset"},
    "measured_by": {"metric"},
    "supports": {"conclusion"},
    "contradicts": {"conclusion", "metric"},
    "reported_by": {"conclusion", "metric", "method"},
    "outperforms": {"method", "material", "model", "metric"},
    "compared_with": {"method", "material", "model", "metric"},
}
COND_RX = re.compile(r"((?:at|under|in the presence of|当|在)\s*[0-9]+(?:\.[0-9]+)?\s*"
                     r"(?:°c|k|mpa|bar|%|h|min|ph\s*[0-9.]+))", re.I)


def extract_relations(cand_by_par):
    """同句共现 + 线索词 → 候选关系；方向由线索词位置决定。"""
    edges = []
    for (sid, pid), group in cand_by_par.items():
        ordered = sorted(group, key=lambda c: c["sentence_start"])
        by_sent = {}
        for c in ordered:
            by_sent.setdefault(c["sentence_start"], []).append(c)
        for sstart, cs in by_sent.items():
            sent = cs[0]["sentence"]
            for rel, rx, direction, needs_cond in CUES:
                for m in rx.finditer(sent):
                    sbase = cs[0]["sentence_start"]
                    before = [dict(c, pos=c["q_start"] - sbase) for c in cs
                              if c["q_start"] - sbase <= m.start()]
                    after = [dict(c, pos=c["q_start"] - sbase) for c in cs
                             if c["q_start"] - sbase >= m.end()]

                    def pick(pool, rel_type):
                        if not pool:
                            return None
                        ordered = sorted(pool, key=lambda c: c["pos"])
                        if rel_type in ("outperforms", "compared_with"):
                            for c in ordered:
                                if c["type"] in ("method", "material", "model"):
                                    return c
                        return ordered[0]

                    subj = pick(before, rel)
                    obj = pick(after, rel)
                    if rel == "reported_by" and obj and subj and obj["type"] == "conclusion":
                        pass
                    if not subj or not obj or norm_label(subj["label"]) == norm_label(obj["label"]):
                        continue
                    if subj["type"] == obj["type"] and rel in ("uses", "evaluates_on", "measured_by", "compared_with"):
                        continue  # 同类型实体之间的“使用/比较”缺乏语义，交由人工复核而非自动建边
                    allowed = OBJ_TYPES.get(rel)
                    if allowed and obj["type"] not in allowed:
                        # 交换一次，兼容“以 X 衡量 Y”等倒装
                        if subj["type"] in allowed:
                            subj, obj = obj, subj
                        else:
                            continue
                    conds = COND_RX.findall(sent)
                    cond = "; ".join(fold(c) for c in conds)
                    attr = "cited_claim" if re.search(r"et al|reported by|according to|等人", sent) else "author_claim"
                    edges.append({
                        "type": rel, "source_id": sid, "paragraph_id": pid,
                        "subject_label": subj["label"], "subject_type": subj["type"],
                        "object_label": obj["label"], "object_type": obj["type"],
                        "direction": "symmetric" if direction == "sym" else "subject_to_object",
                        "conditions": cond, "attribution": attr,
                        "quote": sent, "q_start": sstart, "q_end": sstart + len(sent),
                        "strength": "direct" if (abs(subj["q_start"] - obj["q_start"]) < len(sent)) else "indirect",
                        "cue": fold(m.group(0)),
                        "needs_condition": bool(needs_cond),
                    })
    # 去重
    seen, uniq = set(), []
    for e in edges:
        k = (e["type"], norm_label(e["subject_label"]), norm_label(e["object_label"]), e["paragraph_id"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(e)
    return uniq


# ---------------------------------------------------------------- 建图
def build_graph(corpus, ent_vocab, rel_vocab):
    papers = corpus["papers"]
    cands = []
    for p in papers:
        cands.extend(extract_candidates(p))

    groups = cluster_candidates(cands, ent_vocab)
    nodes, merges = [], []
    idx = {}
    nseq = 0
    for g in groups:
        merge, basis, rule = merge_decision(g, ent_vocab)
        if merge:
            nseq += 1
            nid = f"n{nseq:03d}"
            rep = g[0]
            node = {
                "id": nid, "type": rep["type"], "label": rep["label"],
                "aliases": sorted({c["label"] for c in g} - {rep["label"]}),
                "source_ids": sorted({c["source_id"] for c in g}),
                "evidence": [{"source_id": c["source_id"], "paragraph_id": c["paragraph_id"],
                              "section": c["section"], "quote": c["quote"][:300],
                              "attribution": c["attribution"], "strength": "direct",
                              "q_start": c["q_start"], "q_end": c["q_end"]} for c in g],
                "merge_basis": basis, "merge_rule": rule,
            }
            nodes.append(node)
            for c in g:
                idx[(c["source_id"], c["paragraph_id"], c["type"], norm_label(c["label"]))] = nid
            for c in g:
                merges.append({"decision": "merged", "node_id": nid, "label": c["label"],
                               "type": c["type"], "source_id": c["source_id"],
                               "paragraph_id": c["paragraph_id"], "basis": basis, "rule": rule})
        else:
            # 不合并：每篇各建一个节点（同篇同表述的多段证据归到同一节点，避免重复节点）
            by_src = {}
            for c in g:
                by_src.setdefault(c["source_id"], []).append(c)
            for sid, cs in by_src.items():
                nseq += 1
                nid = f"n{nseq:03d}"
                rep = cs[0]
                nodes.append({
                    "id": nid, "type": rep["type"], "label": rep["label"], "aliases": [],
                    "source_ids": [sid],
                    "evidence": [{"source_id": c["source_id"], "paragraph_id": c["paragraph_id"],
                                  "section": c["section"], "quote": c["quote"][:300],
                                  "attribution": c["attribution"], "strength": "direct",
                                  "q_start": c["q_start"], "q_end": c["q_end"]} for c in cs],
                    "merge_basis": basis, "merge_rule": rule,
                })
                for c in cs:
                    idx[(c["source_id"], c["paragraph_id"], c["type"], norm_label(c["label"]))] = nid
                    merges.append({"decision": "not_merged", "node_id": nid, "label": c["label"],
                                   "type": c["type"], "source_id": c["source_id"],
                                   "paragraph_id": c["paragraph_id"], "basis": basis, "rule": rule})

    by_par = {}
    for p in papers:
        for c in cands:
            if c["source_id"] == p["source_id"]:
                by_par.setdefault((c["source_id"], c["paragraph_id"]), []).append(c)
    raw_edges = extract_relations(by_par)

    edges, eseq, dropped = [], 0, 0
    for e in raw_edges:
        sid = e["source_id"]
        s = idx.get((sid, e["paragraph_id"], e["subject_type"], norm_label(e["subject_label"])))
        o = idx.get((sid, e["paragraph_id"], e["object_type"], norm_label(e["object_label"])))
        if not s or not o or s == o:
            dropped += 1
            continue
        eseq += 1
        edges.append({
            "id": f"e{eseq:03d}", "type": e["type"],
            "subject": s, "object": o,
            "subject_label": e["subject_label"], "object_label": e["object_label"],
            "direction": e["direction"], "conditions": e["conditions"],
            "attribution": e["attribution"], "strength": e["strength"], "cue": e["cue"],
            "evidence": [{"source_id": sid, "paragraph_id": e["paragraph_id"],
                          "quote": e["quote"][:300], "q_start": e["q_start"], "q_end": e["q_end"]}],
        })

    conflicts = detect_conflicts(nodes, edges, papers)
    return {
        "kg_version": VERSION,
        "built_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "papers": [{k: v for k, v in p.items() if k != "paragraphs"} | {"paragraph_count": len(p["paragraphs"]),
                                                                      "paragraph_ids": [x["paragraph_id"] for x in p["paragraphs"]]}
                   for p in papers],
        "nodes": nodes, "edges": edges,
        "merges": merges, "conflicts": conflicts,
        "stats": {"papers": len(papers), "paragraphs": sum(len(p["paragraphs"]) for p in papers),
                  "nodes": len(nodes), "edges": len(edges),
                  "edges_dropped_unmapped": dropped,
                  "candidates": len(cands)},
        "notes": {"paragraph_id_note": "段落 ID 取原文 JATS 段落编号；若输入未给 ID 则标记 pid_synthetic。",
                  "page_note": "本包不含 PDF，节点/边不写页码，禁止把自建分页称作原 PDF 页。"},
    }


def detect_conflicts(nodes, edges, papers):
    """跨篇数值不同 → 冲突记录；同篇不同结论 → 冲突记录。"""
    out = []
    metrics = {}
    for n in nodes:
        if n["type"] != "metric":
            continue
        for ev in n["evidence"]:
            metrics.setdefault(n["label"], {}).setdefault(ev["source_id"], []).append(ev["quote"])
    for lab, by_src in metrics.items():
        if len(by_src) > 1:
            out.append({"kind": "metric_value_divergence", "label": lab,
                        "claims": [{"source_id": s, "paragraph_id": "", "quote": q[0][:220]}
                                   for s, q in by_src.items()],
                        "resolution": "kept_separate",
                        "basis": "跨篇同一指标名不代表同一实验条件/样品，数值不合并、不取均值"})
    for e in edges:
        if e["type"] == "contradicts":
            out.append({"kind": "stated_contradiction", "edge_id": e["id"],
                        "claims": [{"source_id": e["evidence"][0]["source_id"],
                                    "paragraph_id": e["evidence"][0]["paragraph_id"],
                                    "quote": e["evidence"][0]["quote"]}],
                        "resolution": "kept_both", "basis": "原文明确出现相反表述，保留双方并记录条件"})
    return out


# ---------------------------------------------------------------- 质检
def qc(graph, corpus):
    issues = []
    texts = {}
    for p in corpus["papers"]:
        for par in p["paragraphs"]:
            texts[(p["source_id"], par["paragraph_id"])] = par["text"]
    node_ids = {n["id"] for n in graph["nodes"]}
    for n in graph["nodes"]:
        if not n["evidence"]:
            issues.append({"code": "K001", "level": "fail", "target": n["id"], "msg": "节点缺证据"})
        for ev in n["evidence"]:
            t = texts.get((ev["source_id"], ev["paragraph_id"]))
            if t is None:
                issues.append({"code": "K002", "level": "fail", "target": n["id"], "msg": "证据指向不存在的段落"})
            elif locate(ev["quote"][:120], t) is None:
                issues.append({"code": "K003", "level": "fail", "target": n["id"], "msg": "引文无法在段落定位"})
            if len(ev["quote"]) < 12:
                issues.append({"code": "K004", "level": "warn", "target": n["id"], "msg": "引文过短，不足复核"})
    for e in graph["edges"]:
        if e["subject"] not in node_ids or e["object"] not in node_ids:
            issues.append({"code": "K005", "level": "fail", "target": e["id"], "msg": "边端点不存在"})
        if e["type"] not in ("uses", "uses_material", "evaluates_on", "measured_by", "outperforms",
                             "compared_with", "supports", "contradicts", "reported_by",
                             "derived_from", "mentions"):
            issues.append({"code": "K006", "level": "fail", "target": e["id"], "msg": "关系类型不在词表"})
        if e["type"] in ("outperforms", "compared_with") and not e["conditions"]:
            issues.append({"code": "K007", "level": "warn", "target": e["id"], "msg": "比较类关系缺条件"})
        ev = e["evidence"][0]
        t = texts.get((ev["source_id"], ev["paragraph_id"]))
        if t is None or locate(ev["quote"][:120], t) is None:
            issues.append({"code": "K008", "level": "fail", "target": e["id"], "msg": "边引文无法定位"})
    for n in graph["nodes"]:
        if n["merge_rule"] == "R-INSTANCE" and len(n["source_ids"]) > 1:
            issues.append({"code": "K009", "level": "fail", "target": n["id"], "msg": "跨篇实例级实体被合并"})
    for p in corpus["papers"]:
        if p["paragraphs"] and any(x["pid_synthetic"] for x in p["paragraphs"]):
            issues.append({"code": "K010", "level": "warn", "target": p["source_id"],
                           "msg": "输入未给 JATS 段落 ID，已按顺序生成并在 result 中标注"})
    for c in graph["conflicts"]:
        if c["resolution"] == "merged":
            issues.append({"code": "K011", "level": "fail", "target": c["label"], "msg": "冲突被错误合并"})
    for e in graph["edges"]:
        if e["strength"] == "indirect" and e["type"] in ("outperforms", "contradicts"):
            issues.append({"code": "K012", "level": "warn", "target": e["id"], "msg": "结论性关系用了间接证据"})
    summary = {"total": len(issues),
               "fail": sum(1 for i in issues if i["level"] == "fail"),
               "warn": sum(1 for i in issues if i["level"] == "warn")}
    return {"issues": issues, "summary": summary}


# ---------------------------------------------------------------- 查询
def _node_view(graph, n):
    return {"id": n["id"], "type": n["type"], "label": n["label"], "aliases": n["aliases"],
            "source_ids": n["source_ids"], "merge_basis": n["merge_basis"],
            "evidence": n["evidence"]}


def q_entity(graph, term):
    hits = [n for n in graph["nodes"] if norm_label(term) in
            {norm_label(n["label"])} | {norm_label(a) for a in n["aliases"]}]
    rows, ev = [], []
    for n in hits:
        ev.extend(n["evidence"])
        for e in graph["edges"]:
            if e["subject"] == n["id"] or e["object"] == n["id"]:
                other = e["object"] if e["subject"] == n["id"] else e["subject"]
                ol = next((x["label"] for x in graph["nodes"] if x["id"] == other), other)
                rows.append({"edge_id": e["id"], "relation": e["type"],
                             "from": n["label"], "to": ol, "direction": e["direction"],
                             "conditions": e["conditions"], "source_id": e["evidence"][0]["source_id"],
                             "paragraph_id": e["evidence"][0]["paragraph_id"],
                             "quote": e["evidence"][0]["quote"][:180]})
    return {"query": f"entity:{term}", "matched_nodes": [_node_view(graph, n) for n in hits],
            "rows": rows, "evidence": ev, "undetermined": [] if hits else ["图谱中无该实体，可能未覆盖或表述不同"]}


def q_relation(graph, rel, limit=40):
    rows = []
    for e in graph["edges"]:
        if e["type"] != rel:
            continue
        sl = next((n["label"] for n in graph["nodes"] if n["id"] == e["subject"]), e["subject_label"])
        ol = next((n["label"] for n in graph["nodes"] if n["id"] == e["object"]), e["object_label"])
        rows.append({"edge_id": e["id"], "from": sl, "to": ol, "direction": e["direction"],
                     "conditions": e["conditions"] or "(未报告条件)",
                     "attribution": e["attribution"], "strength": e["strength"],
                     "source_id": e["evidence"][0]["source_id"],
                     "paragraph_id": e["evidence"][0]["paragraph_id"],
                     "quote": e["evidence"][0]["quote"][:180]})
    return {"query": f"relation:{rel}", "rows": rows[:limit],
            "undetermined": [] if rows else [f"图谱中没有 {rel} 关系的直接证据"]}


def q_cross(graph):
    rows = []
    for n in graph["nodes"]:
        if len(n["source_ids"]) > 1:
            rows.append({"kind": "merged_across_papers", "node_id": n["id"], "label": n["label"],
                         "type": n["type"], "source_ids": n["source_ids"],
                         "basis": n["merge_basis"], "rule": n["merge_rule"]})
    for m in graph["merges"]:
        if m["decision"] == "not_merged":
            rows.append({"kind": "kept_separate", "node_id": m["node_id"], "label": m["label"],
                         "type": m["type"], "source_id": m["source_id"], "basis": m["basis"]})
    for c in graph["conflicts"]:
        rows.append({"kind": "conflict", "label": c["label"], "resolution": c["resolution"],
                     "basis": c["basis"], "claims": c.get("claims", [])})
    return {"query": "cross_paper_alignment", "rows": rows,
            "undetermined": [r["label"] for r in rows if r["kind"] == "kept_separate"][:10]}


def q_audit(graph, qcres):
    fails = [i for i in qcres["issues"] if i["level"] == "fail"]
    return {"query": "evidence_audit", "rows": fails,
            "summary": qcres["summary"], "undetermined": [] if not fails else ["存在不可复核证据，需回原文修正"]}


def run_queries(graph, qcres, terms):
    out = [q_entity(graph, t) for t in terms]
    out.append(q_relation(graph, "outperforms"))
    out.append(q_cross(graph))
    out.append(q_audit(graph, qcres))
    return out


def pick_query_terms(graph):
    """优先挑跨篇通用实体，其次挑证据最多的节点。"""
    multi = [n for n in graph["nodes"] if len(n["source_ids"]) > 1]
    pool = multi or sorted(graph["nodes"], key=lambda n: -len(n["evidence"]))
    labels = []
    for n in pool:
        if norm_label(n["label"]) not in {norm_label(x) for x in labels}:
            labels.append(n["label"])
        if len(labels) >= 2:
            break
    return labels


# ---------------------------------------------------------------- 导出
def export_all(graph, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    files = {}
    kg_path = outdir / "kg.json"
    kg_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    files["kg"] = str(kg_path)

    with (outdir / "nodes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "type", "label", "aliases", "source_ids", "merge_basis", "paragraph_ids", "quote"])
        for n in graph["nodes"]:
            w.writerow([n["id"], n["type"], n["label"], "|".join(n["aliases"]), "|".join(n["source_ids"]),
                        n["merge_basis"], "|".join(e["paragraph_id"] for e in n["evidence"]),
                        n["evidence"][0]["quote"][:120]])
    files["nodes_csv"] = str(outdir / "nodes.csv")

    with (outdir / "edges.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["edge_id", "relation", "subject", "object", "direction", "conditions",
                    "attribution", "strength", "source_id", "paragraph_id", "quote"])
        for e in graph["edges"]:
            w.writerow([e["id"], e["type"], e["subject"], e["object"], e["direction"], e["conditions"],
                        e["attribution"], e["strength"], e["evidence"][0]["source_id"],
                        e["evidence"][0]["paragraph_id"], e["evidence"][0]["quote"][:160]])
    files["edges_csv"] = str(outdir / "edges.csv")

    gml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
           '  <key id="t" for="node" attr.name="type" attr.type="string"/>',
           '  <key id="s" for="node" attr.name="sources" attr.type="string"/>',
           '  <key id="r" for="edge" attr.name="relation" attr.type="string"/>',
           '  <graph id="litkg" edgedefault="directed">']
    for n in graph["nodes"]:
        gml.append(f'    <node id="{n["id"]}"><data key="t">{sx.escape(n["type"])}</data>'
                   f'<data key="s">{sx.escape("|".join(n["source_ids"]))}</data>'
                   f'<data key="label">{sx.escape(n["label"])}</data></node>')
    for e in graph["edges"]:
        gml.append(f'    <edge id="{e["id"]}" source="{e["subject"]}" target="{e["object"]}">'
                   f'<data key="r">{sx.escape(e["type"])}</data></edge>')
    gml += ["  </graph>", "</graphml>"]
    (outdir / "kg.graphml").write_text("\n".join(gml), encoding="utf-8")
    files["graphml"] = str(outdir / "kg.graphml")

    cypher = ["// litkg export — 可直接导入 Neo4j", "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;"]
    for n in graph["nodes"]:
        cypher.append('MERGE (n:Entity {id: "%s"}) SET n.label = "%s", n.type = "%s", n.sources = "%s";'
                      % (n["id"], n["label"].replace('"', "'"), n["type"], "|".join(n["source_ids"])))
    for e in graph["edges"]:
        cypher.append('MATCH (a:Entity {id: "%s"}), (b:Entity {id: "%s"}) MERGE (a)-[:%s {evidence_paragraph: "%s"}]->(b);'
                      % (e["subject"], e["object"], e["type"].upper(),
                         e["evidence"][0]["paragraph_id"].replace('"', "'")))
    (outdir / "kg.cypher").write_text("\n".join(cypher), encoding="utf-8")
    files["cypher"] = str(outdir / "kg.cypher")

    rows = "".join(
        f"<tr><td>{sx.escape(n['id'])}</td><td>{sx.escape(n['type'])}</td>"
        f"<td>{sx.escape(n['label'])}</td><td>{sx.escape('|'.join(n['source_ids']))}</td>"
        f"<td>{sx.escape(n['evidence'][0]['paragraph_id'])}</td>"
        f"<td>{sx.escape(n['evidence'][0]['quote'][:110])}</td></tr>"
        for n in graph["nodes"])
    erows = "".join(
        f"<tr><td>{sx.escape(e['id'])}</td><td>{sx.escape(e['type'])}</td>"
        f"<td>{sx.escape(e['subject'])}</td><td>{sx.escape(e['object'])}</td>"
        f"<td>{sx.escape(e['conditions'] or '—')}</td>"
        f"<td>{sx.escape(e['evidence'][0]['source_id'])}/{sx.escape(e['evidence'][0]['paragraph_id'])}</td>"
        f"<td>{sx.escape(e['evidence'][0]['quote'][:110])}</td></tr>"
        for e in graph["edges"])
    html = f"""<!doctype html><meta charset="utf-8"><title>litkg — {sx.escape(graph['kg_version'])}</title>
<style>body{{font:14px/1.5 -apple-system,Segoe UI,sans-serif;margin:24px}}table{{border-collapse:collapse;width:100%;margin:12px 0}}
th,td{{border:1px solid #ddd;padding:4px 6px;text-align:left}}th{{background:#f6f6f6}}</style>
<h1>文献知识图谱（{graph['stats']['nodes']} 节点 / {graph['stats']['edges']} 边）</h1>
<p>论文：{", ".join(sx.escape(p['source_id'] + " " + (p['title'] or '')) for p in graph['papers'])}</p>
<h2>节点</h2><table><tr><th>id</th><th>type</th><th>label</th><th>sources</th><th>paragraph</th><th>quote</th></tr>{rows}</table>
<h2>关系</h2><table><tr><th>id</th><th>relation</th><th>subject</th><th>object</th><th>conditions</th><th>source/paragraph</th><th>quote</th></tr>{erows}</table>
"""
    (outdir / "kg.html").write_text(html, encoding="utf-8")
    files["html"] = str(outdir / "kg.html")
    return files


# ---------------------------------------------------------------- Agent 补丁
def apply_patch(graph, patch, corpus):
    """把 Agent 语义层补的节点/边合并进图，逐条校验引文可定位。"""
    texts = {(p["source_id"], par["paragraph_id"]): par["text"]
             for p in corpus["papers"] for par in p["paragraphs"]}
    report = {"nodes_added": [], "edges_added": [], "rejected": []}
    nseq = max([int(n["id"][1:]) for n in graph["nodes"]] or [0])
    eseq = max([int(e["id"][1:]) for e in graph["edges"]] or [0])
    node_ids = {n["id"] for n in graph["nodes"]}
    label2id = {norm_label(n["label"]): n["id"] for n in graph["nodes"]}

    def ev_ok(evs):
        if not evs:
            return False, "缺证据"
        for ev in evs:
            t = texts.get((ev.get("source_id"), ev.get("paragraph_id")))
            if t is None:
                return False, f"段落不存在 {ev.get('source_id')}/{ev.get('paragraph_id')}"
            if locate(ev.get("quote", "")[:160], t) is None:
                return False, f"引文无法定位：{ev.get('quote', '')[:40]}"
        return True, ""

    for item in patch.get("nodes", []):
        ok, why = ev_ok(item.get("evidence"))
        if not ok:
            report["rejected"].append({"kind": "node", "label": item.get("label"), "reason": why})
            continue
        nseq += 1
        nid = item.get("id") or f"n{nseq:03d}"
        if nid in node_ids:
            report["rejected"].append({"kind": "node", "label": item.get("label"), "reason": "id 已存在"})
            continue
        graph["nodes"].append({
            "id": nid, "type": item["type"], "label": item["label"], "aliases": item.get("aliases", []),
            "source_ids": sorted({e["source_id"] for e in item["evidence"]}),
            "evidence": [{"source_id": e["source_id"], "paragraph_id": e["paragraph_id"],
                          "section": e.get("section", ""), "quote": e["quote"][:300],
                          "attribution": e.get("attribution", "author_claim"),
                          "strength": e.get("strength", "direct")} for e in item["evidence"]],
            "merge_basis": item.get("merge_basis", "Agent 依据原文补充，证据已机械校验"),
            "merge_rule": "R-AGENT",
        })
        node_ids.add(nid)
        label2id[norm_label(item["label"])] = nid
        report["nodes_added"].append(nid)

    for item in patch.get("edges", []):
        s = item.get("subject") or label2id.get(norm_label(item.get("subject_label", "")))
        o = item.get("object") or label2id.get(norm_label(item.get("object_label", "")))
        if not s or not o or s not in node_ids or o not in node_ids:
            report["rejected"].append({"kind": "edge", "label": f"{item.get('subject_label')}->{item.get('object_label')}",
                                       "reason": "端点不存在"})
            continue
        ok, why = ev_ok(item.get("evidence"))
        if not ok:
            report["rejected"].append({"kind": "edge", "label": f"{s}->{o}", "reason": why})
            continue
        eseq += 1
        eid = item.get("id") or f"e{eseq:03d}"
        graph["edges"].append({
            "id": eid, "type": item["type"], "subject": s, "object": o,
            "subject_label": next(n["label"] for n in graph["nodes"] if n["id"] == s),
            "object_label": next(n["label"] for n in graph["nodes"] if n["id"] == o),
            "direction": item.get("direction", "subject_to_object"),
            "conditions": item.get("conditions", ""), "attribution": item.get("attribution", "author_claim"),
            "strength": item.get("strength", "direct"), "cue": item.get("cue", "(agent)"),
            "evidence": [{"source_id": e["source_id"], "paragraph_id": e["paragraph_id"],
                          "quote": e["quote"][:300]} for e in item["evidence"]],
        })
        report["edges_added"].append(eid)

    graph["stats"]["nodes"] = len(graph["nodes"])
    graph["stats"]["edges"] = len(graph["edges"])
    return report


def patch_cmd(kg_path, patch_path, corpus_src):
    graph = json.loads(Path(kg_path).read_text(encoding="utf-8"))
    patch = json.loads(Path(patch_path).read_text(encoding="utf-8"))
    corpus = discover(corpus_src)
    report = apply_patch(graph, patch, corpus)
    ent, rel = load_vocab()
    qcres = qc(graph, corpus)
    out = Path(kg_path).with_name("kg.patched.json")
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"patched": str(out), "report": report, "qc": qcres["summary"]},
                     ensure_ascii=False, indent=2))
    return out


# ---------------------------------------------------------------- 主流程
DEFAULT_SYNTH = ROOT / "examples" / "corpus.synthetic.json"


def build(case, outdir, case_id=None):
    corpus = discover(case)
    ent, rel = load_vocab()
    graph = build_graph(corpus, ent, rel)
    qcres = qc(graph, corpus)
    queries = run_queries(graph, qcres, pick_query_terms(graph) or ["(空)"])
    files = export_all(graph, outdir)
    qpath = Path(outdir) / "queries.json"
    qpath.write_text(json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8")
    files["queries"] = str(qpath)

    status = "success"
    if qcres["summary"]["fail"]:
        status = "partial"
    if not graph["nodes"]:
        status = "unable_to_determine"
    limit_notes = []
    if any(p.get("paragraphs") and any(x["pid_synthetic"] for x in p["paragraphs"]) for p in corpus["papers"]):
        limit_notes.append("输入未提供 JATS 段落 ID，段落 ID 由本工具按顺序生成并已标记 pid_synthetic。")
    limit_notes.append("本包不含 PDF 页码与图像附件；节点/边不写页码，亦不推断图表数值。")
    if corpus["warnings"]:
        limit_notes.extend(corpus["warnings"])

    result = {
        "case_id": case_id or "",
        "skill": {"name": "litkg-builder", "version": VERSION},
        "status": status,
        "input_summary": {"papers": [{"source_id": p["source_id"], "doi": p["doi"], "title": p["title"],
                                      "role": p["role"], "paragraph_count": len(p["paragraphs"])}
                                     for p in corpus["papers"]],
                          "corpus_manifest_present": bool(corpus["manifest"])},
        "graph": {"stats": graph["stats"], "nodes": graph["nodes"], "edges": graph["edges"],
                  "merges": graph["merges"], "conflicts": graph["conflicts"]},
        "queries": queries,
        "qc": qcres,
        "uncertainty": {
            "undetermined": [u for q in queries for u in q.get("undetermined", [])][:20],
            "unreported": ["输入无 PDF 页码、无图像与补充材料，不推断其中数值。",
                           "未给条件的比较关系不写绝对优劣。"],
            "conflicts": len(graph["conflicts"]),
            "notes": limit_notes,
        },
        "artifacts": files,
        "change_records": [{"step": "discover", "detail": f"识别 {len(corpus['papers'])} 篇材料"},
                           {"step": "extract", "detail": f"候选实体 {graph['stats']['candidates']} 条 → 节点 {len(graph['nodes'])}"},
                           {"step": "relate", "detail": f"保留边 {len(graph['edges'])}，未映射丢弃 {graph['stats']['edges_dropped_unmapped']}"},
                           {"step": "qc", "detail": f"fail {qcres['summary']['fail']} / warn {qcres['summary']['warn']}"}],
    }
    rpath = Path(outdir) / "result.json"
    rpath.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {rpath}")
    print(f"nodes={len(graph['nodes'])} edges={len(graph['edges'])} "
          f"qc_fail={qcres['summary']['fail']} qc_warn={qcres['summary']['warn']} status={status}")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="litkg — 证据绑定文献知识图谱")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--case", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--case-id", default=None)
    d = sub.add_parser("demo")
    d.add_argument("--out", required=True)
    q = sub.add_parser("query")
    q.add_argument("--kg", required=True)
    q.add_argument("--expr", required=True)
    a = sub.add_parser("audit")
    a.add_argument("--kg", required=True)
    pt = sub.add_parser("patch")
    pt.add_argument("--kg", required=True)
    pt.add_argument("--patch", required=True)
    pt.add_argument("--corpus", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "build":
        build(args.case, args.out, args.case_id)
    elif args.cmd == "demo":
        build(DEFAULT_SYNTH, args.out, "demo-synthetic")
    elif args.cmd == "query":
        graph = json.loads(Path(args.kg).read_text(encoding="utf-8"))
        kind, _, term = args.expr.partition(":")
        if kind == "entity":
            res = q_entity(graph, term)
        elif kind == "relation":
            res = q_relation(graph, term)
        elif kind == "cross":
            res = q_cross(graph)
        else:
            raise SystemExit("expr 形式：entity:<label> | relation:<type> | cross:papers")
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.cmd == "audit":
        graph = json.loads(Path(args.kg).read_text(encoding="utf-8"))
        print(json.dumps({"note": "audit 需配合 build 的 qc 结果；单独 audit 只统计无证据节点/边",
                          "nodes_without_evidence": [n["id"] for n in graph["nodes"] if not n["evidence"]],
                          "edges_without_evidence": [e["id"] for e in graph["edges"] if not e["evidence"]]},
                         ensure_ascii=False, indent=2))
    elif args.cmd == "patch":
        patch_cmd(args.kg, args.patch, args.corpus)


if __name__ == "__main__":
    main()
