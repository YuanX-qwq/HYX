---
name: academic-language-polishing
description: "Polish academic text while preserving meaning: fix grammar/syntax/collocation/punctuation, keep terminology consistent throughout, match the target register (journal paper, thesis, grant, review reply, abstract), and apply minimal edits that preserve qualifier strength, causal vs correlative distinction, negation scope, conditionals and quantifiers. Every revision records original, revised, type and rationale, and a mechanical checker verifies numbers/units/citations/cross-references/negation/hedges survived. Use for 学术语言润色 and bilingual academic expression. Not for rewriting conclusions or strengthening claims."
---

# 写作02｜学术语言润色

## 用途与触发条件

在 Bohrium Playground（Harbor 评测）环境中，对组织方给定的稿件完成**学术语言润色**：改语言层，不改结论层。
Skill 被安装到 `/skills/weekly-skill`，输入 `/input/case.json` 与 `task.md`，过程产物 `/app/work`，最终 `/app/output`。

**适用**：语法与句法修正；术语与全篇一致性；学术语气与语域；语义保持与最小编辑；中英文表达质量。
**不适用**：改结论、补数据、加引用；纯内容问答（不擅自改写）；预制答案。

## 核心关注点

- **改得对**：主谓一致、时态语态、冠词介词、单复数、悬垂修饰、标点与长句切分，消除硬错误。
- **说得像**：符合目标文体（期刊/学位论文/基金/审稿回复/摘要），去口语化、宣传化、绝对化。
- **没改坏**：数字、单位、引用编号、图表/公式指向原样；限定强度不跨级、否定范围不变、条件与量词守恒。
- **讲得清**：每处修改有原文、改文、类型、理由，第三方能判断该不该改。

## 执行流程

1. **读取输入**：读 `/input/case.json` 与 `task.md`，确认目标文体、章节范围、术语约束；`case_id` 原样保留。
2. **建术语表**：先抽出概念及其中英写法、缩写首现形式、大小写与连字符约定，写入 `glossary`。
3. **逐段最小编辑**：一句一改，只解决一类问题；不整段重写。按 `templates/registers.md` 的文体规则与限定强度对照执行。
4. **记录修改**：每条 `{span, original, revised, type, reason, preserves_meaning}`；`original` 必须逐字在原文，`revised` 必须逐字在改文；无法确认保持原意的句子不写进 `revisions`，放 `unresolved`。
5. **机械守恒检查**（关键步骤）：

```bash
python3 scripts/polish_check.py \
  --original /app/work/original.txt \
  --revised  /app/work/revised.txt \
  --glossary /app/work/glossary.json \
  --revisions /app/work/results_draft.json \
  --out /app/work/check.json
```

`verdict=FAIL` 时必须改回：数值/单位/引用/指向被动过、否定被删、限定被升级（may→prove）、条件或量词被删，都会判 FAIL。

6. **序列化交付**：

```bash
python3 scripts/serialize_result.py \
  --case /input/case.json \
  --draft /app/work/results_draft.json \
  --out /app/output/result.json \
  --skill-name academic-language-polishing
```

7. **自检**：`python3 tests/selftest.py`（24 项断言应全过）；确认 `result.json` 九字段齐全、`preserves_meaning` 全为 true、`unresolved` 写明未确认项。

## 输出契约（result.json）

顶层：`case_id, task_id, status, results, sources, uncertainty, changes, artifacts, metadata`（定义见 `resources/output_contract.json`，通用规范见 `resources/conventions.md`）。

`results` 结构：

```json
{
  "revised_text": "润色后的完整文本",
  "revisions": [
    {"span": "sentence 1", "original": "原文片段", "revised": "改后片段",
     "type": "grammar", "reason": "为什么改", "preserves_meaning": true}
  ],
  "glossary": [{"concept": "…", "en_form": "…", "zh_form": "…", "note": "缩写首现/大小写约定"}],
  "register_notes": ["目标文体与语域决策"],
  "unresolved": ["需作者确认、本轮未改的项"]
}
```

`type` 允许：`grammar | syntax | collocation | punctuation | terminology | register | clarity | redundancy | cohesion | bilingual | other`。
`status` 允许：`success | partial | undetermined | refused`。

## 最小调用示例（示例，非正式案例结果）

```bash
python3 scripts/polish_check.py --original examples/before.txt --revised examples/after.txt \
    --revisions examples/draft.json --out examples/check.json
python3 scripts/serialize_result.py --case examples/case.example.json \
    --draft examples/draft.json --out examples/example_result.json
```

见 `examples/example_result.json`（`case_id=EXAMPLE-CASE-000`，明确标注为示例）。

## 限制与失败处理

| 情况 | 处置 |
|---|---|
| 输入超长 / 多章节 | 按章节顺序分批处理，每批落盘后再继续，保持编号与交叉引用 |
| 编码混乱、公式与引用混排 | 只改可读文本层，公式与编号原样保留；乱码段写 `uncertainty` |
| 术语表内部冲突 | 不在结果中自选一种了事；标 `unresolved`，请作者定夺 |
| 目标文体不明 | 按输入体裁推断并在 `register_notes` 声明；无法判断时 `status=undetermined` |
| 机械检查 FAIL | 必须回改；回改不了就还原该句，并在 `unresolved` 说明 |
| 无法确认原意保持 | 不写进 `revisions`，列为待确认项 |

体积约束：≤50 个 UTF-8 文本文件、单文件 ≤500KB、总量 ≤2MB、无符号链接；脚本纯标准库，Python ≥3.8。

## 资源

- `scripts/polish_check.py`：数值/单位/引用/指向/否定/限定/条件/量词/缩写/术语/修改记录共 10 类机械检查。
- `scripts/serialize_result.py`：草稿 → 契约 `result.json`，校验必填字段与枚举。
- `resources/output_contract.json`、`resources/conventions.md`：字段定义与通用工作规范。
- `templates/registers.md`：五种文体规则 + 中式英语高频问题 + 限定强度对照。
- `examples/`：合成示例（before/after/draft/case/result），非正式案例答案。
- `tests/selftest.py`：24 项断言。
