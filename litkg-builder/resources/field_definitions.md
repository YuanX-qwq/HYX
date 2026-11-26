# result.json 字段定义（literature-knowledge-graph）

`resources/output_contract.json` 只是官方平铺示例，本文件说明各字段语义与硬约束。
`scripts/serialize_result.py` 按本文件逐项校验，任何一项不合规都会报错并拒绝写出。

## 顶层
- `case_id`：取自 `/input/case.json` 的案例标识，不得自造。
- `task_id`：取自 `/input/case.json`（或题面 slug），用于回链挑战。
- `status`：`success`（语料全部处理且无未决项）/ `partial`（主体完成但有缺证或冲突未裁）/ `undetermined`（关键输入不足、只能给出候选）/ `refused`（输入越界或不合法）。
- `sources`：证据池，每项 `source_id`（篇 id）、`locator`（如 `paragraph P1-p003`）、`locator_type`（`paragraph`/`section`/`table`/`figure`）、`quote`（逐字原文）、`note`。
- `uncertainty`：每项 `item`、`reason`、`action_required`，只登记真实缺证或未裁项。
- `changes`：每项 `step`、`action`、`note`，记录实际做过的处理动作。
- `artifacts`：产物描述，每项 `artifact_id`、`path`（相对 `/app/output`）、`format`、`type`、`description`。
- `metadata`：`skill_name` 固定 `literature-knowledge-graph`，另含 `skill_version`、`model`、`runtime`、`generated_at`。

## results（只允许这五个键）
- `nodes`：实体节点。`id`、`label`、`type`（取自 `vocab/entity_types.json`）、`canonical`（规范名）、`source_ids`、`evidence[]`（`source_id`/`paragraph_id`/`quote`）。
- `edges`：关系边。`id`、`from`、`to`、`type`（取自 `vocab/relation_types.json`）、`direction`、`conditions[]`、`attribution`、`strength`、`evidence[]`。
- `alignments`：跨篇对齐判定。`canonical`、`decision`（`merged_across_papers`/`kept_separate`/`conflict_flagged`）、`basis`（判定依据）、`members[]`（被比较的节点 id 与篇 id）。
- `queries`：查询问答。每项恰为 `query`、`results`、`evidence` 三键；`results` 为空表示该查询确实无命中；有命中时 `evidence` 不得为空，且每条证据必须是 `source_id` + `paragraph <pid>` + 逐字 `quote`。
- `conflicts`：冲突登记。`type`（如 `metric_value_divergence`）、`subject`、`claims[]`（各自值、篇 id、段落 id）、`resolution`（`kept_separate`/`kept_both`/`flagged`）。

## 硬约束
- 所有 `quote` 必须能在对应段落中逐字命中，校验脚本会回查语料。
- 节点/边 `id` 由内容确定性生成（同输入重跑 id 稳定）。
- 不合并实例级实体（材料、样品、数据集、模型、指标、条件）；仅通用类型术语可跨篇合并。
- 比较类关系缺条件时必须出现在 `conflicts` 或 `uncertainty` 中，不得静默省略。
