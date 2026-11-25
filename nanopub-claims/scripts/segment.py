#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""segment.py — 把页面文本切成带页码与字符偏移的段落。

用法:
  python3 segment.py --pages pages.json --out work/paragraphs.json
  python3 segment.py --text paper.txt --page 1 --out work/paragraphs.json

pages.json 形态: [{"page": 1, "text": "...整页文本..."}, ...]
输出: {"page_count": N, "text_sha256": "...", "paragraphs": [{id,page,text,norm,char_start,char_end}]}
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claimlib import paragraphs_from_pages, read_json, sha256_text, write_json  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", help="页面 JSON（[{'page','text'}]）")
    ap.add_argument("--text", help="纯文本文件")
    ap.add_argument("--page", type=int, default=1, help="纯文本模式下的页码")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.pages:
        pages = read_json(args.pages)
    elif args.text:
        raw = open(args.text, encoding="utf-8").read()
        pages = [{"page": args.page, "text": raw}]
    else:
        ap.error("必须给 --pages 或 --text")

    paras = paragraphs_from_pages(pages)
    out = {
        "page_count": len({p["page"] for p in paras}) or len(pages),
        "text_sha256": sha256_text("".join(p["text"] for p in paras)),
        "paragraphs": paras,
    }
    write_json(args.out, out)
    print(json.dumps({"paragraphs": len(paras), "pages": out["page_count"], "out": args.out},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
