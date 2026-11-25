#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdfwords.py -- extract page lines (text + bbox + font size) from PDF/TXT/MD.

Only the Python standard library is required.  Three optional PDF backends are
tried in order and the first one that works wins:

    1. PyMuPDF   ``import pymupdf`` or ``import fitz``
    2. pdfplumber
    3. poppler   ``pdftotext -bbox-layout`` (XML output)

Plain-text inputs (``.txt`` / ``.md``) are converted to pseudo-lines that keep
paragraph boundaries, so the rest of the pipeline is identical for PDF and text.

Output contract (JSON)::

    {
      "schema": "paper-lines/v1",
      "source": {"file": ..., "sha256": ..., "pages": N, "backend": ..., "encrypted": bool},
      "pages": [{"page": 1, "width": 612.0, "height": 792.0, "lines": [Line, ...]}, ...],
      "warnings": [...]
    }

Line = {"page": int, "text": str, "x0","y0","x1","y1": float,
        "size": float, "bold": bool, "italic": bool}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

# ---------------------------------------------------------------- text hygiene
LIGATURES = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi",
    "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st",
}
MODIFIER_MAP = {
    "\u00ad": "",      # soft hyphen
    "\u00a0": " ",     # nbsp
    "\u2009": " ", "\u202f": " ", "\u2007": " ", "\u2002": " ", "\u2003": " ",
    "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "--",
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
}
INVISIBLE_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(s: str) -> str:
    """Normalise whitespace and replace ligatures / invisible characters."""
    if not s:
        return ""
    for a, b in LIGATURES.items():
        s = s.replace(a, b)
    for a, b in MODIFIER_MAP.items():
        s = s.replace(a, b)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = INVISIBLE_CTRL.sub("", s)
    s = s.replace("\u00a0", " ")
    # collapse runs of spaces (justified PDF text often has wide gaps)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    return s.strip()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- PDF backends
def _lines_from_pymupdf(path: str):
    doc = None
    for mod in ("pymupdf", "fitz"):
        try:
            doc = __import__(mod)
            break
        except Exception:
            continue
    if doc is None:
        raise ImportError("pymupdf/fitz not importable")
    d = doc.open(path)
    if getattr(d, "needs_pass", False) and not d.authenticate(""):
        raise RuntimeError("encrypted-pdf")
    pages = []
    for pno in range(len(d)):
        page = d[pno]
        rect = page.rect
        raw = page.get_text("dict")
        out = []
        for block in raw.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "")]
                if not any(s["text"].strip() for s in spans):
                    continue
                spans.sort(key=lambda s: s["bbox"][0])
                size0 = max((s.get("size") or 10.0) for s in spans)
                buf = []
                prev_x1 = None
                for s in spans:
                    if prev_x1 is not None and s["bbox"][0] - prev_x1 > 0.22 * size0:
                        buf.append(" ")
                    buf.append(s["text"])
                    prev_x1 = max(prev_x1 or 0.0, s["bbox"][2])
                text = clean_text("".join(buf))
                x0 = min(s["bbox"][0] for s in spans)
                y0 = min(s["bbox"][1] for s in spans)
                x1 = max(s["bbox"][2] for s in spans)
                y1 = max(s["bbox"][3] for s in spans)
                size = max((s.get("size") or 0.0) for s in spans) or (y1 - y0)
                fonts = " ".join(str(s.get("font", "")) for s in spans).lower()
                flags = 0
                for s in spans:
                    flags |= int(s.get("flags") or 0)
                direction = line.get("dir") or (1.0, 0.0)
                rot = abs(float(direction[0]) - 1.0) > 0.01 or abs(float(direction[1])) > 0.01
                out.append({
                    "page": pno + 1,
                    "text": text,
                    "rotated": bool(rot),
                    "x0": round(x0, 2), "y0": round(y0, 2),
                    "x1": round(x1, 2), "y1": round(y1, 2),
                    "size": round(float(size), 2),
                    "bold": bool("bold" in fonts or (flags & 16)),
                    "italic": bool("italic" in fonts or "oblique" in fonts or (flags & 2)),
                })
        pages.append({"page": pno + 1, "width": round(rect.width, 2),
                      "height": round(rect.height, 2), "lines": out,
                      "figures": _figure_boxes(page, rect)})
    return pages, "pymupdf"


def _figure_boxes(page, rect):
    """Raster images + large vector drawings, merged into figure regions."""
    boxes = []
    try:
        for info in page.get_image_info():
            b = info.get("bbox")
            if b:
                boxes.append([float(b[0]), float(b[1]), float(b[2]), float(b[3])])
    except Exception:
        pass
    try:
        area = float(rect.width * rect.height)
        for d in page.get_drawings():
            r = d.get("rect")
            if r is None:
                continue
            if float(r.width) * float(r.height) > 0.015 * area:
                boxes.append([float(r.x0), float(r.y0), float(r.x1), float(r.y1)])
    except Exception:
        pass
    merged = []
    for b in boxes:
        for o in merged:
            if not (b[2] < o[0] - 6 or b[0] > o[2] + 6 or b[3] < o[1] - 6 or b[1] > o[3] + 6):
                o[0] = min(o[0], b[0]); o[1] = min(o[1], b[1])
                o[2] = max(o[2], b[2]); o[3] = max(o[3], b[3])
                break
        else:
            merged.append(list(b))
    area = float(rect.width * rect.height)
    return [o for o in merged if (o[2] - o[0]) * (o[3] - o[1]) > 0.012 * area]


def _lines_from_pdfplumber(path: str):
    import pdfplumber  # noqa: F401
    pages = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False,
                                       extra_attrs=["size"])
            # cluster words into lines by rounded 'top'
            buckets = {}
            for w in words:
                key = round(float(w["top"]) / 3.0)
                buckets.setdefault(key, []).append(w)
            out = []
            for key in sorted(buckets):
                ws = sorted(buckets[key], key=lambda w: float(w["x0"]))
                text = " ".join(clean_text(w["text"]) for w in ws)
                text = re.sub(r"\s+", " ", text).strip()
                if not text:
                    continue
                out.append({
                    "page": pno, "text": text,
                    "x0": round(float(ws[0]["x0"]), 2),
                    "y0": round(min(float(w["top"]) for w in ws), 2),
                    "x1": round(max(float(w["x1"]) for w in ws), 2),
                    "y1": round(max(float(w["bottom"]) for w in ws), 2),
                    "size": round(max(float(w.get("size") or 0) for w in ws), 2) or 10.0,
                    "bold": False, "italic": False,
                })
            pages.append({"page": pno, "width": round(float(page.width), 2),
                          "height": round(float(page.height), 2), "lines": out})
    return pages, "pdfplumber"


def _unescape_xml(s: str) -> str:
    s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    s = s.replace("&apos;", "'").replace("&amp;", "&")
    s = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
    return s


def _lines_from_pdftotext(path: str):
    """poppler ``-bbox-layout`` XML, parsed with regex.

    poppler can emit raw control bytes (e.g. \\x01) inside <word>, which makes a
    strict XML parser fail on real papers; the regex path tolerates that.
    """
    exe = shutil.which("pdftotext")
    if not exe:
        raise RuntimeError("pdftotext not found")
    raw = subprocess.run([exe, "-bbox-layout", "-enc", "UTF-8", path, "-"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
    page_re = re.compile(r'<page width="([\d.]+)" height="([\d.]+)"[^>]*>(.*?)</page>', re.S)
    line_re = re.compile(r"<line\b[^>]*>(.*?)</line>", re.S)
    word_re = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
                         r'yMax="([\d.]+)"[^>]*>(.*?)</word>', re.S)
    pages = []
    for pno, (w, h, body) in enumerate(page_re.findall(raw), 1):
        lines = []
        for lb in line_re.findall(body):
            words = []
            for x0, y0, x1, y1, txt in word_re.findall(lb):
                t = clean_text(_unescape_xml(txt))
                if t:
                    words.append((float(x0), float(y0), float(x1), float(y1), t))
            if not words:
                continue
            lines.append({
                "page": pno, "text": " ".join(x[4] for x in words),
                "x0": round(min(x[0] for x in words), 2),
                "y0": round(min(x[1] for x in words), 2),
                "x1": round(max(x[2] for x in words), 2),
                "y1": round(max(x[3] for x in words), 2),
                "size": round(max(x[3] - x[1] for x in words), 2),
                "bold": False, "italic": False,
            })
        pages.append({"page": pno, "width": float(w), "height": float(h), "lines": lines})
    if not pages or not any(p["lines"] for p in pages):
        # last resort: plain text with form-feed page breaks, no word boxes
        txt = subprocess.run([exe, "-enc", "UTF-8", path, "-"],
                             capture_output=True, check=True).stdout.decode("utf-8", "replace")
        txt = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", txt)
        pages = []
        for pno, chunk in enumerate(txt.split("\f"), 1):
            lines = []
            y = 72.0
            for para in re.split(r"\n\s*\n", chunk):
                text = clean_text(re.sub(r"\s*\n\s*", " ", para))
                if not text:
                    continue
                lines.append({"page": pno, "text": text, "x0": 72.0, "y0": y,
                              "x1": 540.0, "y1": y + 12.0, "size": 11.0,
                              "bold": False, "italic": False, "_solo": True})
                y += 14.0 + 12.0 * (len(text) // 90)
            pages.append({"page": pno, "width": 612.0, "height": 792.0, "lines": lines})
    return pages, "pdftotext"


def _lines_from_text(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    lines = []
    y = 100.0
    for i, p in enumerate(paras):
        text = re.sub(r"\s*\n\s*", " ", p).strip()
        text = clean_text(text)
        if not text:
            continue
        n = max(1, len(text) // 80 + 1)
        lines.append({"page": 1, "text": text, "x0": 72.0, "y0": y,
                      "x1": 540.0, "y1": y + 12.0,
                      "size": 16.0 if i == 0 else 11.0,
                      "bold": i == 0, "italic": False, "_solo": True})
        y += 12.0 * n + 10.0
    return [{"page": 1, "width": 612.0, "height": max(792.0, y + 72), "lines": lines}], "text"


def extract(path: str, backend: str | None = None):
    """Return (pages, backend_name, warnings)."""
    ext = os.path.splitext(path)[1].lower()
    warnings = []
    if ext in (".txt", ".md", ".markdown"):
        pages, name = _lines_from_text(path)
        return pages, name, warnings
    order = [backend] if backend else ["pymupdf", "pdfplumber", "pdftotext"]
    fns = {"pymupdf": _lines_from_pymupdf, "pdfplumber": _lines_from_pdfplumber,
           "pdftotext": _lines_from_pdftotext}
    errors = []
    for name in order:
        try:
            pages, used = fns[name](path)
            if not any(p["lines"] for p in pages):
                errors.append("%s: no-text-layer" % name)
                continue
            return pages, used, warnings
        except Exception as e:  # try next backend
            errors.append("%s: %s" % (name, str(e)[:160]))
    raise RuntimeError("all PDF backends failed: " + " | ".join(errors))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Extract page lines from a PDF/text file")
    ap.add_argument("--pdf", required=True, help="input PDF / TXT / MD")
    ap.add_argument("--out", required=True)
    ap.add_argument("--backend", default=None,
                    choices=["pymupdf", "pdfplumber", "pdftotext", "text"])
    a = ap.parse_args(argv)
    try:
        pages, backend, warnings = extract(a.pdf, a.backend)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    doc = {
        "schema": "paper-lines/v1",
        "source": {"file": os.path.basename(a.pdf), "sha256": sha256_file(a.pdf),
                   "pages": len(pages), "backend": backend,
                   "encrypted": "encrypted-pdf" in " ".join(warnings)},
        "pages": pages,
        "warnings": warnings,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    n_lines = sum(len(p["lines"]) for p in pages)
    print(json.dumps({"ok": True, "backend": backend, "pages": len(pages),
                      "lines": n_lines, "out": os.path.abspath(a.out)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
