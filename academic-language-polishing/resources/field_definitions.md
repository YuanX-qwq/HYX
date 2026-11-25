# result.json 字段定义（academic-language-polishing）

`resources/output_contract.json` 给出可直接照抄的示例实例（标注 EXAMPLE ONLY）；
本文件给出字段含义与硬约束。二者等价，示例不是答案。

## 顶层

| 字段 | 约束 |
|---|---|
| `case_id` | 原样取自 `/input/case.json`，不得改写或编造 |
| `task_id` | 本题标识或 case.json 的 task_id |
| `status` | `success \| partial \| undetermined \| refused` |
| `results` | 见下 |
| `sources` | 每条缺 `source_id/locator/quote` 即无效 |
| `uncertainty` | `item / reason / action_required` |
| `changes` | `step / action / note` |
| `artifacts` | 产物路径数组 |
| `metadata` | `skill_name / skill_version / model / runtime / generated_at` |

## results

- `revised_text`：润色后的完整文本，逐段处理，不删段不并段。
- `revisions`：`span`（定位）、`original`（必须逐字出现在原文）、`revised`（必须逐字出现在改文）、
  `type`（`grammar|syntax|collocation|punctuation|terminology|register|clarity|redundancy|cohesion|bilingual|other`）、
  `reason`、`preserves_meaning`（必须 `true`，否则该条不得提交）。
- `glossary`：`concept / en_form / zh_form / note`（缩写首现、大小写、连字符约定）。
- `register_notes`：目标文体、受众、语域决策。
- `unresolved`：需作者确认的条目（与 `uncertainty` 呼应，不重复记同一项）。

## 硬约束（serialize_result.py 会拒绝）

1. 任一条 `revisions.original` 在原文找不到 → 拒绝。
2. 任一条 `revisions.revised` 在 `revised_text` 找不到 → 拒绝。
3. `preserves_meaning=false` 仍提交 → 拒绝。
4. `status=success` 但 `unresolved` 非空 → 拒绝。
5. `case_id` 与 `/input/case.json` 不一致 → 拒绝。
