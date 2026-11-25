#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""claimlib.py — nanopub-claims 的核心纯函数库（仅标准库）。

所有函数确定性、无网络、无随机；同一输入重复运行输出逐字节一致。
被 segment / decompose / evidence / qc / export 与 tests/selftest.py 共用。
"""

import hashlib
import json
import pathlib
import re

# ---------------------------------------------------------------- io helpers


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_ws(text):
    """空白归一化：只压缩空白，不做 Unicode 折叠（保留连字符、希腊字母、上下标）。"""
    return re.sub(r"\s+", " ", text).strip()


# ------------------------------------------------------------ paragraphs


BLOCK_SEP = re.compile(r"\n\s*\n")


def paragraphs_from_pages(pages, page_break=True):
    """把 [{"page":1,"text":"..."}] 切成段落，段落 id = p{page}b{index}（从 1 起）。"""
    paras = []
    for item in pages:
        page = int(item.get("page", 1))
        text = item.get("text", "")
        blocks = [b.strip() for b in BLOCK_SEP.split(text) if b.strip()]
        if page_break and blocks and not blocks:
            blocks = [text.strip()]
        cursor = 0
        for i, block in enumerate(blocks, 1):
            start = text.find(block, cursor)
            if start < 0:
                start = text.find(block)
            cursor = start + len(block)
            paras.append({
                "id": f"p{page}b{i}",
                "page": page,
                "text": block,
                "norm": norm_ws(block),
                "char_start": start,
                "char_end": start + len(block),
            })
    return paras


SENT_END = re.compile(r"[。！？；;?!]+|\.\s+(?=[A-Z\u4e00-\u9fff])|\n\s*\n")


def split_sentences(text):
    """按句末标点切句，返回 [(start, end, sentence_text)]，偏移相对 text。"""
    spans, start = [], 0
    for m in SENT_END.finditer(text):
        end = m.end()
        seg = text[start:end]
        if seg.strip():
            lead = len(seg) - len(seg.lstrip())
            spans.append((start + lead, end, seg.strip()))
        start = end
    tail = text[start:]
    if tail.strip():
        lead = len(tail) - len(tail.lstrip())
        spans.append((start + lead, len(text), tail.strip()))
    return spans


# 并列/因果连接词：只在其前后都有实质内容时切分，避免把 "而且" 之类切碎
CONNECTIVES = ["并且", "同时", "此外", "而且", "但是", "然而", "因此", "所以", "因为", "；",
               " and ", " while ", " because ", " therefore ", " whereas ", " but "]


def split_connectives(text):
    """在连接词处二次切分（一段话里的并列/因果关系拆成独立候选），返回 [(start,end,text)]。"""
    cuts = []
    for cue in CONNECTIVES:
        for m in re.finditer(re.escape(cue), text):
            if m.start() < 4 or len(text) - m.end() < 4:
                continue
            cuts.append((m.start(), m.end()))
    if not cuts:
        return [(0, len(text), text)]
    cuts.sort()
    merged = []
    for s, e in cuts:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    pieces, prev = [], 0
    for s, e in merged:
        seg = text[prev:s]
        if seg.strip():
            lead = len(seg) - len(seg.lstrip())
            pieces.append((prev + lead, s, seg.strip()))
        prev = e
    seg = text[prev:]
    if seg.strip():
        lead = len(seg) - len(seg.lstrip())
        pieces.append((prev + lead, len(text), seg.strip()))
    return pieces


def candidates_from_paragraphs(paragraphs):
    """段落 -> 候选断言（未填语义）。agent 在此基础上补 subject/relation/object。"""
    out = []
    for para in paragraphs:
        for s_start, s_end, sent in split_sentences(para["text"]):
            for c_start, c_end, cand in split_connectives(sent):
                out.append({
                    "candidate_id": f"c{len(out) + 1:03d}",
                    "paragraph_id": para["id"],
                    "page": para["page"],
                    "char_start": s_start + c_start,
                    "char_end": s_start + c_end,
                    "text": cand,
                    "placeholder": True,
                })
    return out


# --------------------------------------------------------------- evidence


def _norm_with_map(text):
    """返回 (归一化文本, 归一化位置 -> 原始位置 的映射)。"""
    buf, idx = [], []
    prev_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            buf.append(" ")
            idx.append(i)
            prev_space = True
        else:
            buf.append(ch)
            idx.append(i)
            prev_space = False
    return "".join(buf).strip(), idx


def squash(text):
    """去掉全部空白后的文本，用于"仅空白差异"的严格比对。"""
    return re.sub(r"\s+", "", text)


def same_text(a, b):
    """逐字比对，允许且仅允许空白差异（连续空格/换行/制表符）。"""
    return squash(a) == squash(b)


def locate_quote(paragraph_text, quote):
    """在段落里定位逐字引文（允许空白差异）。返回 (char_start, char_end) 或 None。

    两级匹配：先按"空白折叠"匹配；失败再按"去掉全部空白"匹配（应对 PDF 断行、
    连字符软换行、以及引用时删掉空格的情况）。
    """
    hay, idx = _norm_with_map(paragraph_text)
    needle = norm_ws(quote)
    if not needle:
        return None
    pos = hay.find(needle)
    if pos >= 0:
        return idx[pos], idx[pos + len(needle) - 1] + 1

    hay2, idx2 = _squash_with_map(paragraph_text)
    needle2 = squash(quote)
    pos2 = hay2.find(needle2) if needle2 else -1
    if pos2 < 0:
        return None
    return idx2[pos2], idx2[pos2 + len(needle2) - 1] + 1


def _squash_with_map(text):
    """(去空白文本, 去空白位置 -> 原始位置 映射)。"""
    chars, idx = [], []
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        chars.append(ch)
        idx.append(i)
    return "".join(chars), idx


def minimal_span(paragraph_text, tokens):
    """包含全部 token 的最短连续片段（长度按字符计）。返回 (start, end) 或 None。"""
    toks = [norm_ws(t) for t in tokens if t and norm_ws(t)]
    if not toks:
        return None
    hay, idx = _norm_with_map(paragraph_text)
    low = hay.lower()
    occ = []  # 每个 token 的全部出现位置 [(start, end), ...]
    for t in toks:
        t = t.lower()
        found, pos = [], low.find(t)
        while pos >= 0:
            found.append((pos, pos + len(t)))
            pos = low.find(t, pos + 1)
        if not found:
            return None
        occ.append(found)

    best = None
    for start in sorted({s for positions in occ for s, _ in positions}):
        hi = start
        ok = True
        for positions in occ:
            cand = next(((s, e) for s, e in positions if e > start), None)
            if cand is None:
                ok = False
                break
            hi = max(hi, cand[1])
        if not ok:
            continue
        width = hi - start
        if best is None or width < best[1] - best[0]:
            best = (start, hi)
    if best is None:
        return None
    return idx[best[0]], idx[best[1] - 1] + 1


def quote_in_document(quote, paragraphs):
    """返回命中的段落 id 列表（允许空白差异的逐字比对）。"""
    q = squash(quote)
    return [p["id"] for p in paragraphs if q and q in squash(p["text"])]


# ------------------------------------------------------------------- qc

INCREASE_CUES = ["increase", "increased", "higher", "rise", "rose", "up-regulation", "增加", "升高", "提高", "上升", "增大", "增强"]
DECREASE_CUES = ["decrease", "decreased", "lower", "reduce", "reduced", "drop", "decline", "down-regulation", "减少", "降低", "下降", "减小", "减弱", "抑制"]
RELATION_CUES = INCREASE_CUES + DECREASE_CUES + ["correlat", "associated with", "相关", "cause", "导致", "inhibit", "抑制", "activate", "激活", "equal", "等于", "为"]
BROAD_QUANTIFIERS = ["all ", "always", "every ", "no ", "never", "所有", "全部", "任何", "总是", "从不", "均"]
MODALITY_CUES = {"hypothesized": ["may ", "might", "could ", "propose", "hypothes", "可能", "推测", "假设"],
                 "inferred": ["therefore", "thus", "hence", "we infer", "由此", "因此", "推断", "说明"]}

PROVENANCE_FIELDS = ("title", "authors", "year", "source_id")


def _norm_assertion_text(assertion):
    return norm_ws(assertion.get("text", "")).lower()


def qc_assertion(assertion, paragraphs, source, vocab_map):
    """对单条断言做可复现的质量检查，返回 issues 列表。每条 issue 带 criterion。"""
    issues = []
    text = assertion.get("text", "")
    subject = (assertion.get("subject") or {}).get("name", "")
    obj = assertion.get("object") or {}
    obj_name = str(obj.get("name") or obj.get("value") or "")
    rel = assertion.get("relation") or {}
    predicate = rel.get("predicate", "")
    ev = (assertion.get("evidence") or [{}])[0]
    quote = ev.get("quote", "")

    # Q001 断言过宽：含多个句末标点 / 多个关系动词 / 无限定全称量词
    sent_count = len(split_sentences(text))
    cue_count = sum(1 for c in RELATION_CUES if c in text.lower())
    quant = any(q in text.lower() for q in BROAD_QUANTIFIERS)
    if sent_count > 1 or cue_count >= 3:
        issues.append({"code": "Q001", "severity": "fail", "detail": "断言含多句或多重关系",
                       "criterion": "句末标点数>1 或关系动词 cue 命中数>=3"})
    elif quant and not (assertion.get("qualifiers") or {}):
        issues.append({"code": "Q001", "severity": "warn", "detail": "全称量词但无 qualifiers 限定",
                       "criterion": "命中全称量词且 qualifiers 为空"})

    # Q002 证据缺失
    if not quote.strip():
        issues.append({"code": "Q002", "severity": "fail", "detail": "未绑定证据片段",
                       "criterion": "evidence[0].quote 为空"})
    else:
        # Q003 引文非逐字
        hits = quote_in_document(quote, paragraphs)
        if not hits:
            issues.append({"code": "Q003", "severity": "fail", "detail": "引文在文档中找不到（非逐字）",
                           "criterion": "空白归一化后 quote 不是任何段落子串"})
        # Q004 证据不足：片段缺少主体或对象
        missing = [n for n in (subject, obj_name) if n and norm_ws(n) not in norm_ws(quote)]
        if missing:
            issues.append({"code": "Q004", "severity": "fail",
                           "detail": "证据片段缺少实体：" + "、".join(missing),
                           "criterion": "subject/object 的 name 未出现在 quote 中"})
        # Q007 方向错误
        if predicate in ("increases", "activates") and any(c in quote.lower() for c in DECREASE_CUES) \
                and not any(c in quote.lower() for c in INCREASE_CUES):
            issues.append({"code": "Q007", "severity": "fail", "detail": "关系方向与证据相反",
                           "criterion": "predicate 方向=up 而 quote 仅含 down cue"})
        if predicate in ("decreases", "inhibits") and any(c in quote.lower() for c in INCREASE_CUES) \
                and not any(c in quote.lower() for c in DECREASE_CUES):
            issues.append({"code": "Q007", "severity": "fail", "detail": "关系方向与证据相反",
                           "criterion": "predicate 方向=down 而 quote 仅含 up cue"})
        # Q008 数值不一致
        nums = re.findall(r"\d+(?:\.\d+)?", text)
        quote_nums = set(re.findall(r"\d+(?:\.\d+)?", quote))
        bad = [n for n in nums if n not in quote_nums and len(n) >= 2]
        if bad:
            issues.append({"code": "Q008", "severity": "warn", "detail": "断言数值未出现在证据中：" + "、".join(bad),
                           "criterion": "断言中长度>=2 的数字不在 quote 内"})
        # Q009 主体错位：主体未出现在该证据段落
        if hits:
            para_ids = [p["id"] for p in paragraphs if p["id"] in hits]
            para_text = " ".join(p["norm"] for p in paragraphs if p["id"] in para_ids)
            if subject and norm_ws(subject) not in para_text:
                issues.append({"code": "Q009", "severity": "warn", "detail": "证据段落未出现断言主体",
                               "criterion": "subject 不在命中段落文本中"})
        # Q010 偏移与引文不一致
        st, en = ev.get("char_start"), ev.get("char_end")
        if isinstance(st, int) and isinstance(en, int) and st < en:
            para = next((p for p in paragraphs if p["id"] == ev.get("paragraph_id")), None)
            if para is not None:
                raw = para["text"][st:en]
                if not same_text(raw, quote):
                    issues.append({"code": "Q010", "severity": "fail", "detail": "char 偏移切出的文本与 quote 不一致",
                                   "criterion": "paragraph_text[char_start:char_end] 归一化后 != quote"})

    # Q005 关系未映射到受控词表
    if predicate and predicate not in vocab_map:
        issues.append({"code": "Q005", "severity": "fail", "detail": f"predicate 不在受控词表：{predicate}",
                       "criterion": "predicate ∉ vocab/predicates.json"})
    if predicate == "other" and not rel.get("free_text"):
        issues.append({"code": "Q005b", "severity": "fail", "detail": "predicate=other 但未填 free_text",
                       "criterion": "predicate=other 且 relation.free_text 为空"})

    # Q006 来源元数据缺失
    missing_src = [f for f in PROVENANCE_FIELDS if not source.get(f)]
    if missing_src:
        issues.append({"code": "Q006", "severity": "fail", "detail": "来源字段缺失：" + "、".join(missing_src),
                       "criterion": "source 的 title/authors/year/source_id 任一为空"})

    # Q011 置信度依据缺失
    conf = assertion.get("confidence") or {}
    if not conf.get("basis") or conf.get("basis") == "absent":
        issues.append({"code": "Q011", "severity": "warn", "detail": "缺少置信度依据",
                       "criterion": "confidence.basis 为空或 absent"})

    # Q012 推论性断言却用直接证据
    mod = assertion.get("modality", "observed")
    if mod in MODALITY_CUES and ev.get("relation_to_assertion") == "direct":
        issues.append({"code": "Q012", "severity": "warn", "detail": "推论/假设性断言标为直接证据",
                       "criterion": "modality in {inferred,hypothesized} 且 evidence.relation_to_assertion=direct"})

    status = "fail" if any(i["severity"] == "fail" for i in issues) else ("warn" if issues else "pass")
    return {"status": status, "issues": issues}


def qc_assertion_set(assertions, paragraphs, source, vocab_map):
    """对整组断言做检查（含重复检测），回填 assertion.qc 并汇总。"""
    seen, dup = {}, []
    for a in assertions:
        key = _norm_assertion_text(a)
        if key in seen:
            dup.append((a["id"], seen[key]))
        else:
            seen[key] = a["id"]
    issues_total = {}
    for a in assertions:
        a["qc"] = qc_assertion(a, paragraphs, source, vocab_map)
        for issue in a["qc"]["issues"]:
            issues_total[issue["code"]] = issues_total.get(issue["code"], 0) + 1
    for aid, first in dup:
        target = next(a for a in assertions if a["id"] == aid)
        target["qc"]["issues"].append({"code": "Q013", "severity": "warn",
                                       "detail": f"与 {first} 文本重复",
                                       "criterion": "归一化断言文本完全相同"})
        target["qc"]["status"] = "warn" if target["qc"]["status"] == "pass" else target["qc"]["status"]
        issues_total["Q013"] = issues_total.get("Q013", 0) + 1
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for a in assertions:
        counts[a["qc"]["status"]] += 1
    return {"assertion_count": len(assertions), "status_counts": counts,
            "issue_counts": issues_total, "duplicates": [d[0] for d in dup]}


# ---------------------------------------------------------------- export


def to_csv(assertions):
    """扁平 CSV，便于下游程序直接解析（不依赖 JSON 解析器）。"""
    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["assertion_id", "assertion_text", "subject", "predicate", "object",
                     "polarity", "modality", "qualifiers", "evidence_quote", "page",
                     "paragraph_id", "char_start", "char_end", "support", "relation_to_assertion",
                     "provenance_ref", "confidence_level", "confidence_basis", "qc_status"])
    for a in assertions:
        ev = (a.get("evidence") or [{}])[0]
        writer.writerow([
            a["id"], a["text"], (a.get("subject") or {}).get("name", ""),
            (a.get("relation") or {}).get("predicate", ""),
            str((a.get("object") or {}).get("name") or (a.get("object") or {}).get("value") or ""),
            a.get("polarity", "positive"), a.get("modality", "observed"),
            json.dumps(a.get("qualifiers", {}), ensure_ascii=False, sort_keys=True),
            ev.get("quote", ""), ev.get("page", ""), ev.get("paragraph_id", ""),
            ev.get("char_start", ""), ev.get("char_end", ""), ev.get("support", ""),
            ev.get("relation_to_assertion", ""), a.get("provenance_ref", ""),
            (a.get("confidence") or {}).get("level", ""), (a.get("confidence") or {}).get("basis", ""),
            (a.get("qc") or {}).get("status", ""),
        ])
    return buf.getvalue()


def _lit(value):
    if isinstance(value, bool):
        return '"true"^^<http://www.w3.org/2001/XMLSchema#boolean>' if value else '"false"^^<http://www.w3.org/2001/XMLSchema#boolean>'
    if isinstance(value, (int, float)):
        return f'"{value}"^^<http://www.w3.org/2001/XMLSchema#decimal>'
    esc = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{esc}"'


def to_trig(assertions, source, base="https://example.org/nanopub/"):
    """输出 TriG 形式的 nanopublication（assertion / provenance / pubInfo 三个子图）。

    文档：http://nanopub.org/guidelines/working_draft/ （np:hasAssertion 等谓词）
    这里是**可解析的序列化**，不替代正式 nanopub 发布所需的密钥签名。
    """
    sub = base.rstrip("/") + "/sub/"
    lines = [
        "@prefix np: <http://www.nanopub.org/nschema#> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        f"@prefix sub: <{sub}> .",
        f"@prefix src: <{base.rstrip('/')}/source/> .",
        "",
        "sub:Head {",
        "  sub:assertion np:hasAssertion sub:assertion ;",
        "                np:hasProvenance sub:provenance ;",
        "                np:hasPublicationInfo sub:pubinfo .",
        "}",
        "",
        "sub:provenance {",
        f"  sub:assertion prov:wasDerivedFrom src:{_slug(source.get('source_id', 'unknown'))} ;",
        "                prov:wasGeneratedBy sub:assertionSet .",
        "}",
        "",
        "sub:pubinfo {",
        f"  sub:assertionSet a np:AssertionSet ; dct:title {_lit(source.get('title', ''))} ; dct:creator {_lit(', '.join(source.get('authors', [])) or 'unknown')} ; dct:issued {_lit(str(source.get('year', '')))} .",
        "}",
        "",
        "sub:assertion {",
    ]
    for a in assertions:
        p = (a.get("relation") or {}).get("predicate", "other")
        s_name = (a.get("subject") or {}).get("name", "")
        o_val = (a.get("object") or {}).get("name")
        if o_val in (None, ""):
            o_val = (a.get("object") or {}).get("value")
        s_uri = f"sub:{a['id']}"
        lines.append(f"  {s_uri} a np:Assertion ;")
        lines.append(f"    np:subject {_lit(s_name)} ;")
        lines.append(f"    np:predicate {_lit(p)} ;")
        lines.append(f"    np:object {_lit(o_val)} ;")
        lines.append(f"    np:hasEvidence sub:ev_{a['id']} ;")
        lines.append(f"    np:confidence {_lit((a.get('confidence') or {}).get('level', 'low'))} ;")
        lines.append(f"    prov:wasAttributedTo src:{_slug(source.get('source_id', 'unknown'))} .")
        ev = (a.get("evidence") or [{}])[0]
        lines.append(f"  sub:ev_{a['id']} a np:Evidence ;")
        lines.append(f"    np:quote {_lit(ev.get('quote', ''))} ;")
        lines.append(f"    np:page {_lit(int(ev.get('page', 0) or 0))} ;")
        lines.append(f"    np:paragraphId {_lit(ev.get('paragraph_id', ''))} ;")
        lines.append(f"    np:charStart {_lit(int(ev.get('char_start', 0) or 0))} ;")
        lines.append(f"    np:charEnd {_lit(int(ev.get('char_end', 0) or 0))} ;")
        lines.append(f"    np:support {_lit(ev.get('support', 'full'))} .")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip("-") or "unknown"
