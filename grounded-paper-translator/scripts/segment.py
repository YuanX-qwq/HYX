#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""segment.py -- PDF/TXT -> anchored translation segments (paragraph units).

Outputs
-------
* ``segments.json``  : every segment in reading order with a stable id
                       (``P0001`` ...), page, bbox, zone, section, kind, text and
                       sentence list.  Later stages may only reference these ids.
* ``segments.md``    : the same content rendered for an agent to read.
* ``translate.todo.jsonl`` : one line per translatable segment
                       ``{"pid","kind","section","page","source","zh":""}``.
* ``scope.json``     : default translation scope + verbatim segments.

Kinds: title, authors, abstract, heading, body, caption, table, equation,
reference, footnote, header, footer.  title/abstract/heading/body/caption/table/
footnote are translatable by default; equations and references are kept verbatim
and are only checked for preservation.

Usage
-----
  python3 segment.py --pdf paper.pdf --out work/segments.json \
      [--md work/segments.md] [--todo work/translate.todo.jsonl] \
      [--backend pymupdf]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdfwords  # noqa: E402
import layout  # noqa: E402

TRANSLATABLE = {"title", "abstract", "heading", "body", "caption", "table", "footnote"}
VERBATIM = {"equation", "reference", "authors", "header", "footer", "margin",
            "figure-label", "fragment"}

HEADING_WORDS = re.compile(
    r"^(abstract|introduction|background|related work|methods?|methodology|model|"
    r"theory|experiments?|results?|discussion|conclusions?|summary|outlook|"
    r"acknowledg(e)?ments?|references?|bibliography|appendix|supplementary|"
    r"data availability|author contributions|competing interests|"
    r"materials and methods)\b", re.I)
HEADING_NUM = re.compile(r"^(\d+(\.\d+)*|[IVXLC]+)\.?\s+[A-Z]")
CAPTION = re.compile(r"^(FIG\.?|FIGURE|TABLE|SCHEME|CHART)\s*[\dIVXLC]+[.:]?\s", re.I)
EQ_NUM = re.compile(r"[\(\[][\dA-Z]{1,3}[\)\]]\s*$")
PAGE_NO = re.compile(r"^[-\u2013\u2014 ]*\d{1,4}[-\u2013\u2014 ]*$")
AFFIL = re.compile(r"^\d?\s*[A-Z][^.]{0,120}(Institute|Department|University|"
                   r"Laboratory|College|Center|Centre)")
REF_ITEM = re.compile(r"^\[\d+\s*[\],]")
MATH_PUA = re.compile(r"[\uf8e0-\uf8ff]")
ABBR = {"e.g.", "i.e.", "et al.", "fig.", "figs.", "eq.", "eqs.", "vs.", "ref.",
        "refs.", "sec.", "no.", "approx.", "cf.", "resp.", "suppl.", "tab.",
        "al.", "ca.", "dr.", "prof.", "st.", "jr.", "sect.", "app.", "ch.",
        "pts.", "min.", "max.", "avg.", "std."}


def split_sentences(text):
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if out:
            prev = out[-1]
            tail = re.findall(r"([A-Za-z.]+)\.$", prev)
            last_word = (tail[0] + ".").lower() if tail else ""
            if (last_word in ABBR or re.search(r"\b(?:[A-Z]\.)+$", prev)
                    or (re.search(r"\d\.$", prev) and re.match(r"\d", p))):
                out[-1] = prev + " " + p
                continue
        out.append(p)
    return out


def sent_end(t):
    return bool(re.search(r"[.!?][\"')\]]?$", (t or "").strip()))


def _inside(b, boxes):
    cx = (b["x0"] + b["x1"]) / 2.0
    cy = (b["y0"] + b["y1"]) / 2.0
    for x0, y0, x1, y1 in boxes:
        if x0 - 2 <= cx <= x1 + 2 and y0 - 2 <= cy <= y1 + 2:
            return True
    return False


def classify(b, ctx):
    hint = b.get("kind_hint")
    if hint:
        return hint
    text = b["text"]
    fs = ctx["body_size"]
    size = b["size"]
    ph = ctx["page_height"]
    n = len(text.split())

    if ctx["refs_mode"]:
        return "reference"
    if ctx["page"] == 1 and size >= 1.15 * fs and 3 <= n <= 40 and len(text) > 8:
        return "title"
    if CAPTION.match(text):
        return "caption"
    if b["y0"] < 0.045 * ph and n < 25:
        return "header"
    if b["y1"] > 0.97 * ph and n < 25:
        return "footer"
    if ctx["figures"] and _inside(b, ctx["figures"]) and n < 80:
        return "figure-label"
    if REF_ITEM.match(text):
        return "reference"
    math_ratio = (len([c for c in text if c in layout.MATH_CHARS])
                  + 2 * len(MATH_PUA.findall(text))) / max(1, len(text))
    if n <= 40 and not sent_end(text):
        if HEADING_NUM.match(text) and (b["bold"] or size >= fs * 0.97):
            return "heading"
        if HEADING_WORDS.match(text) and (b["bold"] or size > fs * 1.02 or text.isupper()):
            return "heading"
        if (b["bold"] or size > fs * 1.18) and n <= 14:
            return "heading"
        if text.isupper() and n <= 6 and not re.search(r"[a-z]", text):
            return "heading"
    if AFFIL.match(text) and n <= 40:
        return "authors"
    if (ctx["page"] == 1 and ctx["seen_title"] and not ctx["seen_abstract"]
            and b.get("centered") and n <= 25):
        return "authors"
    if (n <= 200 and math_ratio > 0.10) or (MATH_PUA.search(text) and math_ratio > 0.06):
        return "equation"
    if n <= 30 and EQ_NUM.search(text) and re.search(r"[=<>≈≤≥]", text):
        return "equation"
    if size < 0.86 * fs and n < 60 and b["y0"] > 0.75 * ph:
        return "footnote"
    if ctx["page"] == 1 and ctx["seen_title"] and not ctx["seen_abstract"] and n >= 25:
        return "abstract"
    if n <= 8 and not sent_end(text):
        return "fragment"
    return "body"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default=None)
    ap.add_argument("--todo", default=None)
    ap.add_argument("--scope", default=None)
    ap.add_argument("--backend", default=None)
    a = ap.parse_args(argv)

    try:
        pages, backend, warnings = pdfwords.extract(a.pdf, a.backend)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    if not any(p["lines"] for p in pages):
        print(json.dumps({"ok": False, "error": "no-text-layer: PDF has no extractable text; "
                                                "run OCR (platform ocr-tool) or pass text"},
                         ensure_ascii=False))
        return 3

    wordlist = layout.build_wordlist(pages)
    size_w = Counter()
    for p in pages:
        for ln in p["lines"]:
            size_w[round(ln["size"], 1)] += len(ln["text"])
    body_size = size_w.most_common(1)[0][0] if size_w else 10.0

    segments = []
    seen_title = seen_abstract = seen_heading = False
    refs_mode = False
    ref_run = 0
    section, section_level = "", 0
    figs = {p["page"]: p.get("figures", []) for p in pages}
    for page, page_w, page_h, blocks in layout.page_blocks(pages, wordlist):
        for b in blocks:
            ctx = {"body_size": body_size, "page": page, "page_height": page_h,
                   "seen_title": seen_title, "seen_abstract": seen_abstract,
                   "refs_mode": refs_mode, "figures": figs.get(page, [])}
            kind = classify(b, ctx)
            if kind == "reference":
                ref_run += 1
                if ref_run >= 2:
                    refs_mode = True
            else:
                ref_run = 0
            if kind == "title":
                seen_title = True
            elif kind == "heading":
                seen_heading = True
                section = re.sub(r"\s+", " ", b["text"]).strip().rstrip(".")
                section_level = (1 if HEADING_NUM.match(section)
                                 else section.count(".") + 1)
                if re.match(r"^(references?|bibliography)\b", section, re.I):
                    refs_mode = True
                if re.match(r"^abstract\b", section, re.I):
                    seen_abstract = True
            elif kind == "abstract":
                seen_abstract = True
            seg = {
                "pid": "P%04d" % (len(segments) + 1),
                "kind": kind,
                "section": section,
                "section_level": section_level,
                "page": page,
                "bbox": [round(b["x0"], 1), round(b["y0"], 1),
                         round(b["x1"], 1), round(b["y1"], 1)],
                "zone": b["zone"],
                "text": b["text"],
                "sentences": split_sentences(b["text"]),
                "words": len(b["text"].split()),
                "chars": len(b["text"]),
            }
            segments.append(seg)

    # figure-internal labels for backends without figure geometry: short blocks
    # sitting just above a caption in the same column are treated as figure text
    caps = {}
    for s in segments:
        if s["kind"] == "caption":
            caps.setdefault(s["page"], []).append(s["bbox"])
    for s in segments:
        if s["kind"] in ("heading", "fragment", "equation") and s["words"] <= 14:
            for cb in caps.get(s["page"], []):
                x_overlap = min(s["bbox"][2], cb[2]) - max(s["bbox"][0], cb[0])
                if (s["bbox"][1] > cb[1] - 0.45 * 792.0 and s["bbox"][3] < cb[1] + 2
                        and x_overlap > 0.3 * (s["bbox"][2] - s["bbox"][0])):
                    s["kind"] = "figure-label"
                    break

    # merge runs of tiny non-prose segments (figure ticks, equation fragments,
    # table glyphs) on the same page so the inventory stays readable
    glued = []
    for s in segments:
        if glued:
            p = glued[-1]
            tiny = {"equation", "fragment", "figure-label"}
            if (p["kind"] in tiny and s["kind"] in tiny and s["page"] == p["page"]
                    and p["words"] <= 30 and s["words"] <= 30
                    and s["bbox"][1] - p["bbox"][3] < 24):
                p["text"] = p["text"] + " " + s["text"]
                p["words"] = len(p["text"].split())
                p["chars"] = len(p["text"])
                p["bbox"][2] = max(p["bbox"][2], s["bbox"][2])
                p["bbox"][3] = max(p["bbox"][3], s["bbox"][3])
                if p["kind"] == "fragment" and s["kind"] == "equation":
                    p["kind"] = "equation"
                continue
        glued.append(s)
    segments = glued

    # merge paragraphs continued across a page break (figure pages may intervene)
    page_h = {p["page"]: p["height"] for p in pages}
    merged = []
    for s in segments:
        if s["kind"] == "body":
            j = None
            for k in range(len(merged) - 1, -1, -1):
                if merged[k]["kind"] == "body":
                    j = k
                    break
            if j is not None:
                prev = merged[j]
                no_body_between = all(x["kind"] != "body" for x in merged[j + 1:])
                page_far = s["page"] - prev.get("page_end", prev["page"])
                at_top = s["bbox"][1] < 0.20 * page_h.get(s["page"], 792.0)
                continues = (s["text"][:1].islower() or at_top
                             or re.match(r"^[\(\[a-z]", s["text"])
                             or bool(re.search(r"[=≈≤≥]", s["text"][:40])))
                if no_body_between and 0 < page_far <= 2 and not sent_end(prev["text"]) and continues:
                    prev["text"] = prev["text"] + " " + s["text"]
                    prev["sentences"] = split_sentences(prev["text"])
                    prev["words"] = len(prev["text"].split())
                    prev["chars"] = len(prev["text"])
                    prev["page_end"] = s["page"]
                    prev["continued"] = True
                    continue
        merged.append(s)
    for i, s in enumerate(merged, 1):
        s["pid"] = "P%04d" % i
    segments = merged
    for s in segments:
        if s["kind"] == "body" and s["words"] <= 5 and not sent_end(s["text"]):
            s["kind"] = "fragment"
    seen_ref = False
    for s in segments:
        if s["kind"] == "reference":
            seen_ref = True
        elif seen_ref and s["kind"] in ("body", "fragment") and s["words"] <= 40:
            s["kind"] = "reference"

    stats = {"segments": len(segments), "words": sum(s["words"] for s in segments),
             "pages": len(pages),
             "translatable": sum(1 for s in segments if s["kind"] in TRANSLATABLE),
             "by_kind": {}}
    for s in segments:
        stats["by_kind"][s["kind"]] = stats["by_kind"].get(s["kind"], 0) + 1

    doc = {
        "schema": "translation-segments/v1",
        "source": {"file": os.path.basename(a.pdf), "sha256": pdfwords.sha256_file(a.pdf),
                   "pages": len(pages), "backend": backend},
        "typography": {"body_size": body_size},
        "segments": segments,
        "stats": stats,
        "warnings": warnings,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    md_path = a.md or (a.out[:-5] + ".md" if a.out.endswith(".json") else None)
    if md_path:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Segments: %s\n\n" % doc["source"]["file"])
            f.write("backend=%s pages=%d segments=%d words=%d\n\n" %
                    (backend, stats["pages"], stats["segments"], stats["words"]))
            for s in segments:
                f.write("### %s | p%d | %s | %s\n\n" %
                        (s["pid"], s["page"], s["kind"], s["section"] or "-"))
                f.write(s["text"] + "\n\n")

    todo_path = a.todo or (os.path.dirname(os.path.abspath(a.out)) + "/translate.todo.jsonl")
    with open(todo_path, "w", encoding="utf-8") as f:
        for s in segments:
            if s["kind"] in TRANSLATABLE:
                f.write(json.dumps({"pid": s["pid"], "kind": s["kind"],
                                    "section": s["section"], "page": s["page"],
                                    "source": s["text"], "zh": ""},
                                   ensure_ascii=False) + "\n")

    scope_path = a.scope or (os.path.dirname(os.path.abspath(a.out)) + "/scope.json")
    with open(scope_path, "w", encoding="utf-8") as f:
        json.dump({"mode": "full",
                   "pids": [s["pid"] for s in segments if s["kind"] in TRANSLATABLE],
                   "verbatim_pids": [s["pid"] for s in segments if s["kind"] in VERBATIM]},
                  f, ensure_ascii=False, indent=1)

    print(json.dumps({"ok": True, "backend": backend, "pages": len(pages),
                      "segments": len(segments), "translatable": stats["translatable"],
                      "words": stats["words"], "by_kind": stats["by_kind"],
                      "out": os.path.abspath(a.out), "md": md_path,
                      "todo": os.path.abspath(todo_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
