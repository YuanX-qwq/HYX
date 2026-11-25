#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gloss.py -- terminology candidate extraction and glossary locking.

Why a script instead of a prompt: a glossary that only lives inside a prompt is
not enforced.  Here the glossary is a CSV/JSON artefact with a lock step, and
``verify.py`` re-scans every translated paragraph against it.  A term that drifts
is reported with the offending paragraph ids, so the agent must fix it instead
of silently paraphrasing.

Commands
--------
  extract --segments SEGMENTS.json --out glossary.candidates.csv [--seed FILE]
          [--min-freq 2] [--max-terms 200]
  lock    --glossary glossary.csv --segments SEGMENTS.json --out glossary.json
          [--require-all]   # fail if any candidate row has an empty term_zh
  stats   --glossary glossary.json

Glossary CSV columns (header required):
  term_en,term_zh,category,variants,note
   - term_zh may be empty in the candidates file: fill it before locking.
   - variants is an optional ``|``-separated list of accepted Chinese spellings.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ACRO = re.compile(r"\b[A-Z][A-Za-z0-9]{1,6}(?:-[A-Za-z0-9]+)?\b")
CAP_WORD = r"[A-Z][A-Za-z-]{2,}"
CAP_PHRASE = re.compile(r"\b%s(?:\s+(?:of|for|and|in|the)?\s*%s){0,3}\b" % (CAP_WORD, CAP_WORD))
STOP = set("""
the a an and or but if then than that this these those with without within from into onto
for of to in on at by as is are was were be been being it its their our we you they he she
which who whom whose what when where why how not no nor can could may might must should
have has had do does did done also such more most less least other another both each few
many much some any all only own same so very just about above after again against below
between during before under over out off up down such while because however therefore thus
figure figures fig table tables equation equations section sections ref refs reference
references appendix supplementary note notes data set sets result results method methods
here there where when then once while using used use show shows shown find found
""".split())


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\u00a0", " ")).strip()


def load_segments(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_seed(path):
    seed = {}
    if not path or not os.path.exists(path):
        return seed
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            en = norm(row.get("term_en") or row.get("en") or "")
            zh = norm(row.get("term_zh") or row.get("zh") or "")
            if en and zh:
                seed[en.lower()] = (en, zh, norm(row.get("category") or ""))
    return seed


def extract(doc, seed, min_freq=2, max_terms=200):
    counts = Counter()
    first = {}
    pids = defaultdict(set)
    for s in doc["segments"]:
        if s["kind"] in ("reference", "header", "footer", "margin"):
            continue
        text = s["text"]
        for m in ACRO.finditer(text):
            t = m.group(0)
            if t.lower() in STOP or t.isdigit():
                continue
            counts[t] += 1
            first.setdefault(t, s["pid"])
            pids[t].add(s["pid"])
        for m in CAP_PHRASE.finditer(text):
            t = norm(m.group(0))
            words = t.split()
            if len(words) < 2:
                continue
            if all(w.lower() in STOP for w in words):
                continue
            counts[t] += 1
            first.setdefault(t, s["pid"])
            pids[t].add(s["pid"])
        low = text.lower()
        for en, (orig, zh, cat) in seed.items():
            if en in low:
                counts[orig] += low.count(en)
                first.setdefault(orig, s["pid"])
                pids[orig].add(s["pid"])
    # drop terms that are a substring of a longer term with the same count
    terms = [t for t, c in counts.items() if c >= min_freq]
    terms.sort(key=lambda t: (-counts[t], t.lower()))
    keep = []
    for t in terms:
        tl = t.lower()
        dominated = False
        for u in terms:
            ul = u.lower()
            if u != t and tl in ul and counts[u] >= counts[t] and len(u.split()) > len(t.split()):
                dominated = True
                break
        if not dominated:
            keep.append(t)
    keep = keep[:max_terms]
    rows = []
    for t in keep:
        en_seed = seed.get(t.lower())
        rows.append({
            "term_en": t,
            "term_zh": en_seed[1] if en_seed else "",
            "category": en_seed[2] if en_seed else "",
            "variants": "",
            "note": "seed" if en_seed else "",
            "occurrences": counts[t],
            "pids": ",".join(sorted(pids[t])[:8]),
        })
    return rows


def cmd_extract(a):
    doc = load_segments(a.segments)
    seed = load_seed(a.seed)
    rows = extract(doc, seed, a.min_freq, a.max_terms)
    fields = ["term_en", "term_zh", "category", "variants", "note", "occurrences", "pids"]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(json.dumps({"ok": True, "terms": len(rows), "filled": sum(1 for r in rows if r["term_zh"]),
                      "out": os.path.abspath(a.out)}, ensure_ascii=False))
    return 0


def read_glossary_csv(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        for i, row in enumerate(rd, 2):
            en = norm(row.get("term_en") or "")
            zh = norm(row.get("term_zh") or "")
            if not en and not zh:
                continue
            rows.append({
                "line": i, "term_en": en, "term_zh": zh,
                "category": norm(row.get("category") or ""),
                "variants": [v.strip() for v in re.split(r"[|;]", row.get("variants") or "") if v.strip()],
                "note": norm(row.get("note") or ""),
            })
    return rows


def cmd_lock(a):
    rows = read_glossary_csv(a.glossary)
    problems, seen_en, seen_zh = [], {}, {}
    terms = []
    for r in rows:
        if not r["term_en"]:
            problems.append({"line": r["line"], "issue": "empty term_en"})
            continue
        if not r["term_zh"]:
            problems.append({"line": r["line"], "issue": "missing term_zh", "term_en": r["term_en"]})
            continue
        key = r["term_en"].lower()
        if key in seen_en:
            problems.append({"line": r["line"], "issue": "duplicate term_en",
                             "term_en": r["term_en"]})
            continue
        if r["term_zh"] in seen_zh:
            problems.append({"line": r["line"], "issue": "same term_zh for two terms",
                             "term_en": r["term_en"], "other": seen_zh[r["term_zh"]]})
        seen_en[key] = r["term_en"]
        seen_zh[r["term_zh"]] = r["term_en"]
        terms.append({
            "term_en": r["term_en"], "term_zh": r["term_zh"],
            "category": r["category"], "variants": r["variants"],
            "note": r["note"], "locked": True,
        })
    hard = [p for p in problems if p["issue"] in ("duplicate term_en", "empty term_en",
                                                  "same term_zh for two terms")]
    if a.require_all and problems:
        hard = problems
    out = {"schema": "glossary-lock/v1", "source": os.path.basename(a.glossary),
           "terms": terms, "problems": problems,
           "locked": not hard, "stats": {"terms": len(terms), "problems": len(problems)}}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({"ok": not hard, "terms": len(terms), "problems": problems[:10],
                      "locked": out["locked"], "out": os.path.abspath(a.out)}, ensure_ascii=False))
    return 0 if not hard else 1


def cmd_stats(a):
    with open(a.glossary, encoding="utf-8") as f:
        g = json.load(f)
    print(json.dumps({"terms": len(g.get("terms", [])), "locked": g.get("locked"),
                      "problems": len(g.get("problems", []))}, ensure_ascii=False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("extract")
    p.add_argument("--segments", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--seed", default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "resources", "glossary.seed.csv"))
    p.add_argument("--min-freq", type=int, default=2)
    p.add_argument("--max-terms", type=int, default=200)
    p.set_defaults(func=cmd_extract)
    p = sub.add_parser("lock")
    p.add_argument("--glossary", required=True)
    p.add_argument("--segments", default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--require-all", action="store_true")
    p.set_defaults(func=cmd_lock)
    p = sub.add_parser("stats")
    p.add_argument("--glossary", required=True)
    p.set_defaults(func=cmd_stats)
    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
