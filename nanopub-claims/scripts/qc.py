#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qc.py — 断言质量检查（Q001-Q013，逐条给出可复现判定依据）。

用法:
  python3 qc.py --assertions work/assertions.json --paragraphs work/paragraphs.json \\
      --vocab vocab/predicates.json --out work/qc_report.json [--allow-fail]

退出码: 0 = 无 fail（warn 允许）；1 = 存在 fail（除非 --allow-fail）。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claimlib import qc_assertion_set, read_json, write_json  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assertions", required=True)
    ap.add_argument("--paragraphs", required=True)
    ap.add_argument("--vocab", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-fail", action="store_true", help="存在 fail 时仍返回 0")
    args = ap.parse_args()

    doc = read_json(args.paragraphs)
    data = read_json(args.assertions)
    vocab = read_json(args.vocab)
    vocab_map = {p["id"]: p for p in vocab["predicates"]}
    source = data.get("source", {}) if isinstance(data, dict) else {}
    assertions = data["assertions"] if isinstance(data, dict) else data

    summary = qc_assertion_set(assertions, doc["paragraphs"], source, vocab_map)
    if isinstance(data, dict):
        data["qc_summary"] = summary
        write_json(args.assertions, data)
    write_json(args.out, {"summary": summary,
                          "assertions": [{"id": a["id"], "qc": a["qc"]} for a in assertions]})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["status_counts"]["fail"] and not args.allow_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
