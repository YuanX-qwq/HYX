# result.json 字段定义（nanopublication-extraction）

`resources/output_contract.json` 是官方平铺示例；本文件说明语义与硬约束，由
`scripts/serialize_result.py` 逐项校验，不合规直接拒绝写出。

## 顶层
- `case_id`：原样取 `/input/case.json` 的案例标识，不得改写。
- `task_id`：题面 slug（阅读14 为 `product-arena-09-0e8befd4`）。
- `status`：`success` / `partial`（存在 fail 级质检或未修项）/ `failed`（无材料或无法解析）/ `refused`（不合规）。
- `sources[]`：`source_id`、`locator`（`page N, paragraph pXbY, chars a-b`）、`locator_type`、`quote`（逐字）、`note`。
- `uncertainty[]`：`item` / `reason` / `action_required`；原文未报告、无法定位、需人工判定的都登记于此。
- `changes[]`：`step` / `action` / `note`，来自 `change_log` 的真实处理记录。
- `artifacts[]`：导出文件对象。
- `metadata`：`skill_name` 固定 `nanopublication-extraction`，另含版本、模型、运行时、生成时间。

## results（只允许两个键）
- `nanopubs[]`：一条断言一个对象
  - `assertion`：单一断言句，不得多句拼接，不得整段照抄；
  - `subject` / `predicate` / `object`：主体、受控关系（`vocab/predicates.json`）、客体（数值带 `= value unit`）；
  - `conditions`：温度/pH/剂量/时长等限定，`key=value; …`；否定断言写 `polarity=negative`；
  - `evidence`：`source_id`、`locator`、`quote`（逐字、最小充分，含主体与客体）、`evidence_type`（`direct`/`supporting`）；
  - `source_metadata`：`authors`、`year`、`version`、`doi_or_id`（论文、作者、年份、版本、标识）；
  - `confidence`：`high`/`medium`/`low`；
  - `status`：`checked`（质检 pass）/ `flagged`（warn）/ `rejected`（fail）/ `unverified`。
- `quality_flags[]`：`{assertion_id, code, severity, detail}`，与 Q001–Q013 质检结果一一对应；无问题时为空数组。

## 硬约束
- 断言数 ≥3（正式案例通常 ≥10），每条必须能回链到原文片段。
- `quote` 必须逐字可定位（去空白匹配也算命中），否则质检 Q003 fail。
- 断言中出现的长数字必须出现在证据里（Q008 warn），主体必须出现在证据段落（Q009 warn）。
- 关系必须落在受控词表内（Q005 fail）；`other` 需给 `free_text`。
- 不得把多篇结论合并成一个松散字段，也不得把一条结论拆成缺主语的碎片。
