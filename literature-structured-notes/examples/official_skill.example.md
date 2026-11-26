---
name: literature-structured-notes
description: "Read a paper and produce reusable structured notes aligned to the paper's own chapter order: a paper card with research question, data, method conditions, main findings and limitations, section-level summaries, retrievable knowledge points, and source back-links for every note. Use for paper cards, section summaries, knowledge-point extraction and source-preserving note taking. Do not force a generic summary template over the paper's actual argument structure."
---

# 阅读10｜文献总结与结构化笔记

## 用途与触发条件
本 Skill 用于在 Bohrium Playground（Harbor 评测）环境中，针对组织方提供的固定科研案例完成本题指定的
文献总结与结构化笔记任务。评测时 Skill 被安装到 `/skills/weekly-skill`，由官方 Harness 在每个
固定原始案例上运行；输入为 `/input/case.json` 与 `task.md`，过程产物放 `/app/work`，最终结果放 `/app/output`。

**适用**：可聚焦其一：章节总结；论文卡片；知识点提取；来源保留；结果复核与复用。

**不适用**：不做预制答案、不解释题目未要求的科学结论、不编造测试成绩或运行日志。

## 核心关注点
- 对得上：笔记骨架与论文自身章节和论证顺序一致，不套用通用摘要模板。
- 留得住：研究问题、数据、方法条件、主要发现与局限都记录，尤其是让结论成立的前提条件。
- 找得回：每条关键笔记指回具体章节、段落、页码或图表，不只给笼统出处。
- 用得上：笔记可检索、可比较、可继续加工，能被下一次阅读或写作直接使用。

## 执行流程
1. **读取输入**：先读 `/input/case.json` 与 `task.md`，确认任务边界、输入材料、约束与证据范围；`case_id` 原样保留。
2. **材料解析**：按本题方向读取真实材料文件，记录每条结论对应的来源定位（来源 ID、章节/段落/图表/公式编号、原文短引）。
3. **结构化处理**：依据下方 `results` 模式组织主结果；区分直接证据与间接推论、作者自述与他人转述。
4. **证据与不确定性**：未报告、冲突、读不出或 OCR 乱码的内容写入 `uncertainty`，不靠猜补齐；部分结果写明边界。
5. **序列化交付**：把 results、sources、uncertainty、changes、artifacts 写入草稿 `/app/work/results_draft.json`，
   运行 `python3 scripts/serialize_result.py` 生成 `/app/output/result.json`（字段见 `resources/output_contract.json`）。
6. **预览与自检**：可编辑产物同时渲染真实 PDF/PNG 预览；对照本 SKILL 的输出模式与通用规范逐项自检。

## 输出契约（result.json）
顶层字段：`case_id, task_id, status, results, sources, uncertainty, changes, artifacts, metadata`，
完整定义见 `resources/output_contract.json`。`results` 本题结构如下：

```json
{
  "paper_card": {
    "research_question": "string",
    "data": "string",
    "methods": "string",
    "findings": "string",
    "limitations": "string"
  },
  "section_notes": [
    {
      "section": "string",
      "purpose": "string",
      "method": "string",
      "result": "string",
      "conclusion": "string",
      "source_id": "string",
      "locator": "string"
    }
  ],
  "knowledge_points": [
    {
      "term": "string",
      "type": "string",
      "statement": "string",
      "aliases": "string",
      "source_id": "string",
      "locator": "string"
    }
  ],
  "comparison_fields": [
    "fields kept uniform across papers for side-by-side comparison"
  ]
}
```

## 题面特殊约定
区分哪些字段可由机器判定、哪些必须人工确认；处理术语、缩写与同义表述，避免条目重复或彼此矛盾。

## 资源与依赖
- `scripts/serialize_result.py`：仅用 Python 标准库，组装并校验 `result.json`，无第三方依赖。
- `resources/conventions.md`：通用工作规范（证据、诚实状态、产物位置、体积约束、禁止事项）。
- `templates/`：本题领域模板；`examples/`：标注为示例的结果样例。
- 运行时若需要解析 PDF / 编译 LaTeX / 渲染 Office，使用平台预置工具；依赖版本与来源在说明中写清。

## 最小调用示例
输入草稿（`/app/work/results_draft.json`，节选，**仅为示例**）：

```json
{
  "paper_card": {
    "research_question": "（示例）",
    "data": "（示例）",
    "methods": "（示例）",
    "findings": "（示例）",
    "limitations": "（示例）"
  },
  "section_notes": [],
  "knowledge_points": [],
  "comparison_fields": [
    "research_question",
    "methods",
    "findings",
    "limitations"
  ]
}
```

执行：

```bash
python3 scripts/serialize_result.py   --input /input/case.json   --draft /app/work/results_draft.json   --out /app/output/result.json   --skill-name literature-structured-notes
```

输出 `/app/output/result.json`，`status` 为 `success|partial|undetermined|refused`，每条关键结论均可回溯到 `sources`。

## 限制与失败处理
- 材料不足或冲突无法判定时，`status=undetermined` 并在 `uncertainty` 说明原因与待确认项。
- 工具不可用、文件缺失、加密/扫描件无法识别时，记录异常与可人工接管位置，不伪造成功结果。
- 体积约束：≤50 个 UTF-8 文本文件，单文件 ≤500 KB，总量 ≤2 MB，无符号链接。
