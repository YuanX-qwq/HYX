---
name: intro-related-work-writing
description: "Write the introduction and related work with traceable evidence: turn a real bibliography into problem/method/evaluation grouped comparisons (conclusion, conditions, limitation per work), derive the research gap only when at least two cited works share a limitation, keep each contribution anchored to an actual figure/table/result id, and audit citation coverage (uncited factual sentences, missing key or recent works, unknown keys). Use for 研究背景、相关工作组织、研究空白、贡献表述、引用覆盖."
---

# 写作08｜引言与相关工作写作

## 用途与触发条件

在 Bohrium Playground（Harbor 评测）环境中，针对组织方给定案例产出**引言与相关工作**的可复核草案。
Skill 装到 `/skills/weekly-skill`，输入 `/input/case.json` 与 `task.md`，过程产物 `/app/work`，最终 `/app/output`。

**适用**：研究背景脉络化；相关工作按维度分组比较；从已引局限推导研究空白；贡献与图表/结果对照；引用覆盖与元数据核对。
**不适用**：编造文献、编造实验数值、用模板套话冒充研究现状、提交预制答案。

## 核心关注点

- **立得住**：背景给出年份跨度、发表渠道、问题设定与具体未解决问题，不写"近年来受到广泛关注"。
- **分得清**：按 `problem / method / evaluation` 三个维度分组；每条工作都带结论、适用条件、局限三格，空则留空并降证据强度，不补编。
- **说得实**：研究空白必须由 ≥2 条已引工作的共同（或冲突）局限支撑；只有 1 条时标 `insufficient`，没有证据时 `gap` 留空、`status` 降级。
- **对得上**：每条贡献绑定 `fig:/tab:/res:` 编号，编号不存在或与图表说明无词元重合即判不通过，不写进贡献表。

## 执行流程

1. **读取输入**：`/input/case.json` + `task.md`，确认语言、篇幅、目标期刊格式与证据范围；`case_id` 原样保留。
2. **解析文献库**：BibTeX / RIS / 纯文本 → 结构化记录（题名、作者、年份、刊名、DOI、摘要、抽取出的结论/条件/局限）。
3. **按维度分组**：三条维度词表命中打分，全部未命中的记录列入 `uncertainty` 而不是硬塞进某一组。
4. **推导空白**：对"局限句"做词元相似聚类，支持 ≥2 才算成立，输出参与条目与原文短引。
5. **贡献对照**：逐条映射到本文图表/结果编号，定位失败或说明不符的条目不进贡献表、进 `uncertainty`。
6. **引用覆盖审计**：事实句（含数字/结果动词）无引用、关键工作未引、近期（近 3 年）进展未引、引用键不在库内，全部列出。
7. **写正文**：按 `templates/related_work.md` 的分组叙述规则写引言，每个事实句后带 `[key]`。
8. **序列化 + 自检**：`serialize_result.py` 生成九字段 `result.json`；`tests/selftest.py`（31 项）应全过。

## 输出契约（result.json）

顶层：`case_id, task_id, status, results, sources, uncertainty, changes, artifacts, metadata`（定义见 `resources/output_contract.json`，通用规范见 `resources/conventions.md`）。

`results` 五个子结构（缺一不可）：

```json
{
  "background": {"thread": "", "problem": "", "constraints": "", "open_issue": ""},
  "related_work": [{"group": "", "dimension": "problem|method|evaluation",
                    "works": [{"ref": "", "conclusion": "", "conditions": "", "limitation": ""}]}],
  "gap": {"gap": "", "evidence": "", "how_paper_fills": ""},
  "contributions": [{"claim": "", "evidence_locator": "fig:1|tab:2|res:R1|ref:key"}],
  "citations_coverage": {"key_works": [], "recent_works": [], "missing": []}
}
```

序列化器校验：`related_work` 至少覆盖 2 个维度、每条 work 四格齐全、`status=success` 时 `gap.evidence` 必须非空、`sources` 每条要 `source_id/locator/locator_type/quote`。

## 最小调用示例（示例，非正式案例结果）

```bash
python3 scripts/introkit.py assemble --case examples/case.json --library examples/library.bib \
    --intro examples/intro.md --paper examples/paper.json --out /app/work/results_draft.json
python3 scripts/serialize_result.py --input examples/case.json --draft /app/work/results_draft.json \
    --out examples/example_result.json --skill-name intro-related-work-writing
```

示例产物 `examples/example_result.json`：`case_id=EXAMPLE-CASE-000`，3 个维度 6 条工作、空白由 2 条文献共同局限支撑、3 条贡献通过对照、1 条贡献因定位失败被剔除并计入不确定项。

## 限制与失败处理

| 情况 | 处置 |
|---|---|
| 文献库为空或缺摘要 | 退化为题名级证据（`evidence_strength=title_only`），结论只写题名可支撑的部分 |
| 记录未命中任何维度 | 列入 `uncertainty`，不强行归组 |
| 共同局限只有 1 条 | `gap.strength=insufficient`，`status=partial`，并在空白句写明"单一工作局限" |
| 贡献找不到图表/结果编号 | 不进贡献表，写入 `uncertainty` 要求补图表或改写 |
| 正文事实句无引用 | 逐句列出 offset 与原文，要求补引用或标为作者判断 |
| 引用键不在文献库 | 列为 `unknown_citations`，不静默当有效引用 |
| 体量超限 | 分批处理并落盘中间结果，保持编号一致 |

体积约束：≤50 个 UTF-8 文本文件、单文件 ≤500KB、总量 ≤2MB、无符号链接；脚本纯标准库，Python ≥3.8。

## 资源

- `scripts/introkit.py`：`parse / group / gap / contrib / coverage / assemble` 六个子命令。
- `scripts/serialize_result.py`：草稿 → 契约 `result.json`，含维度、空白、贡献、覆盖校验。
- `resources/output_contract.json`、`resources/conventions.md`：字段定义与通用规范。
- `templates/related_work.md`：分组叙述规则、空白推导句式、贡献写法与禁用语。
- `examples/`：合成文献库、示例引言、示例 paper.json 与标注为示例的结果。
- `tests/selftest.py`：31 项断言（含 5 类负例）。
