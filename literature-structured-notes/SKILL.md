---
name: literature-structured-notes
description: "把一篇论文整理成可复用的结构化笔记：论文卡片（研究问题/数据/方法条件/主要发现/局限）、按论文自身章节顺序的章节笔记、可检索知识点，以及每条笔记的原文回链。用于论文卡片、章节总结、知识点提取与保留来源的笔记；不要用通用摘要模板覆盖论文实际论证结构。"
---

# 阅读10｜文献总结与结构化笔记

## 用途与触发条件
把论文读成「下次还能直接用」的笔记：骨架跟随论文自身章节与论证顺序，所有结论可回查到章节与段落。

**适用**：论文卡片、章节总结、知识点提取、来源保留、结果复核。
**不适用**：不做预制答案，不解释题面未要求的科学结论，不编造测试成绩或运行日志。

## 核心要求
- **对得上**：笔记骨架等于论文章节顺序，不套通用五段式。
- **留得住**：研究问题、数据、方法条件、主要发现、局限都要落到字段，尤其是结论成立的前提。
- **找得回**：每条笔记带 `section + paragraph` 定位，且能在 `sources` 里找到同段原文。
- **用得上**：知识点可检索、可比较；术语去重，不把同一件事写成两条。

## 执行流程
1. 读 `/input/case.json` 与 `task.md`，确认材料、约束与证据范围；`case_id` 原样保留。
2. 归一材料：`sections[].paragraphs[]`（每段有 `id` 与 `text`）或 `document.paragraphs[]`（带 `section`）。章节标题不合并、不重排。
3. 机械抽取草稿：`python3 scripts/notes.py build --case /input/case.json --out /app/work/results_draft.json`。脚本按线索词挑研究问题（含 whether/是否/问号）、数据（dataset/samples/n=）、方法（we used/采用）、发现（数字与增减）、局限（limitation/不足），并按章节生成 `purpose/method/result/conclusion`。
4. Agent 语义层修订草稿：把误判的句子换掉、缺项写明「原文未明确」、合并同义术语；不得补写原文没有的数字或条件。
5. 序列化交付：`python3 scripts/serialize_result.py --input /input/case.json --draft /app/work/results_draft.json --out /app/output/result.json --task-id <slug>`。校验不过会直接失败退出，按报错回改。
6. 自查：章节顺序、卡片五字段、知识点 ≥5、每条 locator 可反查、`uncertainty` 写清未报告项。

## 输出契约（result.json）
顶层：`case_id, task_id, status, results, sources, uncertainty, changes, artifacts, metadata`。
`results` 只允许四个键：

```json
{
  "paper_card": {"research_question": "", "data": "", "methods": "", "findings": "", "limitations": ""},
  "section_notes": [{"section": "", "purpose": "", "method": "", "result": "", "conclusion": "",
                     "source_id": "", "locator": "section <title>, paragraph <pid>"}],
  "knowledge_points": [{"term": "", "type": "metric|method|concept", "statement": "", "aliases": "",
                        "source_id": "", "locator": "section <title>, paragraph <pid>"}],
  "comparison_fields": ["research_question", "methods", "findings", "limitations"]
}
```

字段定义见 `resources/output_contract.json`（官方平铺示例）与 `resources/field_definitions.md`。

## 规则与边界
- 章节笔记顺序必须等于输入章节顺序；为空的内容字段可留空字符串，但四个都空 = 没写笔记，校验器会拒。
- `status=success` 时卡片五字段不得为空；缺任一项就写 `partial` 并在 `uncertainty` 说明缺什么。
- 数值、条件、样本量只从原文抄；原文没给就留空并登记，不做推断。
- 图表内数值需 PDF/表格转录；只有文本层时在 `uncertainty` 写明。
- 资源约束：≤50 个 UTF-8 文本文件、单文件 ≤500 KB、总 ≤2 MB、无符号链接。

## 异常处理
| 情况 | 处置 |
|---|---|
| 无 `sections`/`paragraphs` | 报「未识别到章节」，`status=undetermined`，不编笔记 |
| 章节标题缺失 | 按 `Section N` 编号，保留原顺序，`uncertainty` 标注 |
| 卡片某字段原文没写 | 留空 + `partial` + `uncertainty`，不补常识 |
| 定位指不到段落 | 序列化器直接拒绝；回到原文重新取 pid |
| 中文/英文混排 | 中英句末标点都切句；小数（0.5）不得被切成两句 |

## 资源
- `scripts/notes.py`：章节切分、线索词抽取、卡片与笔记生成（纯标准库）。
- `scripts/serialize_result.py`：官方契约组装与校验。
- `resources/output_contract.json`、`resources/field_definitions.md`、`resources/conventions.md`。
- `examples/case.example.json` + `examples/output/result.json`（自造语料，非正式答案）。
- `tests/selftest.py`：23 项断言。
