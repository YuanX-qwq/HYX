---
name: grounded-paper-translator
description: "科研文献英译中 Skill：把 PDF/文本切成带页码锚点的段落，先抽术语并锁定译名，再逐段翻译，最后用脚本机械核验数字、单位、引用、图表编号、公式符号、否定与限定是否保留，输出段落级双语对照与可直接复核的 result.json。当输入是 /input/case.json + /input/task.md、要求“文献翻译/全文翻译/双语对照/术语一致/译文核验”，或需要把论文译成中文并保留证据定位时触发。"
---

# 文献翻译：术语锁定 + 段落锚定 + 机械核验（grounded-paper-translator）

把一篇英文科研文献译成中文，并让每一段译文都能**回到原文的页码与区块**、每一个术语都**受同一份术语表约束**、每一处数字/单位/引用/公式都**被脚本核对过**。

四条硬承诺（对应题目四个考察点）：

1. **术语稳**：术语表是文件（`glossary.csv` → `glossary.lock.json`），不是提示词；`verify.py` 逐段回扫，译名不一致直接 FAIL 并给出段号。
2. **段落全**：段落切分带稳定 `pid`（P0001…）与 `page/bbox/section`；范围内缺段、重复段、空译由脚本检出，覆盖率写进结果。
3. **关系准**：数字、单位、文献编号、图表/公式编号、希腊字母与数学符号、否定词、限定/情态词逐项比对；丢失即 FAIL/WARN。
4. **可核验**：`result.json` 的每段含原文、译文、页码、区块坐标、译注与不确定标注；核验报告列出每条问题及人工接管位置。

---

## 适用范围

- **输入**：有文字层的英文科研 PDF（单栏/双栏/多栏、含公式、图注、参考文献），或已抽好的 `.txt/.md`；`/input/case.json` 给出 `case_id` 与 `output_contract`，`/input/task.md` 给出任务边界与翻译范围。
- **输出语言**：英文 → 简体中文（zh-CN）。中文文献转英文、文学翻译不在范围内。
- **不适用 / 降级**：
  - 加密 PDF 且需口令 → 状态 `failed`，写明原因，不猜内容。
  - 纯扫描件无文字层 → 先用平台 `ocr-tool` 转成文本，保存为 `.txt` 后按文本输入（本 Skill 不自带 OCR）；OCR 不可用时状态 `failed` 并说明原因，不猜内容。
  - 图内文字（坐标轴、图例）按结构元素识别，标 `figure-label`，不翻译、不混入正文。
  - 参考文献表保留原文（`reference`），不翻译、不改编号。

## 运行时

- `SKILL_DIR` = 本 SKILL.md 所在目录（评测环境为 `/skills/weekly-skill`）。
- Python 3.8+，脚本仅用标准库；PDF 后端按 `PyMuPDF → pdfplumber → pdftotext -bbox-layout` 自动降级，都不可用时用平台 `pdf-text-tool` 取文本后按 `--backend text` 处理。
- 所有中间产物写 `/app/work/`，交付物写 `/app/output/`。
- 预算纪律（评测 64 次模型请求 / 900 秒 / 单响应 16384 tokens）：切分与核验各只跑一次；翻译按 5–8 段一批；`verify.py` 一次给全部问题，按 pid 定点重修，不整篇重译。

---

## 工作流（严格按序）

### 第 0 步 — 读输入，定范围（1–2 次请求）

1. 读 `/input/case.json`：记录 `case_id`、`output_contract`（结果必须覆盖其全部字段）、材料路径。
2. 读 `/input/task.md`：确认翻译范围（全文 / 指定章节 / 摘要+正文）、目标语言、是否要求双语对照与术语表。
3. 定位材料（PDF/TXT/MD），记下文件名与页数；材料缺失或路径错误 → 状态 `failed`，写清原因，不编造。

### 第 1 步 — 切分（1 次命令）

```bash
mkdir -p /app/work /app/output
python3 "$SKILL_DIR/scripts/segment.py" --pdf "<材料>" \
  --out /app/work/segments.json --md /app/work/segments.md \
  --todo /app/work/translate.todo.jsonl --scope /app/work/scope.json
```

产出：

- `segments.json`：阅读顺序的段落单元，每段含 `pid / kind / section / page / bbox / text / sentences / words`。
- `segments.md`：同一内容的可读版（每段带 pid、页码、类型），供你按节阅读。
- `translate.todo.jsonl`：待译清单（`{"pid","source","zh":""}`），`zh` 由你填写。
- `scope.json`：默认翻译范围（全部可译段）+ 逐字保留段（公式、参考文献、图内文字、页眉页脚）。

`kind` 取值：`title/abstract/heading/body/caption/table/footnote`（可译），`equation/reference/authors/figure-label/fragment/header/footer/margin`（逐字保留）。

**范围收窄**：若 task.md 只要求某些章节，编辑 `scope.json` 的 `pids`（保留其余段作为 `verbatim` 证据），并在最终 `result.scope` 说明；覆盖率按 `scope.pids` 计算。

### 第 2 步 — 抽术语并锁定（1–2 次命令 + 1 次填写）

```bash
python3 "$SKILL_DIR/scripts/gloss.py" extract --segments /app/work/segments.json \
  --out /app/work/glossary.candidates.csv --max-terms 120
```

打开候选表，按下列规则填写 `term_zh`（保留 `term_en/category/variants` 列）：

- 只用领域标准译名；同一英文词只允许一个中文译名。
- 缩写、基因名、软件名可保留原文（如 `CNN`、`TensorFlow`、`t-SNE`）。
- 拿不准的译名不写；该词条留空并在结果 `uncertainty` 记一条 `term-unconfirmed`。
- 会互相包含的词条（如 `parameter` 与 `order parameter`）只锁长词条，避免自相矛盾。

```bash
python3 "$SKILL_DIR/scripts/gloss.py" lock --glossary /app/work/glossary.csv \
  --segments /app/work/segments.json --out /app/work/glossary.lock.json
```

`locked=true` 才继续；有 `duplicate term_en` / 同一译名对应两个词条时先修表。锁定后的术语表在后续翻译中**不得擅自更换**。

### 第 3 步 — 逐段翻译（主要请求预算）

按 `segments.md` 的段落顺序，分批（每批 5–8 段）写入 `/app/work/translations.jsonl`，每行一个对象：

```json
{"pid": "P0012", "kind": "body", "zh": "……中文译文……", "notes": "该段关键译法/术语选择", "uncertainty": "（可选）不确定之处"}
```

翻译铁律：

1. **一段一译**：不合并、不拆分段；原文段内公式与上标保留原记号，译文中用中文叙述衔接。
2. **术语锁定**：`glossary.lock.json` 里的词，译文必须出现对应中文（含 `variants` 中的写法）。
3. **数字与单位逐字保留**：`94%`、`2 × 16 × 16`、`L = 40`、`T = 0`、`≈ 3.640957` 一律不改写、不四舍五入。
4. **引用标记原样**：`[3]`、`[1, 7]`、`[9, 10]`、`[12-17]` 原样保留，不改编号、不删。
5. **交叉引用本地化**：`Figure 3` → `图 3`、`Table I` → `表 I`、`Eq. (A1)` → `式 (A1)`、`Section 2` → `第 2 节`，编号不变。
6. **否定与限定不丢**：`not / without / fail to / cannot` 与 `only / approximately / at least` 必须落成中文否定词与限定词（不、未、无法、仅、约、至少）。
7. **不确定就标注**：读不清、术语存疑、原文残缺 → 译文中保留 `[待确认]` 并在该行 `uncertainty` 写明；不得猜测补写。
8. 参考文献段不必翻译（保持 `reference`），也不要把参考文献混进正文。

### 第 4 步 — 机械核验与定点返修（1 次命令 + 按需返修）

```bash
python3 "$SKILL_DIR/scripts/verify.py" \
  --segments /app/work/segments.json --translations /app/work/translations.jsonl \
  --glossary /app/work/glossary.lock.json --scope /app/work/scope.json \
  --out /app/work/verify_report.json
```

- 输出：覆盖率、术语一致率、FAIL/WARN 计数、逐条问题（pid + 检查项 + 原文/译文片段）。
- 检查项：`coverage / numbers / units / citations / cross_refs / symbols / negation / hedging / glossary / length / sentences / untranslated / placeholder`。
- **只改被点名的段**：按 `issues[].pid` 重写该段译文，重跑 `verify.py`，直到 FAIL=0 或每条 FAIL 都进入 `uncertainty` 并说明原因。
- 覆盖率 <1 时，缺失段要么补译，要么在 `scope`/`uncertainty` 中如实标注，不能悄悄丢段。

### 第 5 步 — 组装交付（1 次命令）

```bash
python3 "$SKILL_DIR/scripts/assemble.py" \
  --segments /app/work/segments.json --translations /app/work/translations.jsonl \
  --glossary /app/work/glossary.lock.json --scope /app/work/scope.json \
  --verify /app/work/verify_report.json --case /input/case.json \
  --out-dir /app/output
```

产出（全部为 UTF-8 文本）：

| 文件 | 内容 |
|---|---|
| `/app/output/result.json` | `case_id`、`status`、`result{title, abstract, glossary, bilingual_paragraphs, metrics, verification, scope}`、`coverage`、`evidence`、`uncertainty`、`sources`、`change_log`；`output_contract` 声明的字段一并覆盖（无法填写的置 `null` 并进 `uncertainty`） |
| `/app/output/bilingual.md` | 段落级双语对照（pid + 页码 + 原文 + 译文） |
| `/app/output/bilingual.csv` | 同上，便于表格复核 |
| `/app/output/glossary.csv` | 锁定术语表（可复用） |

`status` 规则：`success` = 范围内全部译完且 FAIL=0；`partial` = 有缺段或存在 FAIL（`status_note` 与 `uncertainty` 写明限制与接管位置）；`failed` = 无任何译文（写明原因）。

---

## 异常处理矩阵

| 异常 | 识别方式 | 处置 | 状态 |
|---|---|---|---|
| PDF 加密需口令 | `segment.py` 返回 `encrypted-pdf` / 空口令失败 | 说明需口令，不尝试破解 | `failed` |
| 无文字层（扫描件） | `no-text-layer` | 用平台 `ocr-tool` 转成 `.txt` 后按文本输入；OCR 质量差时标 `partial` 并列出不可读页 | `partial`/`failed` |
| 页眉页脚混入正文 | `kind=header/footer` 且 `n_words` 很小 | 由切分脚本自动分离；仍混入时在 `segments.md` 手工核对后调整 `scope.json` | — |
| 双栏串栏 | 段落跨左右栏、句子断裂 | 切分脚本用 XY-cut 先分栏；残留时可对嫌疑段 `pid` 用 `--min-words` 复核，必要时在 `notes` 记 `layout-risk` | `partial` |
| 公式被拆成多段 | `kind=equation` 段极短且带数学符号 | 公式段逐字保留，不翻译；译文在相邻正文段内衔接，`notes` 说明 | — |
| 图内文字 | `kind=figure-label`（位于图像/矢量图区域） | 不翻译，作为结构元素保留 | — |
| 术语表冲突 | `gloss.py lock` 报 `duplicate` / 同译名 | 修表后重锁；不可强行锁定 | — |
| 译文超长/缺句 | `verify.py` 的 `length`/`sentences` WARN | 回看原文，补全缺句；确属中文表达更长为正常时在 `notes` 说明 | — |
| 参考文献无法解析 | 参考文献段格式混乱 | 保留原文不译，`reference` 段不参与覆盖率 | — |
| 重复运行 | — | 全部输出确定性（无随机数）；重跑前可清空 `/app/work/*.json`，pid 由页序重算 | — |

## 自查清单（提交前）

- [ ] `result.json` 含 `case_id` 与 `output_contract` 全部字段
- [ ] `coverage.rate == 1.0`，或缺失 pid 已列入 `uncertainty` 并写明原因
- [ ] `verify.py` FAIL = 0；WARN 均有 `notes` 解释
- [ ] 术语一致率 = 1.0；术语表已导出 `glossary.csv`
- [ ] 每段有 `pid/page/bbox`，`bilingual.md` 可直接对照原文页
- [ ] 未翻译的公式/参考文献/图内文字标为 `verbatim`，未混入正文
- [ ] 示例产物（`examples/`）与本案例产物分开，示例均标 `example: true`

## 脚本速查

| 脚本 | 作用 | 关键参数 |
|---|---|---|
| `scripts/pdfwords.py` | PDF/TXT → 行（文本 + bbox + 字号） | `--pdf --out [--backend]` |
| `scripts/layout.py` | XY-cut 阅读顺序 + 段落重建（被 `segment.py` 调用） | 库函数 |
| `scripts/segment.py` | 段落切分 → `segments.json/md`、todo、scope | `--pdf --out [--md --todo --scope --backend --min-words]` |
| `scripts/gloss.py` | 术语候选抽取 / 锁定 / 统计 | `extract`、`lock`、`stats` |
| `scripts/verify.py` | 13 类机械核验 + 指标 | `--segments --translations --glossary --scope --out` |
| `scripts/assemble.py` | 组装 `result.json` + 双语对照 + 术语表 | `--segments --translations --glossary --scope --verify --case --out-dir` |
| `tests/selftest.py` | 合成样例自测（含负例：丢数字、丢否定、术语漂移、缺段、引用改号） | `--workdir DIR [--real-pdf PATH]` |
