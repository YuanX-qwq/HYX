#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""layout.py -- reading order + paragraph reconstruction from page lines.

Two deterministic stages:

1. ``xy_cut``  -- recursive X/Y cut over line bounding boxes.  A region is split
   at the widest gutter crossed by no line (column cut) or the widest empty
   horizontal band (block cut).  Full-width titles/abstracts block a column cut
   across the whole page, so those are peeled off vertically first: two-column
   text is therefore never interleaved.

2. ``group_paragraphs`` -- inside one cut leaf, consecutive lines are merged
   into a paragraph while font size and vertical gaps stay stable and no
   first-line indent plus sentence-final punctuation marks a boundary.
   End-of-line hyphenation is resolved with corpus evidence (``wordlist``):
   ``dimension-``/``ality`` -> ``dimensionality`` while the compound
   ``condensed-matter`` keeps its hyphen.

Input lines: dicts with x0,y0,x1,y1,text,size,bold,italic (see pdfwords.py).
Output blocks: dicts with text, bbox, page, zone, size, bold, n_lines.
"""
from __future__ import annotations

import re
from statistics import median

SENT_END = re.compile(r"[.!?][\"')\]]?$")
MATH_CHARS = set("=∑∏∫√±×÷≈≠≤≥∂∇∞−αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩħ⟨⟩†‡∗")
HEADING_NUM = re.compile(r"^(\d+(\.\d+)*|[IVXLC]+)\.?\s+\S")
PAGE_NO = re.compile(r"^[-\u2013\u2014 ]*\d{1,4}[-\u2013\u2014 ]*$")
STAMP = re.compile(r"^(arxiv:\S+|preprint|accepted|published|received|doi:)", re.I)
AFFIL = re.compile(r"^\d?\s*[A-Z][^.]{0,120}(Institute|Department|University|"
                   r"Laboratory|College|Center|Centre)")


# ------------------------------------------------------------------ geometry
def media_size(lines):
    return median([l["size"] for l in lines]) if lines else 10.0


def line_gap(lines):
    ys = sorted(l["y0"] for l in lines)
    if len(ys) < 2:
        return 12.0
    fs = media_size(lines)
    gaps = [b - a for a, b in zip(ys, ys[1:]) if 2.0 < (b - a) < 4 * fs]
    return median(gaps) if gaps else 1.6 * fs


def _widest_x_gutter(lines, min_gap):
    ivs = sorted((l["x0"], l["x1"]) for l in lines)
    best = (0.0, None)
    cur_end = ivs[0][1]
    for x0, x1 in ivs[1:]:
        gap = x0 - cur_end
        if gap > best[0]:
            best = (gap, (cur_end + x0) / 2.0)
        cur_end = max(cur_end, x1)
    if best[0] >= min_gap and best[1] is not None:
        return best
    return None


def _widest_y_gap(lines, min_gap):
    ivs = sorted((l["y0"], l["y1"]) for l in lines)
    best = (0.0, None)
    cur_end = ivs[0][1]
    for y0, y1 in ivs[1:]:
        gap = y0 - cur_end
        if gap > best[0]:
            best = (gap, (cur_end + y0) / 2.0)
        cur_end = max(cur_end, y1)
    if best[0] >= min_gap and best[1] is not None:
        return best
    return None


def xy_cut(lines, page_w, min_x_gap=9.0, min_y_gap=None, depth=0, max_depth=24):
    """Return cut leaves: list of line-lists in reading order."""
    if len(lines) <= 1 or depth > max_depth:
        return [sorted(lines, key=lambda l: (round(l["y0"], 1), l["x0"]))]
    if min_y_gap is None:
        fs = media_size(lines)
        min_y_gap = max(1.6 * line_gap(lines), line_gap(lines) + 0.45 * fs)
    xg = _widest_x_gutter(lines, min_x_gap)
    if xg:
        gx = xg[1]
        left = [l for l in lines if (l["x0"] + l["x1"]) / 2.0 < gx]
        right = [l for l in lines if (l["x0"] + l["x1"]) / 2.0 >= gx]
        if len(left) >= 2 and len(right) >= 2:
            return (xy_cut(left, page_w, min_x_gap, min_y_gap, depth + 1, max_depth)
                    + xy_cut(right, page_w, min_x_gap, min_y_gap, depth + 1, max_depth))
    yg = _widest_y_gap(lines, min_y_gap)
    if yg:
        gy = yg[1]
        top = [l for l in lines if (l["y0"] + l["y1"]) / 2.0 < gy]
        bot = [l for l in lines if (l["y0"] + l["y1"]) / 2.0 >= gy]
        if top and bot:
            return (xy_cut(top, page_w, min_x_gap, min_y_gap, depth + 1, max_depth)
                    + xy_cut(bot, page_w, min_x_gap, min_y_gap, depth + 1, max_depth))
    return [sorted(lines, key=lambda l: (round(l["y0"], 1), l["x0"]))]


# --------------------------------------------------------------- hyphenation
def _join_line(prev_text, text, wordlist, size):
    prev_text = prev_text.rstrip()
    text = text.lstrip()
    if prev_text.endswith("-") and re.search(r"[A-Za-z]-$", prev_text) and text[:1].islower():
        left = re.sub(r".*?([A-Za-z]+)-$", r"\1", prev_text)
        m = re.match(r"([A-Za-z]+)", text)
        right = m.group(1) if m else ""
        joined = (left + right).lower()
        hyphenated = (left + "-" + right).lower()
        if wordlist and joined in wordlist and hyphenated not in wordlist:
            return prev_text[:-1] + text
        if wordlist and hyphenated in wordlist and joined not in wordlist:
            return prev_text + text
        # no corpus evidence: keep hyphen for short fragments, drop it when both
        # fragments are long (TeX hyphenation almost always splits long words)
        if len(left) >= 4 and len(right) >= 4 and wordlist:
            return prev_text[:-1] + text
        return prev_text + text
    return prev_text + " " + text


def group_paragraphs(lines, page_w, wordlist=None):
    """Merge reading-ordered lines of one leaf into paragraph blocks."""
    if not lines:
        return []
    blocks = []
    cur = None
    text_l = min(l["x0"] for l in lines)
    text_r = max(l["x1"] for l in lines)
    page_cx = page_w / 2.0

    def centered(ln):
        w = ln["x1"] - ln["x0"]
        return (abs((ln["x0"] + ln["x1"]) / 2.0 - page_cx) < 0.035 * page_w
                and w < 0.80 * (text_r - text_l))

    for ln in lines:
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        starts_new = True
        if cur is not None:
            gap = ln["y0"] - cur["lines"][-1]["y1"]
            lg = cur["_lg"]
            fs = max(cur["size"], ln["size"])
            size_shift = abs(ln["size"] - cur["size"]) > 0.09 * fs
            bold_shift = bool(ln.get("bold")) != bool(cur["bold"]) and (
                ln.get("bold") or cur["bold"]) and (cur["n_lines"] >= 1)
            prev_text = cur["text"]
            indent = ln["x0"] - cur["_left"]
            c_shift = centered(ln) != cur["_centered"] and (centered(ln) or cur["_centered"])
            if ln.get("_solo") or cur["lines"][-1].get("_solo"):
                starts_new = True
            elif c_shift:
                starts_new = True
            elif size_shift:
                starts_new = True
            elif bold_shift and len(cur["text"].split()) <= 40:
                starts_new = True
            elif gap > 1.55 * lg:
                starts_new = True
            elif indent > 0.8 * fs and SENT_END.search(prev_text):
                starts_new = True
            elif SENT_END.search(prev_text) and gap > 1.06 * lg:
                starts_new = True
            elif not SENT_END.search(prev_text) and gap > 1.45 * lg:
                starts_new = True
            else:
                starts_new = False
        if starts_new:
            if cur:
                blocks.append(cur)
            lg = line_gap(lines)
            xs = sorted(l["x0"] for l in lines)
            left = xs[max(0, int(0.1 * (len(xs) - 1)))]
            cur = {
                "lines": [ln], "text": text, "page": ln.get("page", 1),
                "x0": ln["x0"], "y0": ln["y0"], "x1": ln["x1"], "y1": ln["y1"],
                "size": ln["size"], "bold": bool(ln.get("bold")), "n_lines": 1,
                "_lg": lg, "_left": left, "_centered": centered(ln),
            }
        else:
            cur["text"] = _join_line(cur["text"], text, wordlist, cur["size"])
            cur["lines"].append(ln)
            cur["x0"] = min(cur["x0"], ln["x0"])
            cur["y0"] = min(cur["y0"], ln["y0"])
            cur["x1"] = max(cur["x1"], ln["x1"])
            cur["y1"] = max(cur["y1"], ln["y1"])
            cur["size"] = max(cur["size"], ln["size"])
            cur["n_lines"] = len(cur["lines"])
    if cur:
        blocks.append(cur)
    for b in blocks:
        b["text"] = re.sub(r"[ \t]+", " ", b["text"]).strip()
        b["n_lines"] = len(b["lines"])
        b["centered"] = bool(b.pop("_centered", False))
        w = b["x1"] - b["x0"]
        if w > 0.62 * page_w:
            b["zone"] = "full"
        else:
            b["zone"] = "col-1" if (b["x0"] + b["x1"]) / 2 < page_w / 2 else "col-2"
        for k in ("_lg", "_left"):
            b.pop(k, None)
    return blocks


def build_wordlist(pages):
    words = set()
    for p in pages:
        for ln in p["lines"]:
            for w in re.findall(r"[A-Za-z]{3,}", ln["text"]):
                words.add(w.lower())
    return words


def page_blocks(pages, wordlist=None):
    """Return [(page, width, height, blocks)] in reading order."""
    out = []
    for p in pages:
        raw = [dict(l) for l in p["lines"] if (l.get("text") or "").strip()]
        lines, furniture = [], []
        for ln in raw:
            t = ln["text"]
            if ln.get("rotated"):
                furniture.append((ln, "margin"))
            elif PAGE_NO.match(t) and (ln["y0"] < 0.12 * p["height"]
                                       or ln["y0"] > 0.88 * p["height"]):
                furniture.append((ln, "header" if ln["y0"] < 0.12 * p["height"] else "footer"))
            elif STAMP.match(t) and len(t) < 120:
                furniture.append((ln, "margin"))
            else:
                if AFFIL.match(t) and len(t.split()) <= 40:
                    ln["_solo"] = True
                lines.append(ln)
        blocks = []
        if lines:
            leaves = xy_cut(lines, p["width"])
            for leaf in leaves:
                blocks.extend(group_paragraphs(leaf, p["width"], wordlist))
        for ln, hint in sorted(furniture, key=lambda x: x[0]["y0"]):
            blocks.insert(0, {
                "text": ln["text"], "page": p["page"], "x0": ln["x0"], "y0": ln["y0"],
                "x1": ln["x1"], "y1": ln["y1"], "size": ln["size"], "bold": False,
                "n_lines": 1, "zone": "margin", "kind_hint": hint,
            })
        # continuation across leaves: previous block does not end a sentence and
        # the next leaf starts in the same column with a small gap
        merged = []
        for b in blocks:
            if merged:
                last = merged[-1]
                gap = b["y0"] - last["y1"]
                same_col = min(last["x1"], b["x1"]) - max(last["x0"], b["x0"]) > 0.5 * min(
                    last["x1"] - last["x0"], b["x1"] - b["x0"])
                if ("kind_hint" not in b and "kind_hint" not in last
                        and same_col and gap < 1.3 * line_gap([last["lines"][0], b["lines"][0]])
                        and not SENT_END.search(last["text"]) and not b["text"][:1].isupper()):
                    last["text"] = last["text"] + " " + b["text"]
                    last["x1"] = max(last["x1"], b["x1"])
                    last["y1"] = max(last["y1"], b["y1"])
                    last["lines"].extend(b["lines"])
                    last["n_lines"] = len(last["lines"])
                    continue
            merged.append(b)
        out.append((p["page"], p["width"], p["height"], merged))
    return out
