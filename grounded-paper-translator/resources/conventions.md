# 翻译与对照约定

## 1. 段号（pid）

- 段号形如 `P0007`，由 `segment.py` 按“页序 → 阅读顺序 → 段落”生成，是唯一键。
- 段号只增不改：翻译、核验、组装三个环节都引用同一 `pid`；不得自行重排或合并段号。
- 每段保留 `page`（物理页码）与 `bbox`（PDF 坐标，单位 pt，原点左上），用于回看原文。
- 跨页续段保留 `page_end`；引用时写 `p2–p4`。

## 2. 段落类型（kind）

| kind | 含义 | 是否翻译 |
|---|---|---|
| `title` / `abstract` / `heading` / `body` / `caption` / `footnote` | 标题、摘要、小标题、正文、图表题注、脚注 | 是 |
| `table` | 表体文字（能逐格取出时） | 是（保留数字与单位） |
| `equation` | 带编号或数学符号的公式块 | 否，逐字保留 |
| `reference` | 参考文献条目 | 否，逐字保留 |
| `figure-label` | 图像/矢量图内部文字（坐标轴、图例、子图字母） | 否 |
| `header` / `footer` / `margin` | 页眉、页脚、页码、水印、旋转边注 | 否 |
| `authors` | 作者与单位行 | 否（人名不音译） |
| `fragment` | 抽取碎片（< 9 词且无句末标点） | 否，登记备查 |

## 3. 译文写法

1. **数字与单位**：一律保留阿拉伯数字与原单位，不改写、不换算、不四舍五入；范围与误差用原文写法（`2–3`、`±0.5`、`≈ 3.640957`）。
2. **引用标记**：`[3]`、`[1, 7]`、`[9, 10]`、`[12-17]` 原样；不改编号、不改成“文献 3”。
3. **交叉引用**：`Figure 3` → `图 3`，`Fig. 1(A)` → `图 1(A)`，`Table I` → `表 I`，`Eq. (A1)` → `式 (A1)`，`Section 2` → `第 2 节`；编号不变。
4. **公式记号**：希腊字母、上下标、求和/积分符号按原文保留（`σz i`、`ϵ`、`∞`、`≪`）；不把 `ϵ` 改写成 `epsilon`。
5. **否定与限定**：`not / without / fail to / cannot` → 不、未、无法、不能；`only / at least / approximately` → 仅、至少、约。不得省略。
6. **术语**：使用 `glossary.lock.json` 的锁定译名；首次出现可在括号内附英文原词（`序参量（order parameter）`），后续不再重复。

## 4. 不确定与未译标注

| 标记 | 用于 | 必填字段 |
|---|---|---|
| `[待确认]` | 术语存疑、原文残缺、读不清 | 该段 `uncertainty` 写明原因与建议 |
| `[未译]` | 范围内未提供译文（不得静默缺失） | `uncertainty` 中 `kind=not-translated` |
| `[原文如此]` | 原文拼写/语法错误，按原样理解 | 可选，写入 `notes` |

`verify.py` 会检查 `[待确认]`/TODO 是否在 `uncertainty` 中说明；只写标记不说明会被记为 WARN。

## 5. 双语对照输出

`bilingual.md` 每段固定四行：

```
## P0012 · p4 · body · 2. Methods

**EN** <原文逐字>
**ZH** <中文译文>
```

`bilingual.csv` 列：`pid,page,kind,section,source,translation,status`。  
`result.json` 的 `result.bilingual_paragraphs[]` 额外包含 `translation_notes`、`uncertainty`、`sentences`，供逐段复核与二次修订。
