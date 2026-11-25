#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evidence.py — 证据定位、绑定与核验（三个子命令）。

  locate  : 在段落里找某句逐字引文，打印命中段落与字符偏移
  bind    : 给 assertions 的 evidence 回填 page / paragraph_id / char_start / char_end
  verify  : 机械核验——引文是否逐字、偏移是否与引文一致（Q003 / Q010）

用法:
  python3 evidence.py locate --paragraphs work/paragraphs.json --quote "the measured value was 12.5 h"
  python3 evidence.py bind   --assertions work/assertions.json --paragraphs work/paragraphs.json
  python3 evidence.py verify --assertions work/assertions.json --paragraphs work/paragraphs.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claimlib import (locate_quote, quote_in_document, read_json, same_text,  # noqa: E402
                      write_json)


def cmd_locate(args):
    doc = read_json(args.paragraphs)
    hits = []
    for p in doc["paragraphs"]:
        span = locate_quote(p["text"], args.quote)
        if span:
            hits.append({"paragraph_id": p["id"], "page": p["page"],
                         "char_start": span[0], "char_end": span[1],
                         "exact": norm_ws(p["text"][span[0]:span[1]]) == norm_ws(args.quote)})
    print(json.dumps({"quote": args.quote, "hits": len(hits), "matches": hits}, ensure_ascii=False, indent=2))
    return 0 if hits else 2


def cmd_bind(args):
    doc = read_json(args.paragraphs)
    data = read_json(args.assertions)
    assertions = data["assertions"] if isinstance(data, dict) else data
    paras = doc["paragraphs"]
    unbound = []
    for a in assertions:
        for ev in a.get("evidence", []):
            quote = ev.get("quote", "")
            if not quote:
                continue
            span, para = None, None
            # 若已指定段落，优先在该段落定位
            preferred = [p for p in paras if p["id"] == ev.get("paragraph_id")]
            for p in preferred + [p for p in paras if p not in preferred]:
                span = locate_quote(p["text"], quote)
                if span:
                    para = p
                    break
            if not span:
                unbound.append({"assertion_id": a.get("id"), "quote": quote})
                continue
            ev["page"] = para["page"]
            ev["paragraph_id"] = para["id"]
            ev["char_start"] = span[0]
            ev["char_end"] = span[1]
    write_json(args.assertions, data)
    print(json.dumps({"bound": sum(len(a.get("evidence", [])) for a in assertions) - len(unbound),
                      "unbound": len(unbound), "unbound_detail": unbound}, ensure_ascii=False, indent=2))
    return 0 if not unbound else 2


def cmd_verify(args):
    doc = read_json(args.paragraphs)
    data = read_json(args.assertions)
    assertions = data["assertions"] if isinstance(data, dict) else data
    paras = doc["paragraphs"]
    fails, oks = [], 0
    for a in assertions:
        for ev in a.get("evidence", []):
            quote = ev.get("quote", "")
            if not quote:
                fails.append({"assertion_id": a.get("id"), "code": "Q002", "detail": "quote 为空"})
                continue
            if not quote_in_document(quote, paras):
                fails.append({"assertion_id": a.get("id"), "code": "Q003", "detail": "引文非逐字"})
                continue
            para = next((p for p in paras if p["id"] == ev.get("paragraph_id")), None)
            st, en = ev.get("char_start"), ev.get("char_end")
            if para is None or not isinstance(st, int) or not isinstance(en, int) or st >= en:
                fails.append({"assertion_id": a.get("id"), "code": "Q010", "detail": "偏移缺失或不合法"})
                continue
            if not same_text(para["text"][st:en], quote):
                fails.append({"assertion_id": a.get("id"), "code": "Q010",
                              "detail": f"paragraph_text[{st}:{en}] 与 quote 不一致"})
                continue
            oks += 1
    print(json.dumps({"verified": oks, "failed": len(fails), "failures": fails},
                     ensure_ascii=False, indent=2))
    return 0 if not fails else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("locate")
    p1.add_argument("--paragraphs", required=True)
    p1.add_argument("--quote", required=True)
    p2 = sub.add_parser("bind")
    p2.add_argument("--assertions", required=True)
    p2.add_argument("--paragraphs", required=True)
    p3 = sub.add_parser("verify")
    p3.add_argument("--assertions", required=True)
    p3.add_argument("--paragraphs", required=True)
    args = ap.parse_args()
    return {"locate": cmd_locate, "bind": cmd_bind, "verify": cmd_verify}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
