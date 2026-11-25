---
name: nanopub-claims
description: "科研文献的断言级 Nanopublication 抽取 Skill。把论文段落拆成单一可判断真假的断言（主体-受控关系-客体+条件限定），为每条断言绑定最小充分证据片段（逐字引文+页码+段落 id+字符偏移），记录论文/作者/年份/版本/标识符来源元数据，做 Q001–Q013 机械质检，并导出 JSON / CSV / TriG 三态可机读结构。Trigger on: '生成 nanopublication', '把段落拆成断言', '抽取断言和证据', '断言级证据绑定', 'claims + evidence 导出', 'make nanopublications from this paper', /input/case.json 与 /input/task.md 出现且任务涉及断言/证据/知识单元时。"
---

# nanopub-claims — 断言级证据笔记 Skill

把论文里的**结论**变成**可逐条判定真假的知识单元**：一句一断言、一条断言一份最小证据、一份证据一个可回原文的坐标，最后导出下游程序能直接解析的结构。

四个硬承诺（对应题目四个考察点）：

1. **拆得细**：一段话拆成 N 条互不嵌套的断言；复合句的并列、因果、转折分别成条，条件与限定进 `qualifiers`，不留在句子里当形容词。整段塞进一个 `text` 字段算失败。
2. **对得上**：每条断言绑定**最小充分**证据片段——片段里必须同时出现主体与客体，且是原文逐字（只允许空白差异）。直接证据与间接推论分开标。
3. **追得回**：断言 → 证据（页码/段落 id/字符偏移）→ 论文（标题/作者/年份/DOI 或文件哈希/版本）链路完整，任何人可据此回到原文同一处。
4. **读得懂**：固定字段 + JSON Schema + CSV + TriG 三态导出，重复运行逐字节一致，下游无需人工清洗。

---

## 适用与不适用

- **适用**：有文字层的科研论文/报告（英文或中文，单栏/双栏）；任务为断言抽取、证据绑定、来源记录、质量检查、结构化导出。输入可以是 PDF（先转页面文本）、平台给的 `pages.json`，或纯文本。
- **不适用/降级**：加密 PDF（`refused` 并说明）；无文字层且无 OCR（该页 `unreadable`，断言只从可读页产生）；纯图片表格里的数值（标 `image-table`，由 Agent 对照渲染图转录并标 `source: manual`）；原文访问失败（`failed`，不编造断言）。

## 运行时环境

- `SKILL_DIR`：本 SKILL.md 所在目录（评测环境为 `/skills/weekly-skill`）；脚本在 `$SKILL_DIR/scripts/`。
- Python ≥ 3.8，**只用标准库**，无网络请求。
- 输入：`/input/case.json`（`case_id` + `output_contract`）与 `/input/task.md`；材料按 case.json 给出的路径读取。
- 工作目录 `/app/work`，交付目录 `/app/output`。

## 预算纪律（限额：64 次模型请求 / 900 秒 / 每响应 16384 tokens）

- 分段与候选切分只跑一次脚本并缓存，不要反复重跑。
- 读候选时按段落批量读，不要逐条回读全文。
- `evidence.py` 批量绑定/核验，一次调用处理整组断言。
- 请求规划 ≤ 40：读输入 2 + 分段/切分 1 + 分块读原文 ≤ 12 + 写断言 ≤ 14 + 绑定 1 + 质检 1 + 导出 1 + 修补 ≤ 8。

---

## 工作流（严格按序）

### 第 0 步 — 读输入，划边界

1. 读 `/input/case.json`：记 `case_id`、`output_contract`（`result` 必须覆盖其全部字段）、材料路径。
2. 读 `/input/task.md`：任务类型（断言抽取 / 证据绑定 / 来源记录 / 质检 / 导出）与证据范围。
3. 材料缺失或路径不合法：写 `status=failed` 并在 `uncertainty` 说明，**不要编造材料**。

### 第 1 步 — 文档 → 段落（带坐标）

```bash
mkdir -p /app/work /app/output
python3 "$SKILL_DIR/scripts/segment.py" --pages /app/work/pages.json --out /app/work/paragraphs.json
```

`pages.json` 形如 `[{"page":1,"text":"整页文本"}]`；PDF 用平台 `pdf-text-tool` 逐页取文本，或用本仓库姊妹 Skill `pdf-literature-parser` 的 `parse_document.py` 产出 `document.json` 再转 `pages.json`。

每段得到 `id`（`p3b12`=第 3 页第 12 段）、`page`、`char_start/char_end`。

### 第 2 步 — 段落 → 候选断言（机械切分）

```bash
python3 "$SKILL_DIR/scripts/decompose.py" --paragraphs /app/work/paragraphs.json --out /app/work/candidates.json
```

切两层：句末标点 → 句；并列/因果连接词（并且/同时/此外/但是/因此/and/while/because…）→ 候选。这一步**不做语义**，`placeholder=true`。

### 第 3 步 — 候选 → 断言（语义填充，Agent 执行）

对每个候选判断：

1. **是否可判断真假**：是结论/观测/数值才算断言；方法描述、背景铺垫、致谢丢弃，记入 `unreported` 并写明原因。
2. **粒度**：一条候选仍含两个独立关系（"A 抑制 B 并使 C 下降"）→ 在该候选内部再切，各自成条；条件（温度、pH、剂量、时间、样本）进 `qualifiers`，不留在 `text` 里当修饰。
3. **三元组**：`subject`（name + type）、`relation.predicate` 只能取 `vocab/predicates.json` 的 id（不可映射时用 `other` 并填 `relation.free_text`）、`object`（name 或 value + unit）。
4. **语气**：原文明确断言 → `asserted_by=author`、`modality=observed`；读者推论 → `modality=inferred` 且证据标 `relation_to_assertion=indirect`；假设 → `hypothesized`。
5. **文本**：`text` 写成一句能独立判真假的话（可含数值），不得把整段抄进来。

写到 `/app/work/assertions.json`：

```json
{"case_id":"<case_id>","status":"success","source":{...},
 "assertions":[{"id":"a001","text":"…","subject":{...},"relation":{...},"object":{...},
                "qualifiers":{...},"polarity":"positive","modality":"observed",
                "asserted_by":"author","evidence":[{"quote":"…逐字…"}],
                "provenance_ref":"src-001","confidence":{"level":"high","basis":"explicit-statement"}}]}
```

`source` 必填：`source_id`（优先 DOI，无则 `sha256:<文件哈希>`）、`title`、`authors`、`year`；建议补 `venue/doi/version/retrieved_from/file_sha256/license`。**缺失字段留 `null` 并进 `uncertainty`，不要填猜测值。**

### 第 4 步 — 证据绑定与机械核验

```bash
python3 "$SKILL_DIR/scripts/evidence.py" bind \
  --assertions /app/work/assertions.json --paragraphs /app/work/paragraphs.json
python3 "$SKILL_DIR/scripts/evidence.py" verify \
  --assertions /app/work/assertions.json --paragraphs /app/work/paragraphs.json
```

- `bind`：按 `quote` 在段落里定位，回填 `page/paragraph_id/char_start/char_end`；`bind` 返回 `unbound` 的引文必须改写成原文逐字片段或移入 `uncertainty`。
- `verify`：逐条核验"引文是否逐字""偏移切出的文本是否等于引文"，非 0 退出码表示有 Q003/Q010 级问题，必须修到 0 或显式记入 `uncertainty`。
- 找句：`python3 "$SKILL_DIR/scripts/evidence.py" locate --paragraphs ... --quote "…"`。
- **最小充分**：证据片段要同时包含主体与客体；只含结论不含主体的片段视为不足（Q004）。
- 证据跨图表（数值在图/表里）：引文取题注或表头原句，`confidence.basis` 写 `table-value`/`figure-caption`，并在 `evidence.note` 写明"数值见 Table 2 第 3 行"。

### 第 5 步 — 质检

```bash
python3 "$SKILL_DIR/scripts/qc.py" \
  --assertions /app/work/assertions.json --paragraphs /app/work/paragraphs.json \
  --vocab "$SKILL_DIR/vocab/predicates.json" --out /app/work/qc_report.json
```

判定规则见下表；出现 `fail` 必须修（改断言、换证据、补来源），修不了的进 `uncertainty` 并说明。`--allow-fail` 只用于"确实无法修复且已声明"的场景。

### 第 6 步 — 导出与自查

```bash
python3 "$SKILL_DIR/scripts/export.py" \
  --assertions /app/work/assertions.json --out-dir /app/output \
  --case-id "<case_id>" --status success
```

产出 `assertion_set.json`（规范 JSON）、`assertions.csv`（19 列扁平表）、`nanopub.trig`（assertion / provenance / pubInfo 三子图）。再把 `paragraphs.json`、`qc_report.json`、`change_log.json` 复制到 `/app/output`。

`change_log.json` 每条 `{"step":"segment|decompose|bind|qc|export","detail":"…"}`，记录丢弃的候选、修复的引文、降级的页。

---

## 字段字典（速查；完整版见 `FIELD_DICTIONARY.md`）

| 字段 | 含义 | 约束 |
|---|---|---|
| `assertions[].id` | 断言标识 | `a001` 起递增，稳定不复用 |
| `text` | 单一断言句 | 一句一断言；不得整段照抄 |
| `subject` / `object` | 主体 / 客体 | `name` + `type`；数值给 `value`+`unit` |
| `relation.predicate` | 受控关系 | `vocab/predicates.json` 的 id |
| `qualifiers` | 条件限定 | 温度/pH/剂量/时长/样本等键值 |
| `polarity` / `modality` | 极性 / 认识状态 | positive\|negative；observed\|inferred\|hypothesized |
| `asserted_by` | 谁断言 | author\|reader |
| `evidence[]` | 证据 | quote 逐字 + page + paragraph_id + char_start/char_end + support + relation_to_assertion |
| `provenance_ref` | 来源引用 | 指向 `source.source_id` |
| `confidence` | 置信度 | level + basis（explicit-statement/table-value/figure-caption/cross-section-inference） |
| `qc` | 质检结论 | status + issues[{code, detail, criterion}] |

## 质检规则（Q001–Q013，均可复现）

| 代码 | 含义 | 判定（脚本实际执行） | 级别 |
|---|---|---|---|
| Q001 | 断言过宽 | 句末标点 >1，或关系 cue 命中 ≥3；或命中全称量词且 `qualifiers` 为空 | fail / warn |
| Q002 | 无证据 | `evidence[0].quote` 为空 | fail |
| Q003 | 引文非逐字 | 去掉空白后 quote 不是任何段落的子串 | fail |
| Q004 | 证据不足 | quote 缺少 subject 或 object 的 name | fail |
| Q005 | 关系未映射 | `predicate` ∉ 受控词表；`other` 但无 `free_text` | fail |
| Q006 | 来源缺失 | `source` 的 title/authors/year/source_id 任一为空 | fail |
| Q007 | 方向错误 | predicate 方向=up 而 quote 仅含下降 cue（反之亦然） | fail |
| Q008 | 数值不一致 | 断言中长度 ≥2 的数字不在 quote 内 | warn |
| Q009 | 主体错位 | subject 不在命中段落文本中 | warn |
| Q010 | 偏移不一致 | `paragraph_text[start:end]` 去空白后 ≠ quote | fail |
| Q011 | 无置信依据 | `confidence.basis` 为空或 absent | warn |
| Q012 | 语气错配 | inferred/hypothesized 却标 direct 证据 | warn |
| Q013 | 重复断言 | 归一化后文本与另一条完全相同 | warn |

## 异常处理矩阵

| 异常 | 识别 | 处置 |
|---|---|---|
| 加密 PDF | `pdfprobe` 报 `needs_password` / 打开失败 | 空口令重试；仍失败 `status=refused` + 原因 |
| 扫描件无文字层 | 该页无文本 | 有 OCR 则 OCR；无则整页 `unreadable`，只从可读页产生断言 |
| 原文访问失败 | 文件缺失/路径错 | `status=failed`，`uncertainty.kind=missing-source` |
| 证据跨图表 | 数值只在表/图 | 引题注/表头原句 + `evidence.note` 指向表行，`basis` 用 table-value |
| 找不到支撑片段 | `bind` 返回 unbound | 改写成原文子串；仍无 → 断言降级为 `inferred` 或移入 `uncertainty` |
| 断言与证据冲突 | Q007 / Q004 | 以原文为准改断言；原文本身自相矛盾 → `uncertainty.kind=conflict` 并列出两处位置 |
| 字段缺失 | Q006 / Q011 | 补元数据；确实无 → `null` + `uncertainty`，不猜 |
| 重复运行 | — | 全流程确定性（无随机/无时间戳），先清 `/app/work/*.json` 再跑 |

## 自查清单（导出前）

- [ ] 每条断言 `text` 只含一个可判断的关系；条件在 `qualifiers` 里
- [ ] 每条断言 `evidence[0]` 同时包含 subject 与 object，且 `verify` 通过
- [ ] `predicate` 全部在受控词表内；`other` 都带 `free_text`
- [ ] `source` 四项齐全（title/authors/year/source_id），缺失项已进 `uncertainty`
- [ ] `qc` 无 `fail`；有 `warn` 的已说明理由
- [ ] 三个导出文件存在；`assertions.csv` 行数 = 断言数 + 1
- [ ] `status` 与内容一致（partial 必须写明限制与接管位置）
- [ ] 示例产物与本次案例产物分开，本案例结果无 `synthetic` 标记
