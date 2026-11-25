#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_document.py — PDF -> document.json + document.md（+ 可选逐页 PNG）

用法:
  python3 parse_document.py --pdf paper.pdf --work /app/work --out /app/work/document.json \
      [--md /app/work/document.md] [--ocr] [--ocr-langs eng] [--render]

解析失败返回非零退出码，并把错误写入 stderr；部分成功会写 warnings。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdftool import Parser, render_markdown  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--work", default=None, help="工作目录（渲染 PNG 等）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default=None)
    ap.add_argument("--backend", default=None)
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--ocr-langs", default="eng")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--render-dpi", type=int, default=150)
    ap.add_argument("--max-pages", type=int, default=None)
    a = ap.parse_args()

    workdir = a.work or os.path.dirname(os.path.abspath(a.out))
    os.makedirs(workdir, exist_ok=True)
    try:
        p = Parser(a.pdf, workdir=workdir, backend=a.backend, ocr=a.ocr,
                   ocr_langs=a.ocr_langs, render=a.render,
                   render_dpi=a.render_dpi, max_pages=a.max_pages)
        document = p.parse()
    except Exception as e:
        print("PARSE_ERROR: %s" % e, file=sys.stderr)
        sys.exit(2)

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=1)

    md_path = a.md
    if md_path is None and a.out.endswith(".json"):
        md_path = a.out[:-5] + ".md"
    if md_path:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(render_markdown(document))

    print(json.dumps({
        "ok": True,
        "backend": document["source"]["backend"],
        "pages": document["source"]["pages"],
        "sections": len(document.get("sections", [])),
        "tables": len(document.get("tables", [])),
        "figures": len(document.get("figures", [])),
        "equations": len(document.get("equations", [])),
        "references": len(document.get("references", [])),
        "warnings": len(document.get("warnings", [])),
        "warnings_list": document.get("warnings", []),
        "out": os.path.abspath(a.out),
        "md": os.path.abspath(md_path) if md_path else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
