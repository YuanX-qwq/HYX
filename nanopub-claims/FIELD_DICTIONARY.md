# 字段字典（nanopub-claims v1.0）

`assertion_set.json` 的每个字段：类型、必填、含义、取值约束、示例。机器校验以
`schemas/assertion_set.schema.json` 为准；本文件是给人看的同一份契约。

## 顶层

| 字段 | 类型 | 必填 | 含义 | 约束 / 示例 |
|---|---|---|---|---|
| `schema_version` | string | 是 | 版本常量 | 固定 `nanopub-claims/1.0` |
| `case_id` | string | 是 | 输入案例标识 | 与 `/input/case.json` 的 `case_id` 一致 |
| `status` | enum | 是 | 运行状态 | `success` / `partial` / `failed` / `unable` / `refused` |
| `source` | object | 是 | 论文来源元数据 | 见下表 |
| `document` | object | 否 | 文档级信息 | `page_count` / `paragraph_ids` / `text_sha256` |
| `assertions` | array | 是 | 断言列表 | 每条见「断言」 |
| `unreported` | array\<string\> | 否 | 原文未报告的项 | 每条写清"哪一内容原文没写" |
| `uncertainty` | array | 否 | 不确定/冲突 | `{kind, detail, assertion_id, location}` |
| `qc_summary` | object | 否 | 质检汇总 | 由 `qc.py` 写入 |

### `source`

| 字段 | 类型 | 必填 | 含义 | 示例 |
|---|---|---|---|---|
| `source_id` | string | 是 | 稳定标识，去重键 | `10.1234/abcd.2026.001` 或 `sha256:9f2c…` |
| `title` | string | 是 | 论文标题 | `Potassium sensing in strain K-12` |
| `authors` | array\<string\> | 是 | 作者列表 | `["A. Author","B. Author"]` |
| `year` | integer | 是 | 年份 | `2026` |
| `venue` | string\|null | 否 | 期刊/会议 | `Synthetic Journal` |
| `doi` | string\|null | 否 | DOI | `10.1234/abcd` |
| `version` | string\|null | 否 | 版本（预印本/修订） | `v2 preprint` |
| `retrieved_from` | string\|null | 否 | 材料来源 | `/input/paper.pdf` 或 URL |
| `file_sha256` | string\|null | 否 | 文件哈希 | `9f2c…` |
| `license` | string\|null | 否 | 许可 | `CC-BY-4.0` |

### 断言 `assertions[]`

| 字段 | 类型 | 必填 | 含义 | 约束 |
|---|---|---|---|---|
| `id` | string | 是 | 断言标识 | `^a\d{3,}$`，`a001` 起，稳定不复用 |
| `text` | string | 是 | 断言句 | 一句一断言；可含数值；**不得整段照抄** |
| `subject` | object | 是 | 主体 | `{name,type,identifier?,value?,unit?}` |
| `relation` | object | 是 | 关系 | `{predicate,free_text?,direction?}` |
| `object` | object | 是 | 客体 | 同 `subject` 结构 |
| `qualifiers` | object | 否 | 条件限定 | `temperature` / `ph` / `dose` / `duration` / `population` 等 |
| `polarity` | enum | 否 | 极性 | `positive` / `negative`（默认 positive） |
| `modality` | enum | 否 | 认识状态 | `observed` / `inferred` / `hypothesized` |
| `asserted_by` | enum | 否 | 谁断言 | `author`（原文明确）/ `reader`（读者推论） |
| `evidence` | array | 是 | 证据列表 | ≥1 条，见「证据」 |
| `provenance_ref` | string | 是 | 来源引用 | 指向 `source.source_id` |
| `confidence` | object | 是 | 置信度 | `{level,basis,note?}` |
| `qc` | object | 是 | 质检结论 | `{status,issues[]}` |

### `subject` / `object`（entity）

| 字段 | 类型 | 必填 | 含义 | 取值 |
|---|---|---|---|---|
| `name` | string | 是 | 实体名 | 原文用词（不擅自翻译） |
| `type` | enum | 是 | 实体类型 | `material`/`compound`/`gene`/`protein`/`organism`/`process`/`metric`/`condition`/`model`/`dataset`/`other` |
| `identifier` | string\|null | 否 | 稳定标识 | CAS / UniProt / 基因 ID |
| `value` | number\|string | 否 | 取值 | 数值断言用 |
| `unit` | string\|null | 否 | 单位 | `per hour`、`percent (w/v)`（原样保留） |

### `relation`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `predicate` | string | 是 | 只能取 `vocab/predicates.json` 的 id |
| `free_text` | string\|null | 条件必填 | `predicate=other` 时必填，记录原文动词 |
| `direction` | enum | 否 | `up` / `down` / `none`，须与词表一致 |

### 证据 `evidence[]`

| 字段 | 类型 | 必填 | 含义 | 约束 |
|---|---|---|---|---|
| `quote` | string | 是 | 逐字引文 | 与原文仅允许空白差异 |
| `page` | integer | 是 | 物理页码 | 与段落 `page` 一致 |
| `paragraph_id` | string | 是 | 段落 id | `p{page}b{n}` |
| `char_start` | integer | 是 | 段内起始偏移 | 0 基，含 |
| `char_end` | integer | 是 | 段内结束偏移 | 开区间 |
| `bbox` | array\|null | 否 | 区块坐标 | PDF 场景可选 |
| `support` | enum | 是 | 支持强度 | `full` / `partial` |
| `relation_to_assertion` | enum | 是 | 直接/间接 | `direct`（原文直述）/ `indirect`（推论所需） |
| `note` | string\|null | 否 | 补充 | 如"数值见 Table 2 第 3 行" |

### `confidence`

| 字段 | 类型 | 必填 | 取值 |
|---|---|---|---|
| `level` | enum | 是 | `high` / `medium` / `low` |
| `basis` | enum | 是 | `explicit-statement` / `table-value` / `figure-caption` / `cross-section-inference` / `absent` |
| `note` | string\|null | 否 | 判定依据的自由说明 |

### `qc`

| 字段 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `status` | enum | 是 | `pass` / `warn` / `fail`（任一 fail 即 fail） |
| `issues[]` | array | 否 | `{code, detail, criterion, severity}`；`criterion` 是脚本实际执行的判定式 |

## CSV 列（`assertions.csv`，19 列，行序 = 断言顺序）

`assertion_id, assertion_text, subject, predicate, object, polarity, modality, qualifiers, evidence_quote, page, paragraph_id, char_start, char_end, support, relation_to_assertion, provenance_ref, confidence_level, confidence_basis, qc_status`

## TriG（`nanopub.trig`）

三个子图：`sub:assertion`（每条断言三元组 + `np:hasEvidence` 指向证据节点）、`sub:provenance`
（`prov:wasDerivedFrom` 指向来源）、`sub:pubinfo`（标题/作者/年份）。命名空间：`np:`
=`http://nanopub.org/nschema#`，`prov:`=`http://www.w3.org/ns/prov#`。

**限制**：这是可解析的序列化，不等价于已签名发布的 nanopublication；正式发布需另加密钥签名与
trusty URI。
