#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export.py — 导出可机器读取的三种形态（JSON / CSV / TriG nanopublication）。

用法:
  python3 export.py --assertions work/assertions.json --out-dir output --source source.json

产出:
  <out-dir>/assertion_set.json   规范 JSON（含 source / document / assertions / qc_summary）
  <out-dir>/assertions.csv       扁平 CSV（19 列，下游可直接解析）
  <out-dir>/nanopub.trig         TriG：assertion / provenance / pubInfo 三个子图

确定性：同一输入重复运行，三个文件逐字节一致（不含时间戳、不含随机 ID）。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claimlib import read_json, to_csv, to_trig, write_json  # noqa: E402

REQUIRED = ("id", "text", "subject", "relation", "object", "evidence", "provenance_ref", "confidence", "qc")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assertions", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--source", help="source 元数据 JSON（不给则用 assertions 里已有的 source）")
    ap.add_argument("--case-id", default=None)
    ap.add_argument("--status", default=None)
    args = ap.parse_args()

    data = read_json(args.assertions)
    assertions = data["assertions"] if isinstance(data, dict) else data
    missing = [(a.get("id"), [k for k in REQUIRED if k not in a]) for a in assertions]
    missing = [(i, ks) for i, ks in missing if ks]
    if missing:
        print(json.dumps({"error": "断言缺少必需字段", "detail": missing}, ensure_ascii=False, indent=2))
        return 2

    source = read_json(args.source) if args.source else data.get("source", {})
    out = {
        "schema_version": "nanopub-claims/1.0",
        "case_id": args.case_id or data.get("case_id", "unknown-case"),
        "status": args.status or data.get("status", "success"),
        "source": source,
        "document": data.get("document", {}),
        "assertions": assertions,
        "unreported": data.get("unreported", []),
        "uncertainty": data.get("uncertainty", []),
        "qc_summary": data.get("qc_summary", {}),
        "change_log": data.get("change_log", []),
    }

    os.makedirs(args.out_dir, exist_ok=True)
    write_json(os.path.join(args.out_dir, "assertion_set.json"), out)
    with open(os.path.join(args.out_dir, "assertions.csv"), "w", encoding="utf-8", newline="") as fh:
        fh.write(to_csv(assertions))
    with open(os.path.join(args.out_dir, "nanopub.trig"), "w", encoding="utf-8") as fh:
        fh.write(to_trig(assertions, source))

    print(json.dumps({"assertions": len(assertions),
                      "files": ["assertion_set.json", "assertions.csv", "nanopub.trig"],
                      "out_dir": args.out_dir}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
