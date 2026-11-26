# litkg-builder

把论文材料建成**可回原文的知识图谱**：每个节点、每条边都带 `source_id` + JATS `paragraph_id` + 原文短引；跨篇合并与否都有依据；冲突不合并不取均值；查询真跑真出证据。

## 快速开始

```bash
python3 scripts/kg.py build --case /input/case.json --out /app/output --case-id "<case_id>"
python3 scripts/kg.py demo  --out ./examples/output     # 合成示例，非真实文献
python3 scripts/kg.py query --kg ./examples/output/kg.json --expr "entity:Cu-doped TiO2"
python3 tests/selftest.py                                # 41 项断言
```

只依赖 Python ≥3.8 标准库，无第三方包、无网络、无 GPU。

## 产出

| 文件 | 内容 |
|---|---|
| `result.json` | 官方契约：`case_id` / `task_id` / `status` / `results`（papers + graph + queries + qc）/ `sources` / `uncertainty` / `changes` / `artifacts` / `metadata` |
| `kg.json` | 完整图谱（论文、节点、边、合并记录、冲突） |
| `nodes.csv` / `edges.csv` | 供表格复核 |
| `kg.graphml` / `kg.cypher` | 供 Gephi / Neo4j 导入 |
| `kg.html` | 人眼复核视图（节点表 + 关系表，含引文） |
| `queries.json` | ≥3 个查询的结果、证据与无法确定项 |

## 文件

```
SKILL.md                      Agent 使用手册（触发、流程、判定规则、自查）
scripts/kg.py                 单文件核心：装载/抽取/对齐/建边/质检/查询/导出/补丁
scripts/serialize_result.py   草稿 → 契约形态 result.json（含必填校验）
resources/output_contract.json  result.json 字段定义（含示例标注）
resources/conventions.md      通用工作规范（证据/诚实状态/产物位置/体积/禁止事项）
vocab/entity_types.json       10 类实体定义 + 实例级标记
vocab/relation_types.json     11 类关系：方向、是否需条件、证据强度
schemas/kg.schema.json        图谱 JSON Schema（draft 2020-12）
tests/selftest.py             41 项 fixture 断言（全过为合格）
examples/corpus.synthetic.json  全合成两篇论文，DOI 为 10.0000 保留段
examples/output/              合成示例的构建产物（示例，不是正式案例结果）
```

## 字段约定（摘）

- `papers[].source_id`：`P1`/`P2`…，一篇一个，独立编号；根级 DOI/标题/作者只属第一篇。
- `nodes[].evidence[]`：`{source_id, paragraph_id, section, quote(12–300字), attribution, strength}`。
- `attribution`：`author_claim`（本文自述）/ `cited_claim`（转述他人）；转述不得写成作者结论。
- `edges[].conditions`：比较类关系必须尽量填；原文未报告就留空，不补常识。
- `merges[].rule`：`R-SAME`/`R-NORM`（合并）、`R-GENERIC`（跨篇通用术语）、`R-INSTANCE`（跨篇实例不合并）、`R-TYPE`（同名异类不合并）、`R-AGENT`（Agent 补丁）。
- `conflicts[].resolution`：只有 `kept_separate` / `kept_both`；跨篇同指标不同数值一律不合并。
- 位置只有段落 ID；本 Skill 不写页码，也不把自建分页称作原 PDF 页。

## 质检码

`K001` 节点无证据 · `K002` 段落不存在 · `K003` 引文无法定位 · `K004` 引文过短 · `K005` 边端点缺失 · `K006` 关系类型不在词表 · `K007` 比较关系缺条件（warn） · `K008` 边引文无法定位 · `K009` 跨篇实例被合并 · `K010` 段落 ID 由工具生成（warn） · `K011` 冲突被合并 · `K012` 结论性关系用间接证据（warn）

## 限制

- 线索词模式只覆盖显式句式，漏抽需按 SKILL.md 第 4 步用 `patch` 子命令补，补的边同样要过引文定位校验。
- 输入无 PDF 时不给页码、不读图、不推断图表数值。
- 跨篇是否"同一物"最终由人/Agent 判定，脚本只按规则给出禁止合并的边界。
- 示例语料全部合成（`10.0000/…` 为样例保留段），不得当作真实科研结论引用。

## 来源与许可

自研，无外部依赖与第三方代码。示例语料 CC0-1.0。

