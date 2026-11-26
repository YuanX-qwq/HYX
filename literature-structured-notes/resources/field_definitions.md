# result.json 字段定义（literature-structured-notes）

`resources/output_contract.json` 是官方平铺示例；本文件说明语义与硬约束，由 `scripts/serialize_result.py` 校验。

## 顶层
- `case_id`：原样取 `/input/case.json`，不得改写。
- `task_id`：题面 slug（阅读10 为 `product-arena-06-6d8cf72b`）。
- `status`：`success`（卡片五字段齐备且有笔记）/ `partial`（卡片缺项或证据受限）/ `undetermined`（材料不足）/ `refused`（不合规）。
- `sources[]`：`source_id`、`locator`（`section <title>, paragraph <pid>`）、`locator_type`、`quote`（逐字）、`note`。
- `uncertainty[]`：`item` / `reason` / `action_required`；原文未报告、图表不可读、需人工判定的都登记。
- `changes[]`：`step` / `action` / `note`，真实处理记录。
- `artifacts[]`：导出文件对象（`artifact_id`/`path`/`format`/`type`/`description`）。
- `metadata`：`skill_name` 固定 `literature-structured-notes`，另含版本、模型、运行时、生成时间。

## results（只允许四个键）
- `paper_card`：恰含 `research_question`、`data`、`methods`、`findings`、`limitations`。内容是原文句子的摘录，不超过 220 字符；缺项留空并降级 `partial`。
- `section_notes[]`：每个输入章节一条，顺序必须与论文自身章节一致；字段 `section`、`purpose`、`method`、`result`、`conclusion`、`source_id`、`locator`。四个内容字段可以部分为空（该章节不涉及），但不能全空。
- `knowledge_points[]`：可检索知识点，≥5 条；字段 `term`、`type`（`metric`/`method`/`concept`）、`statement`（原句摘录）、`aliases`（可空）、`source_id`、`locator`。`term` 不得重复（大小写不敏感）。
- `comparison_fields[]`：跨论文对比用的统一字段名，至少 3 项，默认 `research_question`/`methods`/`findings`/`limitations`。

## 硬约束
- 所有 `locator` 必须是 `section <title>, paragraph <pid>` 形式，且 `<pid>` 在输入中真实存在。
- 每条章节笔记与知识点的定位，必须能在 `sources` 中找到同 `source_id` + 同 `pid` 的逐字证据。
- 小数（如 `0.5 wt%`）不得被切成两句；中英句末标点都要切句。
- 不合并章节、不改章节顺序；不补写原文没有的数值与条件。
