#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decompose.py — 段落 -> 候选断言（机械切分，不做语义判断）。

切分两层：句末标点 -> 句；并列/因果连接词 -> 候选。
斜杠/分号并列的枚举项会被切出来，交给 agent 逐条补 subject/relation/object。

用法:
  python3 decompose.py --paragraphs work/paragraphs.json --out work/candidates.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claimlib import candidates_from_paragraphs, read_json, write_json  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paragraphs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-chars", type=int, default=8,
                    help="短于该长度的候选标记 short=true（通常是表头/编号，需人工判断）")
    args = ap.parse_args()

    doc = read_json(args.paragraphs)
    cands = candidates_from_paragraphs(doc["paragraphs"])
    for c in cands:
        c["short"] = len(c["text"]) < args.min_chars
    write_json(args.out, {"candidate_count": len(cands), "candidates": cands})
    print(json.dumps({"candidates": len(cands), "short": sum(1 for c in cands if c["short"]),
                      "out": args.out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
