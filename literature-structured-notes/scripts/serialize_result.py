#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serialize_result.py — 把结构化笔记草稿校验并组装成官方 result.json（标准库）。

results 只允许四个键：paper_card / section_notes / knowledge_points / comparison_fields。
硬约束（任一条不满足即拒绝写出）：
  1) 四个键齐备，不得出现契约外键
  2) paper_card 恰含 research_question/data/methods/findings/limitations
  3) section_notes ≥2 且顺序与输入章节一致；每条含 section/purpose/method/result/conclusion/source_id/locator
  4) knowledge_points ≥5；每条含 term/type/statement/aliases/source_id/locator
  5) 所有 locator 形如 "section <title>, paragraph <pid>"，且 <pid> 在输入中真实存在
  6) 每条笔记的 locator 必须能反查到 sources 中的同段证据（来源保留）
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

STATUS = ("success", "partial", "undetermined", "refused")
TOP = ("case_id", "task_id", "status", "results", "sources", "uncertainty", "changes", "artifacts", "metadata")
RES_KEYS = ("paper_card", "section_notes", "knowledge_points", "comparison_fields")
CARD_KEYS = ("research_question", "data", "methods", "findings", "limitations")
LOC = re.compile(r"^section .+, paragraph .+$")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def para_ids(case):
    ids = set()
    for s in case.get("sections") or []:
        for p in s.get("paragraphs") or []:
            if isinstance(p, dict):
                ids.add(str(p.get("id") or p.get("paragraph_id") or ""))
            else:
                ids.add("")
    if not ids:
        for p in (case.get("document") or {}).get("paragraphs") or case.get("paragraphs") or []:
            ids.add(str(p.get("id") or p.get("paragraph_id") or "") if isinstance(p, dict) else "")
    return {i for i in ids if i}


def pid_of(loc):
    m = re.search(r"paragraph ([^,]+)$", loc or "")
    return m.group(1).strip() if m else ""


def validate(result, case):
    errs = []
    for k in TOP:
        if k not in result:
            errs.append("缺少顶层字段 " + k)
    if result.get("status") not in STATUS:
        errs.append("status 非法：" + str(result.get("status")))
    if not result.get("case_id"):
        errs.append("case_id 为空（必须原样来自 case.json）")
    res = result.get("results") or {}
    extra = [k for k in res if k not in RES_KEYS]
    if extra:
        errs.append("results 出现契约外字段：" + str(extra))
    for k in RES_KEYS:
        if k not in res:
            errs.append("results 缺少 " + k)
    card = res.get("paper_card") or {}
    if set(card) != set(CARD_KEYS):
        errs.append("paper_card 字段应为 %s，实际 %s" % (list(CARD_KEYS), sorted(card)))
    for k in CARD_KEYS:
        if result.get("status") == "success" and not card.get(k):
            errs.append("status=success 但 paper_card.%s 为空" % k)

    notes = res.get("section_notes") or []
    if len(notes) < 2:
        errs.append("section_notes 少于 2 条（实际 %d）" % len(notes))
    sec_titles = [str(s.get("title") or "") for s in case.get("sections") or []]
    for i, n in enumerate(notes):
        for k in ("section", "purpose", "method", "result", "conclusion", "source_id", "locator"):
            if k not in n:
                errs.append("section_notes[%d] 缺 %s" % (i, k))
        if not n.get("section") or not n.get("source_id"):
            errs.append("section_notes[%d] section/source_id 为空" % i)
        if not LOC.match(n.get("locator") or ""):
            errs.append("section_notes[%d] locator 不合规：%s" % (i, n.get("locator")))
        if not any(n.get(k) for k in ("purpose", "method", "result", "conclusion")):
            errs.append("section_notes[%d] 四个内容字段全空，等于没写笔记" % i)
    if sec_titles and [n.get("section") for n in notes][:len(sec_titles)] != sec_titles:
        errs.append("section_notes 顺序与输入章节不一致（必须照论文自身章节顺序）")

    kps = res.get("knowledge_points") or []
    if len(kps) < 5:
        errs.append("knowledge_points 少于 5 个（实际 %d）" % len(kps))
    terms = [k.get("term") for k in kps]
    if len(set(t.lower() for t in terms if t)) != len([t for t in terms if t]):
        errs.append("knowledge_points 存在重复术语")
    for i, k in enumerate(kps):
        for f in ("term", "type", "statement", "aliases", "source_id", "locator"):
            if f not in k:
                errs.append("knowledge_points[%d] 缺 %s" % (i, f))
        if not k.get("term") or not k.get("statement"):
            errs.append("knowledge_points[%d] term/statement 为空" % i)
        if not LOC.match(k.get("locator") or ""):
            errs.append("knowledge_points[%d] locator 不合规" % i)
    if not isinstance(res.get("comparison_fields"), list) or len(res.get("comparison_fields") or []) < 3:
        errs.append("comparison_fields 必须是 ≥3 项的 list")

    ids = para_ids(case)
    if ids:
        for i, n in enumerate(notes):
            if pid_of(n.get("locator")) not in ids:
                errs.append("section_notes[%d] locator 指向不存在的段落" % i)
        for i, k in enumerate(kps):
            if pid_of(k.get("locator")) not in ids:
                errs.append("knowledge_points[%d] locator 指向不存在的段落" % i)

    src_loc = {(s.get("source_id"), pid_of(s.get("locator"))) for s in result.get("sources") or []}
    for i, n in enumerate(notes):
        if src_loc and (n.get("source_id"), pid_of(n.get("locator"))) not in src_loc:
            errs.append("section_notes[%d] 的定位在 sources 中找不到对应证据" % i)
    for i, s in enumerate(result.get("sources") or []):
        for k in ("source_id", "locator", "quote"):
            if not s.get(k):
                errs.append("sources[%d] 缺 %s" % (i, k))
    for i, u in enumerate(result.get("uncertainty") or []):
        for k in ("item", "reason", "action_required"):
            if not u.get(k):
                errs.append("uncertainty[%d] 缺 %s" % (i, k))
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="结构化笔记结果序列化与官方契约校验")
    ap.add_argument("--input", default=None, help="/input/case.json")
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--skill-name", default="literature-structured-notes")
    ap.add_argument("--skill-version", default="1.0.0")
    a = ap.parse_args(argv)

    draft = load(a.draft)
    case = load(a.input) if a.input and Path(a.input).exists() else {}
    case_id = str(draft.get("case_id") or case.get("case_id") or case.get("id") or "")
    task_id = a.task_id or case.get("task_id") or case.get("challenge_id") or "product-arena-06-6d8cf72b"
    res = draft.get("results") or {}

    result = {
        "case_id": case_id,
        "task_id": str(task_id),
        "status": draft.get("status") or "partial",
        "results": {k: res.get(k) for k in RES_KEYS},
        "sources": draft.get("sources") or [],
        "uncertainty": draft.get("uncertainty") or [],
        "changes": draft.get("changes") or [],
        "artifacts": draft.get("artifacts") or [],
        "metadata": {"skill_name": a.skill_name, "skill_version": a.skill_version, "model": "",
                     "runtime": "python " + sys.version.split()[0],
                     "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")},
    }
    errs = validate(result, case)
    if errs:
        print("INVALID: " + "; ".join(errs), file=sys.stderr)
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote " + str(out))
    print("status=%s sections=%d knowledge_points=%d sources=%d"
          % (result["status"], len(result["results"]["section_notes"]),
             len(result["results"]["knowledge_points"]), len(result["sources"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
