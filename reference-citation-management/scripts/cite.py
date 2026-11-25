#!/usr/bin/env python3
"""citation management core: parse manuscript + reference library, renumber,
deduplicate, convert styles (GB/T 7714-2015 / APA 7), audit claim-reference match.

纯标准库。子命令：parse / renumber / dedup / convert / verify / audit
"""
import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

STOP = set("""the a an of in on for with to and or is are was were be been this that these those
we our it its as by from at into than then which who whom whose what when where while
can could may might should would will not also such more most less least very much many
study studies result results data method methods paper article show shows showed suggest suggests
研究 结果 方法 数据 本文 我们 能够 可以 说明 表明 显示 以及 通过 进行 一个 一种 由于 因此""".split())

TYPE_MAP = {
    "journal": "J", "article": "J", "book": "M", "inbook": "M", "incollection": "M",
    "conference": "C", "inproceedings": "C", "proceedings": "C", "thesis": "D",
    "phdthesis": "D", "mastersthesis": "D", "online": "EB/OL", "web": "EB/OL",
    "patent": "P", "report": "R", "techreport": "R", "standard": "S", "preprint": "EB/OL",
}
TYPE_ZH = {"J": "期刊论文", "M": "专著", "C": "会议论文", "D": "学位论文",
           "EB/OL": "电子资源", "P": "专利", "R": "报告", "S": "标准"}

_FIELD_ALIASES = {
    "author": "authors", "authors": "authors", "au": "authors",
    "title": "title", "ti": "title", "t": "title",
    "journal": "container", "journaltitle": "container", "jo": "container",
    "t2": "container", "booktitle": "container", "j": "container",
    "year": "year", "py": "year", "date": "year", "y1": "year", "d": "year",
    "volume": "volume", "vl": "volume", "v": "volume",
    "number": "issue", "issue": "issue", "is": "issue", "n": "issue",
    "pages": "pages", "sp": "pages", "page": "pages", "p": "pages",
    "doi": "doi", "do": "doi", "r": "doi",
    "publisher": "publisher", "pb": "publisher", "url": "url", "ur": "url",
    "type": "type", "ty": "type", "m3": "type",
}


def norm_key(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def norm_title(t):
    """去标点、空白、大小写，用于题名比对。"""
    t = (t or "").lower()
    t = re.sub(r"[\W_]+", " ", t, flags=re.UNICODE)
    return " ".join(t.split())


def tokens(s):
    return {w for w in re.findall(r"[\w\u4e00-\u9fff]+", (s or "").lower())
            if w not in STOP and len(w) > 1}


# 中英概念桥：中文论断与英文题名可比，避免中英混排时一律判 mismatch
CONCEPT = {"掺杂": "doping", "催化": "cataly", "稳定": "stability", "晶格": "lattice",
           "产率": "yield", "衍射": "diffraction", "水热": "hydrothermal", "氧化物": "oxide",
           "样品": "sample", "温度": "temperature", "活性": "activity", "收缩": "contraction",
           "掺杂剂": "dopant", "比表面积": "surface", "反应": "reaction", "机理": "mechanism",
           "密度": "density", "强度": "strength", "效率": "efficiency", "性能": "performance"}


def stem(w):
    return w[:5]


def concept_stems(text):
    """词干集合：中文按二字切分并映射到英文概念，英文按前缀截断。"""
    out = set()
    for w in tokens(text):
        if re.search(r"[A-Za-z]", w):
            out.add(stem(w))
        else:
            for zh, en in CONCEPT.items():
                if zh in (text or ""):
                    out.add(stem(en))
            for i in range(len(w) - 1):
                out.add("zh:" + w[i:i + 2])
    return out


# ---------------- 解析入口 ----------------
def parse_bibtex(text):
    out = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        start = m.end()
        depth, i = 1, m.start() + text[m.start():].index("{") + 1
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[start:i - 1]
        etype, key = m.group(1).lower(), m.group(2).strip()
        rec = {"key": key, "type": etype, "raw_type": etype}
        for fm in re.finditer(r"(\w+)\s*=\s*\{([^{}]*)\}", body):
            name, val = fm.group(1).lower(), fm.group(2).strip()
            if name == "author":
                rec["authors"] = [a.strip() for a in re.split(r"\s+and\s+", val) if a.strip()]
            elif name in ("pages", "page"):
                rec["pages"] = val.replace("--", "-").replace("–", "-")
            else:
                rec[_FIELD_ALIASES.get(name, name)] = re.sub(r"\s+", " ", val)
        rec.setdefault("authors", [])
        rec.setdefault("title", "")
        out.append(rec)
    return out


def parse_ris(text):
    blocks, cur = [], []
    for line in text.splitlines():
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(line.rstrip())
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        rec = {"authors": []}
        key = None
        for line in b:
            m = re.match(r"^([A-Z][A-Z0-9])\s{1,2}-\s?(.*)$", line)
            if not m:
                continue
            tag, val = m.group(1), m.group(2).strip()
            if tag in ("AU", "A1"):
                rec["authors"].append(val)
            elif tag == "TI" or tag == "T1":
                rec["title"] = val
            elif tag in ("JO", "T2", "JF", "JA"):
                rec["container"] = val
            elif tag in ("PY", "Y1"):
                rec["year"] = re.findall(r"\d{4}", val)[0] if re.findall(r"\d{4}", val) else val
            elif tag == "VL":
                rec["volume"] = val
            elif tag == "IS":
                rec["issue"] = val
            elif tag == "SP":
                rec["pages"] = val
            elif tag == "EP":
                rec["pages"] = (rec.get("pages", "") + "-" + val).strip("-")
            elif tag == "DO":
                rec["doi"] = val
            elif tag == "PB":
                rec["publisher"] = val
            elif tag == "UR":
                rec["url"] = val
            elif tag == "TY":
                rec["raw_type"] = val.lower()
                rec["type"] = {"JOUR": "journal", "BOOK": "book", "CONF": "conference",
                               "THES": "thesis", "ELEC": "online", "GEN": "journal",
                               "PAT": "patent", "RPRT": "report"}.get(val.upper(), "journal")
                key = val.upper()
            elif tag == "ID":
                rec["key"] = val
        if not rec.get("key"):
            rec["key"] = "%s-%s" % ((rec.get("authors") or ["anon"])[0].split(",")[0].lower(),
                                    rec.get("year", "nd"))
        rec.setdefault("title", "")
        out.append(rec)
    return out


def parse_endnote(text):
    out, rec = [], None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("%0"):
            if rec:
                out.append(rec)
            rec = {"authors": [], "raw_type": line[2:].strip().lower(),
                   "type": "journal" if "journal" in line.lower() else "book"}
            continue
        if rec is None:
            rec = {"authors": [], "type": "journal"}
        tag, val = line[:2].strip(), line[2:].strip()
        if tag in ("%A", "%E"):
            rec["authors"].append(val)
        elif tag == "%T":
            rec["title"] = val
        elif tag in ("%J", "%B"):
            rec["container"] = val
        elif tag == "%D":
            rec["year"] = re.findall(r"\d{4}", val)[0] if re.findall(r"\d{4}", val) else val
        elif tag == "%V":
            rec["volume"] = val
        elif tag == "%N":
            rec["issue"] = val
        elif tag == "%P":
            rec["pages"] = val
        elif tag == "%R":
            rec["doi"] = val
        elif tag == "%I":
            rec["publisher"] = val
        elif tag == "%U":
            rec["url"] = val
    if rec:
        out.append(rec)
    for i, r in enumerate(out, 1):
        r.setdefault("key", "EN-%02d" % i)
    return out


CNKI_RE = re.compile(r"^\s*(?P<authors>[^\.]{1,120}?)\.\s*(?P<title>[^\.]{4,200}?)\[(?P<t>[A-Z]{1,5}(?:/[A-Z]{2})?)\]\.\s*(?P<container>[^,]{0,120}),?\s*(?P<year>19|20)\d{2}")


def parse_cnki(text):
    """知网导出常见形态：作者. 题名[J]. 刊名, 年, 卷(期): 页."""
    out = []
    for i, line in enumerate([l.strip() for l in text.splitlines() if l.strip()], 1):
        m = CNKI_RE.match(line)
        if not m:
            continue
        rec = {"key": "CNKI-%02d" % i, "type": "journal", "raw_type": "cnki",
               "authors": [a.strip() for a in re.split(r"[,;，；]", m.group("authors")) if a.strip()],
               "title": m.group("title").strip(), "container": m.group("container").strip(),
               "year": m.group("year"), "lang": "zh"}
        tail = line[m.end():]
        vm = re.search(r"(\d+)\s*\((\d+)\)\s*:\s*([\d\-–]+)", tail)
        if vm:
            rec["volume"], rec["issue"], rec["pages"] = vm.group(1), vm.group(2), vm.group(3).replace("–", "-")
        dm = re.search(r"(10\.\d{4,9}/[^\s,;]+)", line)
        if dm:
            rec["doi"] = dm.group(1).rstrip(".")
        out.append(rec)
    return out


def detect_format(text):
    if re.search(r"^\s*@\w+\{", text, re.M):
        return "bibtex"
    if re.search(r"^TY\s{1,2}-", text, re.M):
        return "ris"
    if re.search(r"^%[0A-Z]\s", text, re.M):
        return "endnote"
    if re.search(r"\[[JMDCRSP]\]\.", text):
        return "cnki"
    return "plain"


def parse_library(text, fmt=None):
    fmt = fmt or detect_format(text)
    fn = {"bibtex": parse_bibtex, "ris": parse_ris, "endnote": parse_endnote,
          "cnki": parse_cnki}.get(fmt)
    if not fn:
        raise ValueError("unsupported library format: %s" % fmt)
    recs = fn(text)
    for r in recs:
        r.setdefault("lang", "en" if re.search(r"[A-Za-z]{4}", r.get("title", "")) else "zh")
    return recs


# ---------------- 渲染 ----------------
def gbt_authors(authors, zh):
    names = [a.replace(" and ", " ") for a in (authors or [])]
    if not names:
        return ""
    if zh or re.search(r"[\u4e00-\u9fff]", names[0]):
        head = ", ".join(names[:3])
        if len(names) > 3:
            head += ", 等"
        return head + "."
    fmt = []
    for n in names[:3]:
        if "," in n:
            last, rest = [x.strip() for x in n.split(",", 1)]
            initials = " ".join(x[0].upper() + "." for x in rest.replace(".", " ").split())
        else:
            parts = n.split()
            last = parts[-1]
            initials = " ".join(p[0].upper() + "." for p in parts[:-1])
        fmt.append(("%s %s" % (last.upper(), initials)).strip())
    head = ", ".join(fmt)
    if len(names) > 3:
        head += ", et al"
    return head.rstrip(".") + "."


def apa_authors(authors):
    out = []
    for n in (authors or []):
        if "," in n:
            out.append(n.strip())
        else:
            parts = n.split()
            if len(parts) >= 2:
                out.append("%s, %s" % (" ".join(parts[:-1]), "".join(p[0] + "." for p in parts[-1:])))
            else:
                out.append(parts[0])
    if not out:
        return ""
    if len(out) == 1:
        return out[0]
    return ", ".join(out[:-1]) + ", & " + out[-1]


def render_gbt(r):
    t = TYPE_MAP.get((r.get("type") or "journal").lower(), "J")
    year = str(r.get("year") or "")
    au = gbt_authors(r.get("authors"), r.get("lang") == "zh")
    title = (r.get("title") or "").strip().rstrip(".")
    head = ("%s %s[%s]." % (au, title, t)) if au else ("%s[%s]." % (title, t))
    body = ""
    if t == "J":
        body = "%s, %s" % (r.get("container") or "", year)
        if r.get("volume"):
            body += ", %s" % r["volume"]
            if r.get("issue"):
                body += "(%s)" % r["issue"]
        if r.get("pages"):
            body += ": %s" % r["pages"]
        body += "."
    elif t in ("M", "C", "R", "D"):
        place = r.get("publisher") or r.get("container") or ""
        body = ("%s, %s." % (place, year)) if place else ("%s." % year)
    else:
        body = "%s." % year
    out = " ".join(x for x in (head, body) if x)
    if r.get("doi"):
        out += " DOI: %s." % r["doi"]
    return out


def render_apa(r):
    year = r.get("year", "")
    title = r.get("title", "")
    s = "%s (%s). %s." % (apa_authors(r.get("authors")), year, title)
    if (r.get("type") or "journal").lower() in ("journal", "conference", "preprint"):
        s += " %s" % r.get("container", "")
        if r.get("volume"):
            s += ", %s" % r["volume"]
            if r.get("issue"):
                s += "(%s)" % r["issue"]
        if r.get("pages"):
            s += ", %s" % r["pages"]
        s += "."
    if r.get("doi"):
        s += " https://doi.org/%s" % r["doi"]
    return re.sub(r"\s+", " ", s).strip()


def render(rec, style="gbt"):
    return render_gbt(rec) if style.startswith("gbt") or "7714" in style else render_apa(rec)


# ---------------- 正文标记 ----------------
MARK_RE = re.compile(r"\[(\d+(?:\s*[-,–]\s*\d+)*)\]|［(\d+(?:\s*[-,–]\s*\d+)*)］")


def expand_marks(s):
    nums = []
    for grp in re.findall(r"\d+(?:\s*[-,–]\s*\d+)*", s.replace("－", "-")):
        for part in re.split(r"[-,–]", grp):
            if part.strip():
                nums.append(int(part))
    return nums


def compress(nums):
    nums = sorted(set(nums))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else "%d-%d" % (nums[i], nums[j]))
        i = j + 1
    return ",".join(out)


def find_marks(text):
    for m in MARK_RE.finditer(text):
        yield m.start(), m.end(), expand_marks(m.group(0))


def split_sentences(text):
    chunks = re.split(r"(?<=[。！？；.!?;])\s*", text)
    return [c for c in chunks if c.strip()]


def renumber(manuscript, n_refs):
    """按正文首次出现顺序重排编号；返回新正文、映射、问题清单。"""
    order = OrderedDict()
    all_nums = set()
    for _, _, nums in find_marks(manuscript):
        for n in nums:
            all_nums.add(n)
            if 1 <= n <= n_refs and n not in order:
                order[n] = len(order) + 1
    issues = []
    referenced = set(order)
    for n in sorted(all_nums):
        if n < 1 or n > n_refs:
            issues.append({"kind": "dangling_intext", "number": n,
                           "detail": "正文引用编号超出文献表范围 1..%d" % n_refs})
    for i in range(1, n_refs + 1):
        if i not in referenced:
            issues.append({"kind": "uncited_reference", "number": i,
                           "detail": "文献表第 %d 条未被正文引用" % i})

    def repl(m):
        nums = expand_marks(m.group(0))
        new = [order.get(n, n) for n in nums]
        return "[%s]" % compress(new)

    new_text = MARK_RE.sub(repl, manuscript)
    if MANUAL_MARK_RE.search(manuscript):
        issues.append({"kind": "non_numeric_marker", "number": 0,
                       "detail": "存在著者-出版年或脚注式标记，顺序编码制重排不覆盖，需人工确认"})
    return new_text, order, issues


MANUAL_MARK_RE = re.compile(r"[（(]\s*[A-Z][A-Za-z\-' ]+(?:\s*(?:et al\.?|等))?,\s*(?:19|20)\d{2}[a-z]?\s*[）)]")


# ---------------- 去重 ----------------
def dedup_records(recs):
    """返回 (合并后记录, 合并组, 误合并风险清单)。组内 keep_key 为保留下来的条目。"""
    merged, groups, used = [], [], set()
    for i, a in enumerate(recs):
        if i in used:
            continue
        members, basis = [i], []
        for j in range(i + 1, len(recs)):
            if j in used:
                continue
            rule = merge_basis(a, recs[j])
            if rule:
                members.append(j)
                basis.append({"with": recs[j].get("key", j), "rule": rule})
                used.add(j)
        used.add(i)
        if len(members) > 1:
            m = build_merged([recs[k] for k in members], basis)
            keep = a.get("key") or "idx%d" % (i + 1)
            m["_keep_key"] = keep
            merged.append(m)
            groups.append({"keep_key": keep,
                           "merged_keys": [recs[k].get("key") for k in members],
                           "basis": basis})
        else:
            merged.append(dict(a))
    return merged, groups, []


def merge_basis(a, b):
    """给出合并判据；返回 None 表示不合并（宁可不合也不误合）。"""
    da, db = (a.get("doi") or "").lower().strip(), (b.get("doi") or "").lower().strip()
    if da and db and da == db:
        return "R-DOI: 同一 DOI"
    ta, tb = norm_title(a.get("title")), norm_title(b.get("title"))
    if not ta or not tb:
        return None
    if ta == tb:
        title_rule = "R-TITLE-NORM: 题名规范化后一致"
    else:
        inter = tokens(ta) & tokens(tb)
        union = tokens(ta) | tokens(tb)
        if not (len(inter) >= 3 and len(inter) / float(len(union) or 1) >= 0.75):
            return None
        title_rule = "R-TITLE-FUZZY: 题名词元高度重合"
    sa, sb = surname(a), surname(b)
    if sa and sb and sa != sb:
        return None
    ya, yb = str(a.get("year") or ""), str(b.get("year") or "")
    if ya.isdigit() and yb.isdigit() and abs(int(ya) - int(yb)) > 1:
        same_journal = (a.get("container") or "").strip().lower() == \
                       (b.get("container") or "").strip().lower() and bool(a.get("container"))
        if not same_journal:
            return None
    pa, pb = is_preprint(a), is_preprint(b)
    if pa != pb:
        return "R-PREPRINT: 同题预印本与正式版，保留正式版"
    if a.get("lang") and b.get("lang") and a["lang"] != b["lang"]:
        return "R-BILINGUAL: 中英文题名同源（需人工复核）"
    return title_rule


def is_preprint(rec):
    return ("preprint" in (rec.get("raw_type") or "").lower()
            or "arxiv" in (rec.get("container") or "").lower()
            or (rec.get("type") or "").lower() == "preprint"
            or "biorxiv" in (rec.get("container") or "").lower())


def surname(rec):
    au = (rec.get("authors") or [""])[0]
    if not au:
        return ""
    return (au.split(",")[-1] if "," in au else au.split()[-1]).strip().lower()


def build_merged(recs, basis):
    """优先保留正式发表版：非预印本优先，其次字段更全的条目。"""
    order = sorted(range(len(recs)), key=lambda i: (
        1 if is_preprint(recs[i]) else 0,
        -(len(recs[i].get("doi") or "")),
        -(len(str(recs[i].get("pages") or ""))),
        -(len(str(recs[i].get("volume") or "")))))
    base = dict(recs[order[0]])
    for i in range(1, len(recs)):
        for k, v in recs[i].items():
            if k == "key":
                continue
            if not base.get(k) and v:
                base[k] = v
    base["merged_from"] = [r.get("key") for r in recs]
    base["merge_basis"] = basis
    return base


# ---------------- 核验 ----------------
DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$")


def verify_records(recs):
    out = []
    for r in recs:
        flags = []
        doi = (r.get("doi") or "").strip()
        if doi and not DOI_RE.match(doi):
            flags.append({"kind": "doi_malformed", "detail": "DOI 不符合 10.xxxx/... 形态"})
        if not doi and (r.get("type") or "journal") == "journal":
            flags.append({"kind": "doi_missing", "detail": "期刊条目缺 DOI，无法在线核验"})
        if not r.get("year"):
            flags.append({"kind": "year_missing", "detail": "缺年份，无法与正文年份比对"})
        if not r.get("authors"):
            flags.append({"kind": "author_missing", "detail": "缺作者"})
        if re.search(r"(example|dummy|test|placeholder|待补|XXX)", (r.get("title") or ""), re.I):
            flags.append({"kind": "placeholder_title", "detail": "题名像占位/编造内容"})
        out.append({"key": r.get("key"), "flags": flags,
                    "status": "verified_shape" if not flags else "needs_check"})
    return out


def claim_match(claim, rec):
    ct = concept_stems(claim)
    rt = concept_stems((rec.get("title") or "") + " " + (rec.get("container") or ""))
    if not ct or not rt:
        return "undetermined", 0.0
    inter = ct & rt
    score = len(inter) / max(3.0, min(len(rt), 8))
    if len(inter) >= 2 and score >= 0.28:
        return "strong", round(min(1.0, score), 3)
    if inter:
        return "weak", round(score, 3)
    return "mismatch", 0.0


NUM_CUE = re.compile(r"\d+(?:\.\d+)?\s*(%|mg|g|kg|mL|L|h|min|°C|K|MPa|cm|nm)|百分|倍")
ASSERT_CUE = re.compile(r"(表明|证明|显示|说明|证实|优于|提升|降低|显著|总是|均|全部|"
                        r"\b(show|shows|prove|proves|confirm|confirms|demonstrate|demonstrates|"
                        r"improve|improves|increase|increases|decrease|decreases)\b)", re.I)


def placement_of(sentence, mark_pos):
    """判断引用标注贴在哪类论断后面，用于"挂得对"自查。"""
    before = sentence[:mark_pos] if mark_pos >= 0 else sentence
    if NUM_CUE.search(before):
        return "after-numeric-claim"
    if ASSERT_CUE.search(before):
        return "after-assertion"
    if mark_pos >= 0 and mark_pos > len(sentence) * 0.8:
        return "sentence-end"
    return "mid-sentence"


# ---------------- 审计 ----------------
def audit(manuscript, recs, style="gbt", case_id="", lib_format=""):
    recs, groups, _ = dedup_records(recs)
    for idx, r in enumerate(recs, 1):
        r["order"] = idx
    checks = verify_records(recs)
    cit, cc = [], []
    for sent in split_sentences(manuscript):
        marks = list(find_marks(sent))
        for _, _, nums in marks:
            for n in nums:
                target = next((r for r in recs if r.get("order") == n), None)
                if target is None:
                    cc.append({"claim": sent.strip(), "ref_key": "?%d" % n,
                               "match": "dangling", "evidence": "文献表无第 %d 条" % n})
                    continue
                verdict, score = claim_match(sent, target)
                cc.append({"claim": sent.strip(), "ref_key": target.get("key"),
                           "match": verdict,
                           "evidence": "%s | 词重叠得分 %.3f | 题名：%s" % (
                               verdict, score, target.get("title")),
                           "score": score})
                cit.append({"claim_span": sent.strip(), "ref_keys": target.get("key"),
                            "placement": placement_of(sent, sent.rfind("[")),
                            "style": style})
    gaps = []
    for sent in split_sentences(manuscript):
        if list(find_marks(sent)) or len(sent) < 18:
            continue
        numeric = re.search(r"\d+(?:\.\d+)?\s*(?:%|‰|倍|[A-Za-zµ°]{1,4}\s*/?\s*[A-Za-z]*)", sent)
        assert_cue = ASSERT_CUE.search(sent) or re.search(r"(高于|低于|达到|超过|显著|均|全部)", sent)
        if numeric or assert_cue:
            gaps.append({"sentence": sent.strip(),
                         "reason": ("含数值" if numeric else "含断言") + "但无引用标记"})
    ref_list = []
    for r in recs:
        st = next((c["status"] for c in checks if c["key"] == r.get("key")), "needs_check")
        ref_list.append({"key": r.get("key"), "metadata": render(r, style),
                         "doi": r.get("doi") or "", "source": r.get("merged_from") or r.get("key"),
                         "status": st})
    dedup_rows = []
    for g in groups:
        rules = sorted({b["rule"].split(":")[0] for b in g["basis"]})
        dedup_rows.append({"merged_keys": ", ".join(str(k) for k in g["merged_keys"]),
                           "basis": "; ".join(rules),
                           "kept_key": g["keep_key"]})
    revised, mapping, re_issues = renumber(manuscript, len(recs))
    ordered = [None] * len(recs)
    for old, new in mapping.items():
        if 1 <= old <= len(recs) and 1 <= new <= len(recs):
            ordered[new - 1] = ref_list[old - 1]
    ordered = [r for r in ordered if r] + [r for r in ref_list if r not in ordered]
    for i, r in enumerate(ordered, 1):
        r["order"] = i
    return {
        "manuscript_revised": revised,
        "order": {str(k): v for k, v in mapping.items()},
        "renumber_issues": re_issues,
        "citations": cit,
        "reference_list": ordered,
        "dedup": dedup_rows,
        "consistency_checks": cc,
        "format_notes": {"target_style": style, "converted_from": lib_format or "",
                         "kept_fields": ["DOI", "volume", "issue", "pages"]},
        "citation_gaps": gaps,
        "verify": checks,
        "stats": {"refs_in": len(recs) + sum(len(g["merged_keys"]) - 1 for g in groups),
                  "refs_out": len(recs), "merged_groups": len(groups),
                  "citations": len(cit), "gaps": len(gaps),
                  "weak_matches": sum(1 for c in cc if c["match"] in ("weak", "mismatch"))},
    }


# ---------------- CLI ----------------
def load_text(p):
    return Path(p).read_text(encoding="utf-8", errors="replace")


def cmd_parse(a):
    recs = parse_library(load_text(a.library), a.format)
    print(json.dumps({"format": detect_format(load_text(a.library)), "records": recs},
                     ensure_ascii=False, indent=2))


def cmd_renumber(a):
    ms = load_text(a.manuscript)
    recs = parse_library(load_text(a.library), a.format)
    new_text, mapping, issues = renumber(ms, len(recs))
    out = {"manuscript": new_text, "mapping": {str(k): v for k, v in mapping.items()},
           "issues": issues, "verdict": "FAIL" if any(i["kind"] == "dangling_intext" for i in issues) else "PASS"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_dedup(a):
    recs = parse_library(load_text(a.library), a.format)
    merged, groups, _ = dedup_records(recs)
    print(json.dumps({"merged": merged,
                      "groups": [{"keep_key": g["keep_key"], "members": g["merged_keys"],
                                  "basis": [b["rule"] for b in g["basis"]]} for g in groups],
                      "count_in": len(recs), "count_out": len(merged)},
                     ensure_ascii=False, indent=2))


def cmd_convert(a):
    recs = parse_library(load_text(a.library), a.format)
    out = [{"key": r.get("key"), "rendered": render(r, a.style)} for r in recs]
    print(json.dumps({"style": a.style, "items": out}, ensure_ascii=False, indent=2))


def cmd_verify(a):
    recs = parse_library(load_text(a.library), a.format)
    print(json.dumps(verify_records(recs), ensure_ascii=False, indent=2))


def cmd_audit(a):
    ms = load_text(a.manuscript)
    recs = parse_library(load_text(a.library), a.format)
    res = audit(ms, recs, style=a.style, case_id=a.case_id or "", lib_format=a.format or detect_format(load_text(a.library)))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description="reference & citation management toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, need_ms in (("parse", cmd_parse, False), ("renumber", cmd_renumber, True),
                              ("dedup", cmd_dedup, False), ("convert", cmd_convert, False),
                              ("verify", cmd_verify, False), ("audit", cmd_audit, True)):
        sp = sub.add_parser(name)
        sp.add_argument("--library", required=True)
        sp.add_argument("--format", default=None)
        sp.add_argument("--style", default="gbt")
        sp.add_argument("--case-id", default="")
        sp.add_argument("--out", default=None)
        if need_ms:
            sp.add_argument("--manuscript", required=True)
        sp.set_defaults(func=fn)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main() or 0)
