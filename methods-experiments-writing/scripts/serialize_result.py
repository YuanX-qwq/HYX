#!/usr/bin/env python3
"""把 results 草稿序列化为符合 output_contract 的 result.json，并做必填/枚举/一致性校验。

用法：
  python3 scripts/serialize_result.py --input /input/case.json --draft /app/work/results_draft.json \
      --out /app/output/result.json --skill-name methods-experiments-writing
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

TOP = ["case_id", "task_id", "status", "results", "sources", "uncertainty",
       "changes", "artifacts", "metadata"]
STATUS = {"success", "partial", "undetermined", "refused"}
LIST_KEYS = {
    "method_steps": ["order", "action", "inputs", "outputs", "condition"],
    "parameters": ["name", "value", "unit", "target", "source"],
    "baselines": ["name", "version", "budget_matched", "source"],
    "limitations": ["limitation", "failure_scenario", "requires_confirmation"],
}
DICT_KEYS = {
    "experimental_setup": ["hardware", "software_versions", "seed", "repetitions", "train_val_test"],
    "dataset": ["name", "version", "scale", "preprocess", "split", "purpose"],
    "reproducibility": ["code_version", "environment", "seed", "commands", "data_access"],
}
RESULT_KEYS = list(LIST_KEYS) + list(DICT_KEYS)


def fail(msg):
    print("FAIL: " + msg, file=sys.stderr)
    raise SystemExit(1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="")
    ap.add_argument("--draft", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skill-name", default="methods-experiments-writing")
    ap.add_argument("--version", default="1.0.0")
    a = ap.parse_args(argv)

    draft = json.loads(Path(a.draft).read_text(encoding="utf-8"))
    case = {}
    if a.input and Path(a.input).exists():
        try:
            case = json.loads(Path(a.input).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            case = {}

    results = draft.get("results") or {k: draft[k] for k in RESULT_KEYS if k in draft}
    res = {k: draft.get(k) for k in TOP}
    res["case_id"] = draft.get("case_id") or case.get("case_id", "")
    res["task_id"] = draft.get("task_id") or case.get("task_id", "")
    res["status"] = draft.get("status") or "partial"
    res["sources"] = draft.get("sources") or []
    res["uncertainty"] = draft.get("uncertainty") or []
    res["changes"] = draft.get("changes") or []
    res["artifacts"] = draft.get("artifacts") or []
    res["results"] = results

    if res["status"] not in STATUS:
        fail("status 非法: %r（允许 %s）" % (res["status"], sorted(STATUS)))
    if not res["case_id"]:
        fail("case_id 为空；必须原样写入 case.json 的 case_id")

    for key, fields in LIST_KEYS.items():
        val = results.get(key)
        if not isinstance(val, list):
            fail("results.%s 必须是数组" % key)
        for i, item in enumerate(val):
            for f in fields:
                if f not in item:
                    fail("results.%s[%d] 缺少字段 %s" % (key, i, f))
    for key, fields in DICT_KEYS.items():
        val = results.get(key)
        if not isinstance(val, dict):
            fail("results.%s 必须是对象" % key)
        missing = [f for f in fields if f not in val]
        if missing:
            fail("results.%s 缺少字段 %s" % (key, missing))

    # 语义校验：来源、步骤顺序、数值非空
    for i, p in enumerate(results["parameters"]):
        if not str(p.get("value", "")).strip():
            fail("results.parameters[%d]（%s）取值为空" % (i, p.get("name")))
        if not str(p.get("source", "")).strip():
            fail("results.parameters[%d]（%s）缺来源绑定" % (i, p.get("name")))
    orders = [s["order"] for s in results["method_steps"]]
    if orders != sorted(orders):
        fail("method_steps 顺序不是升序：%s" % orders)
    if len(results["method_steps"]) < 2:
        fail("method_steps 少于 2 步，无法构成可执行流程")
    for i, b in enumerate(results["baselines"]):
        if not str(b.get("source", "")).strip():
            fail("results.baselines[%d]（%s）缺来源" % (i, b.get("name")))

    for i, s in enumerate(res["sources"]):
        for f in ("source_id", "locator", "locator_type", "quote"):
            if not str(s.get(f) or "").strip():
                fail("sources[%d] 缺少 %s" % (i, f))
    for i, u in enumerate(res["uncertainty"]):
        for f in ("item", "reason", "action_required"):
            if not str(u.get(f) or "").strip():
                fail("uncertainty[%d] 缺少 %s" % (i, f))

    need_confirm = [l["limitation"] for l in results["limitations"] if l.get("requires_confirmation")]
    if res["status"] == "success" and need_confirm:
        fail("status=success 但仍有 %d 条需作者确认的限制：%s" % (len(need_confirm), need_confirm[:2]))

    meta = dict(draft.get("metadata") or {})
    meta.setdefault("skill_name", a.skill_name)
    meta.setdefault("skill_version", a.version)
    meta.setdefault("generated_at", dt.datetime.now().astimezone().isoformat(timespec="seconds"))
    meta.setdefault("model", "")
    meta.setdefault("runtime", "")
    res["metadata"] = meta

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote %s status=%s steps=%d params=%d baselines=%d limitations=%d sources=%d uncertainty=%d"
          % (a.out, res["status"], len(results["method_steps"]), len(results["parameters"]),
             len(results["baselines"]), len(results["limitations"]),
             len(res["sources"]), len(res["uncertainty"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
