---
name: methods-experiments-writing
description: "Write reproducible methods and experiments sections by extracting elements from real materials (config, run log, step records, draft): ordered executable steps with inputs/outputs/conditions, train-val-test setup with hardware/software/seed/repetitions, a parameter table with name-value-unit-target-source, dataset version and split, baselines with matched-budget notes, a reproducibility checklist, and limitations tied to concrete failure scenarios. Every number in the draft must be traceable to config or log; unsourced or conflicting values are flagged rather than smoothed over. Use for methods/experiments writing, setup description, parameter tables and reproducibility checks."
---

# 写作09｜方法与实验章节写作

## 用途与触发条件

对组织方给定的真实材料（配置、运行日志、步骤记录、稿件草稿），把散落要素整理成**可执行、可核对**的方法与实验章节。评测时 Skill 装到 `/skills/weekly-skill`，输入 `/input/case.json` + `task.md`，过程产物在 `/app/work`，最终 `/app/output`。

**适用**：方法步骤序列化；实验设置（硬件/软件/种子/重复/T-V-T 分离）；参数表与来源绑定；数据集版本与划分；对照实验同预算说明；可复现清单与具体失效场景限制。
**不适用**：凭常识补数值；把配置里没有的参数写进表格；用"按常规设置"掩盖缺失；预制答案。

## 核心关注点

- **写得全**：六要素（步骤、设置、参数、数据、对照、复现/限制）逐项落地，不靠"能读通的主干"。
- **写得准**：正文每个数值都要能在配置或日志里找到；找不到就标 `unsourced`，与配置矛盾就标 `conflict`。
- **做得着**：每步有输入/操作/输出/判断，读者按章节能复做；版本、环境、种子、命令给全。
- **说得住**：缺口显式写进 `uncertainty`，限制指向具体失效场景而不是套话。

## 执行流程

1. **读取输入**：读 `case.json` 与 `task.md`，确认材料路径与目标体裁；`case_id` 原样保留。
2. **解析材料**：`mew.py parse` 解析 config（yaml/json，含嵌套）与 run log，抽出参数、环境、数据集、基线、步骤。
3. **参数表与对齐**：`mew.py params` 生成参数表（名称/取值/单位/作用对象/来源），并把草稿里的数值逐一对齐——命中记 `sourced`，同键不同值记 `conflict`，无线索但带度量线索的词记 `unsourced`。
4. **六要素检查**：`mew.py check` 给出 steps/setup/params/dataset/baselines 五项状态与明细。
5. **成稿**：`mew.py assemble` 生成可编辑 Markdown 章节（步骤、设置、参数表、数据集、对照、复现、限制）。
6. **序列化**：`python3 scripts/serialize_result.py --input /input/case.json --draft /app/work/results_draft.json --out /app/output/result.json`。
7. **自检**：`python3 tests/selftest.py`（34 项），并对照 `templates/methods_checklist.md` 逐条确认；有 `conflict`/`unsourced` 时 `status` 必须是 `partial`。

```bash
python3 scripts/mew.py run --case /input/case.json \
  --config /app/work/config.yaml --log /app/work/run.log \
  --steps /app/work/steps.md --draft /app/work/draft.md \
  --out /app/work/results_draft.json          # 同时写出 section.md（可编辑章节）
```

## 输出契约（result.json）

顶层：`case_id, task_id, status, results, sources, uncertainty, changes, artifacts, metadata`（见 `resources/output_contract.json`）。

`results` 结构：

```json
{
  "method_steps": [{"order": 1, "action": "…", "inputs": "…", "outputs": "…", "condition": "…"}],
  "experimental_setup": {"hardware": "…", "software_versions": "…", "seed": "…", "repetitions": "…", "train_val_test": "…"},
  "parameters": [{"name": "train.lr", "value": 0.001, "unit": "—", "target": "训练", "source": "config.yaml:6"}],
  "dataset": {"name": "CIFAR-10", "version": "", "scale": "50000", "preprocess": "…", "split": "train 0.9 / val 0.1", "purpose": "…"},
  "baselines": [{"name": "vanilla resnet18", "version": "", "budget_matched": "未说明", "source": "config.yaml:14"}],
  "reproducibility": {"code_version": "…", "environment": "…", "seed": "…", "commands": "…", "data_access": "…"},
  "limitations": [{"limitation": "…", "failure_scenario": "…", "requires_confirmation": true}]
}
```

`status`：`success | partial | undetermined | refused`。存在需作者确认的限制时不得填 `success`（序列化器会拒绝）。

## 限制与失败处理

| 情况 | 处置 |
|---|---|
| 配置/日志缺失 | 对应用字段留空 + `uncertainty` 写明缺什么，不按"常规设置"补 |
| 正文数值与配置冲突 | 记 `conflict` 并写 `limitations`（失效场景：按正文复现结果不同），交作者确认 |
| 正文出现材料里没有的数值 | 记 `unsourced`，不写进参数表、不静默保留 |
| 步骤记录不可解析 | `uncertainty` 报 `steps_missing`，不凭草稿编步骤 |
| 数据集版本缺失 | `dataset.version` 留空 + 限制条目，标明换版本后结果不可比 |
| 基线是否同预算未说明 | `budget_matched="未说明"`，限制条目写明"不同预算下对比不成立" |

体积约束：≤50 个 UTF-8 文本文件、单文件 ≤500KB、总量 ≤2MB、无符号链接；脚本纯标准库。

## 资源

- `scripts/mew.py`：解析/参数/步骤/检查/成稿/一键流程。
- `scripts/serialize_result.py`：九字段契约序列化与语义校验。
- `resources/output_contract.json`、`resources/conventions.md`：字段定义与通用规范。
- `templates/methods_checklist.md`：六要素自查表与追问清单。
- `examples/`：合成材料（config/run.log/steps.md/draft.md）与示例结果，均标注为示例。
- `tests/selftest.py`：34 项断言。
