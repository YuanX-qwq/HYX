# 引用管理规则表

## 一、去重判据（按优先级）

| 规则 | 触发条件 | 保留哪条 | 备注 |
|---|---|---|---|
| `R-DOI` | DOI 忽略大小写后相同 | 字段更全者 | 最硬的证据，无需别的条件 |
| `R-TITLE-NORM` | 题名去标点/空白/大小写后完全相同 | 正式发表版 | 仍需作者姓氏一致 |
| `R-TITLE-FUZZY` | 题名词元交集 ≥3 且 Jaccard ≥0.75 | 正式发表版 | 处理副标题、连字符差异 |
| `R-PREPRINT` | 同题，一条在 arXiv/bioRxiv 等预印本库 | 正式发表版 | 合并后 `merged_from` 记两条 |
| `R-BILINGUAL` | 同题中英文各一且 DOI/刊名同源 | 待人工复核 | 语言不同只登记不自动删 |

**不合并护栏**（任一命中即放弃合并）：
1. 第一作者姓氏不同；
2. 年份差 >1 年且不同刊；
3. 题名词元交集 <3；
4. 一条有 DOI、另一条 DOI 不同（同题为巧合时）；
5. 只是刊名缩写相同而题名不同。

## 二、样式字段映射

| 字段 | GB/T 7714-2015 | APA 7 |
|---|---|---|
| 作者 | 姓全大写 + 名首字母，≤3 全列，>3 加 `, et al`（中文加 `, 等`） | `Last, I. I., & Last, I.`，≤20 全列 |
| 题名 | 原样 + `[文献类型标识]` 后接 `.` | 句首大写，`Title.` |
| 刊名 | 全称, 年, 卷(期): 起止页. | *Journal*, volume(issue), pages. |
| 文献类型 | J / M / C / D / EB/OL / P / R / S | 不标注类型 |
| DOI | `DOI: 10.xxxx/...` | `https://doi.org/10.xxxx/...` |

## 三、论断—文献匹配

1. 词干化：英文取前 5 字符；中文按二字切分，并用概念桥映射到英文概念（掺杂→doping、催化→cataly、稳定→stability、晶格→lattice、产率→yield、衍射→diffraction……）。
2. 得分 = 交集词干数 / max(3, min(文献词干数, 8))。
3. `strong`：交集 ≥2 且得分 ≥0.28；`weak`：有交集但未达阈值；`mismatch`：无交集；`dangling`：编号无对应条目。
4. `weak` 与 `mismatch` 一律进 `consistency_checks` 并在 `uncertainty` 说明，不自动改引用。

## 四、缺引用句识别（citation gap）

句长 ≥18 字符、无 `[n]` 标记，且满足任一：含带单位数值、含"表明/证明/显示/优于/提升/降低/高于/低于/达到/超过/显著"、含英文 `show/prove/confirm/demonstrate/increase/decrease`。命中即为 gap，需作者决定是否补引。

## 五、六项自查

- [ ] 每条 `citations[].claim_span` 能在稿件中逐字找到；
- [ ] `reference_list` 编号连续、与重排后正文一致；
- [ ] `dedup` 每条都有 `basis` 且 `kept_key` 存在于 `reference_list`；
- [ ] `consistency_checks` 覆盖所有正文引用点，无遗漏无臆造；
- [ ] `uncertainty` 写明 dangling、weak/mismatch、编造候选三类待确认项；
- [ ] `metadata.example_only` 与 `case_id` 正确，示例未冒充正式结果。

## 六、常见失败模式

| 现象 | 原因 | 处置 |
|---|---|---|
| 编号重排后图表注对不上 | 只重排正文与文献表 | 图表注引用一并扫；漏扫则报 `non_numeric_marker` |
| 两条不同文献被合并 | 题名相似但作者不同 | 护栏 1/2 生效，保留两条并记 `uncertainty` |
| 条目"看起来核验过" | 只做了形态检查 | 状态写 `verified_shape`，在线核验列入待办 |
| 中文论断全判 mismatch | 未启用概念桥 | 补 CONCEPT 映射或在 `uncertainty` 说明语言不匹配 |
