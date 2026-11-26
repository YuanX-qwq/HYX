#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py — 结构化笔记 Skill 的 fixture 自测（标准库）。

覆盖：章节顺序、卡片五字段、小数不被切成两句、知识点去重、来源回链、
确定性、以及契约校验器对真实坏输入的拦截（章节乱序、定位不存在、success 但卡片空）。
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import notes  # noqa: E402
import serialize_result as sr  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("  " + str(detail) if detail and not cond else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="notes-selftest-")
    case = notes.load(os.path.join(ROOT, "examples", "case.example.json"))
    corpus = notes.parse_case(case)
    draft = notes.build_notes(corpus, case["case_id"])
    res = draft["results"]

    titles = [s["title"] for s in case["sections"]]
    check("section_count", len(corpus["sections"]) == len(titles) == 6, str(len(corpus["sections"])))
    check("section_order_preserved", [n["section"] for n in res["section_notes"]] == titles,
          str([n["section"] for n in res["section_notes"]]))
    check("paper_card_keys", set(res["paper_card"]) == set(sr.CARD_KEYS), str(sorted(res["paper_card"])))
    check("paper_card_complete", all(res["paper_card"][k] for k in sr.CARD_KEYS),
          str([k for k in sr.CARD_KEYS if not res["paper_card"][k]]))
    check("research_question_is_question",
          "whether" in res["paper_card"]["research_question"].lower(),
          res["paper_card"]["research_question"][:60])
    check("methods_keep_decimal_loading",
          "0.5" in res["paper_card"]["methods"] and "2.0 wt%" in res["paper_card"]["methods"],
          res["paper_card"]["methods"][:80])
    check("findings_carry_metric",
          "92%" in res["paper_card"]["findings"], res["paper_card"]["findings"][:80])
    check("limitations_from_limitation_section",
          "limited" in res["paper_card"]["limitations"].lower(), res["paper_card"]["limitations"][:80])

    kps = res["knowledge_points"]
    check("knowledge_points_min", len(kps) >= 5, str(len(kps)))
    check("knowledge_points_unique_terms",
          len({k["term"].lower() for k in kps}) == len(kps), str(len(kps)))
    check("knowledge_points_typed", all(k["type"] in ("metric", "method", "concept") for k in kps),
          str({k["type"] for k in kps}))
    check("every_note_locator_canonical",
          all(sr.LOC.match(n["locator"]) for n in res["section_notes"] + kps),
          "locator 格式 section X, paragraph Y")

    src_loc = {(s["source_id"], sr.pid_of(s["locator"])) for s in draft["sources"]}
    check("every_note_backlinked",
          all((n["source_id"], sr.pid_of(n["locator"])) in src_loc
              for n in res["section_notes"] + kps))
    check("uncertainty_objects",
          all({"item", "reason", "action_required"} <= set(u) for u in draft["uncertainty"]),
          str(draft["uncertainty"][:1]))

    # 序列化器接受好结果
    out = os.path.join(tmp, "result.json")
    with open(os.path.join(tmp, "draft.json"), "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False)
    rc = sr.main(["--input", os.path.join(ROOT, "examples", "case.example.json"),
                  "--draft", os.path.join(tmp, "draft.json"), "--out", out,
                  "--task-id", "product-arena-06-6d8cf72b"])
    check("serializer_exit_0", rc == 0, str(rc))
    good = json.loads(open(out, encoding="utf-8").read())
    check("serializer_results_four_keys", set(good["results"]) == set(sr.RES_KEYS), str(sorted(good["results"])))
    check("serializer_skill_name", good["metadata"]["skill_name"] == "literature-structured-notes")

    # 契约必须拦住的坏输入
    bad = json.loads(json.dumps(good))
    bad["results"]["section_notes"] = list(reversed(bad["results"]["section_notes"]))
    check("reject_unsorted_sections", any("顺序" in e for e in sr.validate(bad, case)))
    bad2 = json.loads(json.dumps(good))
    bad2["results"]["knowledge_points"][0]["locator"] = "section X, paragraph p999"
    check("reject_unknown_paragraph", any("不存在的段落" in e for e in sr.validate(bad2, case)))
    bad3 = json.loads(json.dumps(good))
    bad3["results"]["paper_card"]["findings"] = ""
    check("reject_empty_card_on_success", any("paper_card.findings" in e for e in sr.validate(bad3, case)))
    bad4 = json.loads(json.dumps(good))
    bad4["results"]["extra"] = 1
    check("reject_extra_results_key", any("契约外字段" in e for e in sr.validate(bad4, case)))
    bad5 = json.loads(json.dumps(good))
    bad5["results"]["section_notes"][0]["purpose"] = ""
    bad5["results"]["section_notes"][0]["method"] = ""
    bad5["results"]["section_notes"][0]["result"] = ""
    bad5["results"]["section_notes"][0]["conclusion"] = ""
    check("reject_empty_section_note", any("四个内容字段全空" in e for e in sr.validate(bad5, case)))

    # 确定性
    d2 = notes.build_notes(notes.parse_case(case), case["case_id"])
    check("deterministic", json.dumps(d2, sort_keys=True, ensure_ascii=False)
          == json.dumps(draft, sort_keys=True, ensure_ascii=False))

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d/%d assertions passed" % (len(PASS), len(PASS) + len(FAIL)))
    if FAIL:
        print("failed:", FAIL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
