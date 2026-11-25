---
name: litkg-builder
description: "Build an evidence-bound literature knowledge graph (实体-关系-证据图谱) from one or more paper materials, with per-paper source_id, JATS paragraph_id and verbatim short quotes on every node and edge, explicit cross-paper merge / no-merge decisions, conflict records, at least three executable queries, incremental re-build without renumbering, and export to JSON/CSV/GraphML/Cypher/HTML. Trigger on: 'literature knowledge graph', 'knowledge graph from papers', '文献知识图谱', '实体关系抽取', 'extract entities and relations from these papers', 'build a citation-grounded KG', '图谱查询与证据', 'entity alignment across papers', '增量更新图谱', or when a task asks for entities/relations with paragraph-level evidence and cross-paper alignment."
---

# litkg-builder — 证据绑定的文献知识图谱

**一句话**：把一批论文变成可查询的节点与边，每个节点和每条边都能回到某篇论文的某个 JATS 段落与一句原文。

机械层（本 Skill 的脚本）负责切句、定位、候选抽取、证据校验、导出；语义层（你，Agent）负责判定实体类型、接受或否决合并、补模式漏掉的关系。**脚本产出的都是"候选"，不是结论；对外交付前必须过第 4 步与第 7 步。**

## 0. 触发与边界

用：需要从论文材料构建"实体—关系—证据"结构、要求跨篇对齐、要求回原文复核时。
不用：只需要摘要或翻译（直接做）；只需要读单篇问答（不必建图）；输入根本没有段落文本（先说明缺料）。

## 1. 读输入（不许按标签猜内容）

输入固定为 `/input/case.json` 与 `task.md`，材料在旁侧 JSON（常见：`corpus-manifest.json`、`material.json`、`primary-material.json`、`secondary-material.json`）。先看清再动手：

```bash
python3 scripts/kg.py build --case /input/case.json --out /app/work/kg
```

- 根级 `doi`/`title`/`authors` 属于**第一篇**，不得套到第二篇；每篇的 `source_id`（P1/P2…）独立。
- 段落位置一律用 **JATS 段落 ID**。没有 PDF 页码就绝不写页码，也不能把自建分页称作"原 PDF 第 1 页"。
- 输入未给段落 ID 时脚本会生成并标 `pid_synthetic`，这一限制要写进结果的 `uncertainty`。

## 2. 机械建图

上一条命令会产出 `kg.json`、`nodes.csv`、`edges.csv`、`kg.graphml`、`kg.cypher`、`kg.html`、`queries.json`，并打印 `nodes / edges / qc_fail / qc_warn / status`。候选来自线索词模式（using 使用、compared with 比较、outperforms 优于、et al. 转述…），**只覆盖显式句式**，漏抽是常态，靠第 4 步补。

## 3. 实体判定（逐条过，别整段照抄）

对每个节点确认三件事：`type` 是否与词表一致（`vocab/entity_types.json`）、`label` 是否是原文真实表述、`quote` 是否同句包含该表述。

- 类型纠正：把归错类的节点改对（如 `photoreduction` 应为 `task` 而非 `material`）。
- 丢弃：泛词（"study"、"results"）、纯数值、非原文出现的概念一律不要。
- 保留原文位置与原文表述；同义改写不算实体。
- 分自述/转述：`author_claim`（本文做的）vs `cited_claim`（"X et al. reported…"）。转述不得写成作者结论。

## 4. 关系判定（宁缺勿滥）

只保留有证据的关系，逐条看 `kg.json` 的 `edges`：

- 类型与方向必须与原文一致；`compared_with` 只说明"发生比较"，不等于"优于"。
- 比较类（`outperforms`/`compared_with`）能写条件就必须写（温度、浓度、样本、数据集）；原文没给就留空并在结果里记为未报告，不要补常识条件。
- 同一句里两个同类方法之间的"使用"不建边（脚本已过滤，人工也别加）。
- 共现不算因果；综述式"已被广泛使用"只能记为 `mentions`，不能成为结论依据。

模式漏掉但原文确有的关系，用补丁加入（脚本会逐条校验引文能否定位，定位失败自动拒绝）：

```bash
cat > /app/work/patch.json <<'JSON'
{"edges": [{"type": "uses", "subject_label": "in situ XRD", "object_label": "Cu-doped TiO2",
            "conditions": "", "strength": "direct", "attribution": "author_claim",
            "evidence": [{"source_id": "P1", "paragraph_id": "P1-p002",
                          "quote": "Phase identification was carried out using in situ XRD"}]}]}
JSON
python3 scripts/kg.py patch --kg /app/work/kg/kg.json --patch /app/work/patch.json --corpus /input/case.json
```

## 5. 跨篇对齐（本题最容易被扣分的地方）

`merges` 里每条都有 `basis` 与 `rule`，按下面四条判定，**不能为了"图更整齐"强行合并**：

| 规则 | 何时用 | 处置 |
|---|---|---|
| R-SAME / R-NORM | 同篇同类型同表述（或同篇异写） | 合并 |
| R-GENERIC | 跨篇**通用**类型（方法、任务、机构）且规范形式一致 | 合并，basis 写明"通用术语非具体实例" |
| R-INSTANCE | 跨篇材料/样品/数据集/模型/指标/条件 | **不合并**，各自成节点；相同通用材料名 ≠ 同一物理样品 |
| R-TYPE | 同名但类型不同 | 不合并，标 `needs_review` |

跨篇数值不同（如两篇给出不同效率）→ `conflicts` 记 `kept_separate`，说明"指标名相同但条件/样品不同，不合并、不取均值、不合成一个结论"。原文明确互相矛盾 → `kept_both`，双方条件都要留。

## 6. 查询（至少 3 个，必须真跑）

```bash
python3 scripts/kg.py query --kg /app/work/kg/kg.json --expr "entity:<标签>"
python3 scripts/kg.py query --kg /app/work/kg/kg.json --expr "relation:outperforms"
python3 scripts/kg.py query --kg /app/work/kg/kg.json --expr "cross:papers"
```

每个查询结果都要能落到 `source_id + paragraph_id + quote`；查不到就写进 `undetermined`（"图谱无该实体/无该关系的直接证据"），**不要用其他段落的句子顶替**。推荐三条固定问法：①某方法/材料被谁用、在什么条件下；②`outperforms` 有哪些、条件是什么；③跨篇哪些合并了、哪些刻意没合并。

## 7. 交付

`build` 已经把 `result.json` 写到输出目录。核对并补齐：

```bash
python3 scripts/kg.py build --case /input/case.json --out /app/output --case-id "<case_id>"
```

`result.json` 必需字段：`case_id`、`status`（success / partial / unable_to_determine）、`graph`（nodes/edges/merges/conflicts）、`queries`、`qc`、`uncertainty`（undetermined / unreported / conflicts / notes）、`artifacts`、`change_records`。
若 `case.json` 或 `task.md` 声明了 `output_contract`，逐项确认都已覆盖；缺项要么补，要么在 `uncertainty` 里写明原因。
配套导出 `kg.html` 供人眼复核；`kg.cypher`/`kg.graphml` 供下游入库。增量更新用同一 `--out` 目录重跑：节点/边编号按出现顺序稳定生成，新增论文的节点追加在后，既有编号不变；合并与冲突的处置记录保留在 `merges`/`conflicts`，不覆盖历史。

## 8. 异常与自查

| 情况 | 处置 |
|---|---|
| 找不到 `material.json` 等旁侧文件 | 用 `build --case <目录>` 递归识别；仍无段落 → `status=unable_to_determine` 并写缺什么 |
| PDF/XML 解析失败 | 说明失败位置，改走文本层；无文本层则拒答，不臆造 |
| 同名不同物 | 不合并，`R-TYPE`/`R-INSTANCE` + `needs_review` |
| 证据互相冲突 | `kept_both`，双方条件并列，不取平均 |
| 查询无结果 | `undetermined` 明确写"图谱未覆盖" |

自查（每次交付前跑一遍）：

```bash
python3 tests/selftest.py          # 32 项 fixture 断言，应全过
python3 scripts/kg.py build --case /input/case.json --out /app/work/check --case-id check
```

验收线：`qc.summary.fail == 0`；所有节点/边 `evidence` 非空且 `quote` 能在对应段落定位；`queries` ≥ 3 且每条含 `rows` 或 `undetermined`；`merges` 每条有 `basis`+`rule`；`conflicts` 全部 `kept_separate`/`kept_both`。

## 资源

`vocab/entity_types.json`（10 类实体与实例标记）、`vocab/relation_types.json`（11 类关系、方向与证据强度定义）、`schemas/kg.schema.json`、`scripts/kg.py`（单文件，纯标准库，Python ≥3.8）、`tests/selftest.py`、`examples/corpus.synthetic.json`（全合成示例，非真实文献）。
