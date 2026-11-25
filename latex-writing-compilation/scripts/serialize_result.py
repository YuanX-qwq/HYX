#!/usr/bin/env python3
"""把草稿组装成符合 output_contract 的 result.json，并做语义校验（标准库）。

用法：
  python3 scripts/serialize_result.py --input /input/case.json \
      --draft /app/work/results_draft.json --out /app/output/result.json \
      --skill-name latex-writing-compilation
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

TOP = ["case_id", "task_id", "status", "results", "sources", "uncertainty", "changes", "artifacts", "metadata"]
RES_KEYS = ["latex_sources", "build", "artifacts", "template_compliance", "reproduction_notes"]
BUILD_KEYS = ["engine", "passes", "status", "logs", "errors"]
ERR_KEYS = ["file", "line", "cause", "fix"]
REPRO_KEYS = ["distro", "package_versions", "font_versions", "commands"]
STATUS = {"success", "partial", "undetermined", "refused"}


def load(p, default=None):
    p = Path(p)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def validate(case_id, res):
    bad = []
    for k in RES_KEYS:
        if k not in res:
            bad.append("results.%s 缺失" % k)
    b = res.get("build", {})
    for k in BUILD_KEYS:
        if k not in b:
            bad.append("results.build.%s 缺失" % k)
    for i, e in enumerate(b.get("errors", [])):
        for k in ERR_KEYS:
            if k not in e:
                bad.append("results.build.errors[%d].%s 缺失" % (i, k))
    for k in REPRO_KEYS:
        if k not in res.get("reproduction_notes", {}):
            bad.append("results.reproduction_notes.%s 缺失" % k)
    tc = res.get("template_compliance", {})
    if not isinstance(tc.get("layout_ok"), bool):
        bad.append("template_compliance.layout_ok 必须是布尔值")
    if not isinstance(tc.get("required_fields"), list):
        bad.append("template_compliance.required_fields 必须是列表")
    for i, s in enumerate(res.get("latex_sources", [])):
        if not s.get("path"):
            bad.append("latex_sources[%d].path 为空" % i)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skill-name", default="latex-writing-compilation")
    ap.add_argument("--skill-version", default="1.0.0")
    a = ap.parse_args(argv)

    case = load(a.input, {}) or {}
    draft = load(a.draft, {})
    if not draft:
        sys.exit("draft not found: %s" % a.draft)

    case_id = case.get("case_id") or draft.get("case_id")
    if not case_id:
        sys.exit("case_id missing: case.json 与 draft 都没有")
    if draft.get("case_id") and draft["case_id"] != case.get("case_id", draft["case_id"]):
        sys.exit("case_id 被改写：draft=%s case=%s" % (draft["case_id"], case.get("case_id")))

    merged = dict(draft)
    merged["case_id"] = case_id
    merged.setdefault("task_id", case.get("task_id", ""))
    merged.setdefault("status", "partial")
    merged.setdefault("sources", [])
    merged.setdefault("uncertainty", [])
    merged.setdefault("changes", [])
    merged.setdefault("artifacts", [])

    res = merged.get("results", {})
    problems = validate(case_id, res)
    if problems:
        sys.exit("contract violation: " + "; ".join(problems))

    status = merged["status"]
    if status not in STATUS:
        sys.exit("status 非法：%s（允许 %s）" % (status, sorted(STATUS)))

    b = res["build"]
    notes = res["reproduction_notes"]
    if status == "success":
        if b.get("status") != "success":
            sys.exit("status=success 但 build.status=%s：编译未通过不得报 success" % b.get("status"))
        if b.get("errors"):
            sys.exit("status=success 但 build.errors 非空")
        if not res["template_compliance"].get("layout_ok"):
            sys.exit("status=success 但 layout_ok=false")
        for k in ("commands", "distro"):
            if not str(notes.get(k, "")).strip():
                sys.exit("status=success 但 reproduction_notes.%s 为空：构建不可复现" % k)
        if not str(notes.get("engine") or b.get("engine") or "").strip():
            sys.exit("status=success 但 engine 为空：构建不可复现")
        try:
            if int(str(b.get("passes", "0"))) < 1:
                sys.exit("status=success 但 passes<1")
        except ValueError:
            sys.exit("build.passes 非整数：%r" % b.get("passes"))

    for i, s in enumerate(merged["sources"]):
        if not s.get("source_id") or not s.get("locator") or not s.get("quote"):
            sys.exit("sources[%d] 缺 source_id/locator/quote：证据必须可回链" % i)

    tz = timezone(timedelta(hours=8))
    meta = merged.get("metadata", {}) or {}
    meta.update({
        "skill_name": a.skill_name,
        "skill_version": a.skill_version,
        "generated_at": datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    })
    meta.setdefault("model", "")
    meta.setdefault("runtime", "")
    merged["metadata"] = meta

    order = {k: merged.get(k) for k in TOP}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(order, ensure_ascii=False, indent=2), encoding="utf-8")
    errs = b.get("errors") or []
    print("wrote %s status=%s build=%s errors=%d sources=%d uncertainty=%d"
          % (out, order["status"], b.get("status"), len(errs),
             len(order["sources"]), len(order["uncertainty"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
