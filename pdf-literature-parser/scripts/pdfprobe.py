#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdfprobe.py — PDF 诊断（解析前必须第一步执行）

输出 probe.json:
  file, sha256, size_bytes, pages, page_sizes, encrypted, needs_password,
  backend(可用链), has_text_layer(每页), text_chars(每页), fonts(样本),
  images(每页图片数), warnings

用法:
  python3 pdfprobe.py --pdf paper.pdf --out /app/work/probe.json
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdftool import FitzBackend, PdfPlumberBackend, PdftotextBackend, mojibake_ratio  # noqa: E402


def open_best(path):
    errs = []
    for cls in (FitzBackend, PdfPlumberBackend, PdftotextBackend):
        try:
            return cls(path).open(), errs
        except Exception as e:
            errs.append("%s: %s" % (cls.__name__, str(e)[:160]))
    return None, errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    probe = {"file": os.path.basename(a.pdf), "path": a.pdf, "ok": False}
    h = hashlib.sha256()
    try:
        with open(a.pdf, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        probe["sha256"] = h.hexdigest()
        probe["size_bytes"] = os.path.getsize(a.pdf)
    except OSError as e:
        probe["read_error"] = str(e)

    doc, errs = open_best(a.pdf)
    if doc is None:
        probe["ok"] = False
        probe["backend_errors"] = errs
        probe["advice"] = "无法用任何后端打开；请检查文件是否为有效 PDF 或已损坏。"
    else:
        probe["ok"] = True
        probe["backend"] = doc.backend
        probe["pages"] = doc.pages
        probe["page_sizes"] = doc.page_sizes
        probe["encrypted"] = doc.encrypted
        probe["needs_password"] = doc.needs_password
        probe["producer"] = doc.producer[:200]
        probe["has_text_layer"] = []
        probe["text_chars"] = []
        probe["mojibake"] = []
        fonts = {}
        for pno in range(doc.pages):
            words, _rich = doc.page_words(pno)
            nchars = sum(len(w.text) for w in words)
            probe["has_text_layer"].append(bool(words))
            probe["text_chars"].append(nchars)
            probe["mojibake"].append(round(mojibake_ratio(
                " ".join(w.text for w in words)), 4))
            for w in words:
                if w.font and len(fonts) < 60:
                    fonts[w.font] = fonts.get(w.font, 0) + 1
        probe["fonts"] = fonts
        try:
            doc.close()
        except Exception:
            pass

    probe["warnings"] = []
    if not probe.get("has_text_layer"):
        pass
    else:
        for i, (tl, nc) in enumerate(zip(probe["has_text_layer"], probe["text_chars"])):
            if not tl:
                probe["warnings"].append({"page": i + 1, "code": "no-text-layer",
                                          "detail": "无文字层（扫描件），需要 OCR。"})
            elif nc < 40:
                probe["warnings"].append({"page": i + 1, "code": "sparse-text",
                                          "detail": "文字层极少(%d字符)，疑似扫描件或图片型页面。" % nc})
        for i, m in enumerate(probe["mojibake"]):
            if m > 0.05:
                probe["warnings"].append({"page": i + 1, "code": "mojibake",
                                          "detail": "疑似乱码比例 %.3f" % m})

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(probe, f, ensure_ascii=False, indent=1)
    print(json.dumps({
        "ok": probe["ok"],
        "backend": probe.get("backend"),
        "pages": probe.get("pages"),
        "encrypted": probe.get("encrypted"),
        "pages_without_text_layer": sum(
            1 for t in probe.get("has_text_layer", []) if not t),
        "warnings": len(probe.get("warnings", [])),
        "out": os.path.abspath(a.out),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
