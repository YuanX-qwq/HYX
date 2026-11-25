---
name: pdf-literature-parser
description: "科研 PDF 文献解析与问答 Skill。把论文 PDF 解析成带证据锚点的结构化文档模型（多栏阅读顺序、章节层级、表格网格、公式编号、参考文献、页眉页脚、OCR 回退），并据此完成解析、翻译、问答、提取、核验、知识结构化任务，每个结论附页码/区块/引文依据。Trigger on: '阅读这篇文献', 'parse this paper', '从 PDF 里提取', '按材料回答问题并给出依据', '文献文档解析', /input/case.json 与 /input/task.md 出现时。"
---

# PDF 文献解析 Skill（pdf-literature-parser）

把科研 PDF 解析成**可复核的结构化结果**：文字逐字保真、多栏顺序正确、表格/章节/公式拆得清、每段每表都能指回原文页码与区块，读不出的部分如实标注。

四个硬性承诺（对应题目四个考察点）：

1. **提得全**：正文、图表题注、脚注、参考文献逐字提取；页眉页脚单独归档，不混进正文。
2. **排得对**：双栏/多栏按 band-walk 阅读顺序输出，不串栏、不错行、不把相邻段拼成一句。
3. **拆得清**：章节层级、表格行列与单元格归属、公式编号与上下标/希腊字母还原为可继续处理的结构。
4. **核得回**：每个结构元素带 `{page, bbox, zone, source}` 锚点；每句答案附逐字引文，由脚本机械核验；读不出/未报告/无法判断如实标注，不靠猜补齐。

---

## 适用与不适用

- **适用**：有文字层的科研 PDF（单栏/双栏/三栏、含表格、公式、脚注、参考文献）；部分页无文字层时走 OCR 回退；任务类型包括解析、翻译、问答、提取、核验、知识结构化。
- **不适用/降级**：加密且需口令的 PDF（拒绝并说明原因）；纯图片型表格（输出定位 + 标注"image-table"，由 Agent 对照渲染图人工转录并标 `source: manual`）；整本无法打开或损坏的 PDF（报告失败原因）。

## 运行时环境

- `SKILL_DIR`：本 SKILL.md 所在目录（评测环境为 `/skills/weekly-skill`）。所有脚本在 `$SKILL_DIR/scripts/` 下。
- 若不知道路径：`find / -name pdfprobe.py 2>/dev/null | head -1` 得到 `scripts/` 所在目录。
- Python：`python3`（脚本仅用标准库；可选后端 PyMuPDF/pdfplumber，缺省自动降级到 `pdftotext`）。
- 平台工具（脚本后端缺失时的替代）：`pdf-text-tool`、`pdf-render-tool`、`ocr-tool`、`latex-compiler`、`scientific-python`。

## 预算纪律（评测限额：64 次模型请求 / 900 秒 / 每响应 16384 tokens）

- 解析只跑一次并缓存到 `/app/work/document.json`；不要反复重解析。
- 阅读用 `document.md`（已按阅读顺序渲染），按节分块读，不要重复读同一块。
- 证据检索批量交给 `evidence.py`（一次脚本调用可查多条引文）。
- 规划请求数 ≤ 40：读输入 2 + probe 1 + parse 1 + 读 document.md 分块 ≤ 12 + 证据检索 2 + 写答案 2 + 组装 1 + 核验 1 + 收尾修补 ≤ 10。

---

## 工作流（严格按序执行）

### 第 0 步 — 读输入，识别边界

1. 读 `/input/case.json`：记录 `case_id`、`output_contract`（答案必须覆盖其全部字段）、材料文件路径。
2. 读 `/input/task.md`：判断任务类型（解析 / 翻译 / 问答 / 提取 / 核验 / 知识结构化）与证据范围要求。
3. 定位材料 PDF（`/input/` 下，可能是子目录；用文件名匹配，不要靠标签猜内容）。
4. 材料缺失、路径错误：在结果中写明，状态用 `failed`/`unable`，不要编造文件。

### 第 1 步 — 诊断（probe）

```bash
mkdir -p /app/work /app/output
python3 "$SKILL_DIR/scripts/pdfprobe.py" --pdf "<PDF>" --out /app/work/probe.json
```

读 probe 结果，按下列矩阵决定后续路径：

| probe 现象 | 处置 |
|---|---|
| `needs_password=true` | 先试空口令解析；仍失败 → 状态 `refused`，说明"加密 PDF 需要口令"，输出到 result.json 后结束 |
| 某页 `no-text-layer` / `sparse-text` | parse 加 `--ocr --ocr-langs eng`（有中文页再试 `chi_sim`） |
| 某页 `mojibake` | 对该页用 `--render` 出 PNG，Agent 对照 PNG 人工复核并标注 |
| 打开失败 | 记录 `backend_errors` 到结果，状态 `failed` |

### 第 2 步 — 解析（parse）

```bash
python3 "$SKILL_DIR/scripts/parse_document.py" \
  --pdf "<PDF>" --work /app/work --out /app/work/document.json \
  --md /app/work/document.md [--ocr] [--render]
```

产出：

- `/app/work/document.json`：结构化文档模型（见 `schemas/document.schema.json`）。每块含 `id`（如 `p3b12`=第 3 页第 12 块）、`kind`、`text`（逐字）、`bbox`、`zone`、`page`。
- `/app/work/document.md`：按阅读顺序渲染的 Markdown，带 `[pNbM zone]` 锚点与 `{anchor:pNbM}` 标记。
- `/app/work/page-*.png`（`--render` 时）：逐页渲染图，用于复核表格/公式/乱码。

脚本无 Python 后端时：用平台 `pdf-text-tool` 取文本、`pdf-render-tool` 出图，把文本与坐标按 document.schema.json 手工整理为 document.json（标注 `backend: platform-tool`），流程不变。

### 第 3 步 — 阅读并完成任务

1. 分块读 `/app/work/document.md`（先读"结构索引"，再按任务范围读对应节）。
2. 按 task.md 要求完成任务（问答/翻译/提取/核验/知识结构化）。**铁律**：
   - 答案只依据 document.md / document.json 中的原文；引用必须逐字（多空格等保持原样）。
   - 每条关键结论写 `evidence`：`{"quote": "<原文逐字>", "page": N, "block_id": "pNbM", "zone": "...", "bbox": [...]}`。
   - 原文没有的 → 进 `unreported`；无法判断的 → 进 `uncertainty`（kind=`cannot-determine`）；材料冲突 → 进 `uncertainty`（kind=`conflict`，列双方位置）。**禁止把未报告写成事实。**
   - 表格按行列结构引用（行×列 + 块 id），不要抄成一段文字。
   - 公式按编号引用，符号用 Unicode 原样（² ³ 希腊字母不转写），上下标用 `^(...)` / `_(...)` 标注。
3. 需要定位某句原文时批量调用：
   ```bash
   python3 "$SKILL_DIR/scripts/evidence.py" locate --document /app/work/document.json --quote "<要找的句子>"
   ```
4. 把答案写成 `/app/work/answers.json`：
   ```json
   {"case_id": "<case_id>", "status": "success", "result": {…按 output_contract 字段…}, "unreported": [...], "uncertainty": [...]}
   ```
   `result` 内的每个答案条目带 `evidence` 列表。output_contract 的**全部字段**都要出现（没有内容填 `null` 并在 uncertainty 说明）。

### 第 4 步 — 机械核验 + 组装

```bash
python3 "$SKILL_DIR/scripts/evidence.py" check \
  --document /app/work/document.json --answers /app/work/answers.json --out /app/work/quote_check.json
python3 "$SKILL_DIR/scripts/make_result.py" \
  --case /input/case.json --answers /app/work/answers.json \
  --document /app/work/document.json --probe /app/work/probe.json \
  --out /app/output/result.json --change-log /app/work/change_log.json
python3 "$SKILL_DIR/scripts/evidence.py" verify \
  --document /app/work/document.json --result /app/output/result.json --out /app/work/verify_report.json
```

- `quote_check.json` 有 `unverified/mismatch` 时：修正引文或把该条移入 uncertainty，再重跑，直到全部 `verified` 或已在 uncertainty 中说明。
- 复制交付物到 `/app/output/`：`document.json`、`document.md`、`probe.json`、`verify_report.json`、页面 PNG（若有）。可编辑的 Office/图产物需真实渲染 PDF/PNG 预览（用 `office-renderer`）。

### 第 5 步 — 检查输出契约

确认 `/app/output/result.json`：

- 含 `case_id`、`status`（success/partial/failed/unable/refused）、`result`（覆盖 output_contract 全部字段）、`evidence_check`、`uncertainty`、`unreported`、`sources`、`change_log`。
- `status=partial` 时必须写清限制与可人工接管的位置（哪页哪块）。
- 保存 `/app/work/change_log.json`：每条为 `{"step": ..., "detail": ...}`，记录 probe→parse→answer→verify 的改动与异常。

---

## 脚本速查

| 脚本 | 作用 | 关键参数 |
|---|---|---|
| `scripts/pdfprobe.py` | 诊断（加密/文字层/乱码/字体） | `--pdf --out` |
| `scripts/parse_document.py` | 解析 PDF → document.json/.md | `--pdf --work --out [--md] [--ocr] [--ocr-langs] [--render] [--backend pymupdf\|pdfplumber\|pdftotext] [--max-pages]` |
| `scripts/evidence.py` | `locate` 检索引文 / `check` 核验 answers / `verify` 核验 result | 见工作流 |
| `scripts/make_result.py` | 组装 result.json（保留契约字段 + 状态 + 核验） | `--case --answers --document [--probe] --out [--change-log]` |
| `tests/selftest.py` | 自测（fixture 15 项；有 LaTeX+后端时另跑真实 PDF 9 项） | `--workdir DIR [--no-real-pdf]` |
| `schemas/*.json` | document/result 的 JSON Schema | — |

## 异常处理矩阵

| 异常 | 识别 | 处置 |
|---|---|---|
| 加密 PDF | probe `needs_password` | 空口令重试 → 仍失败 `refused` + 原因 |
| 无文字层扫描件 | probe `no-text-layer` | `--ocr`；tesseract 词级置信度进 lines；低置信词如实标注 `[?]` |
| OCR 不可用 | parse warnings `page-unreadable` | 该页状态 `unreadable`，结果中说明，不编造 |
| 图片型表格 | 表格区无词但 caption 在 | 输出 caption 定位 + `kind: image-table`；Agent 对照渲染图人工转录并标 `source: manual` |
| 乱码字体 | probe `mojibake` | `--render` 出图人工复核；块标注 `text-degraded` |
| 页码错乱 | 物理页与印刷页号不一致 | 全部用物理页码 + 保留 `label`（印刷页码）双字段 |
| 跨页续表 | 次页首表列数同 + 表头相似 | 自动合并为同一逻辑表（parts[] 记录各页块） |
| 重复运行 | — | 全部输出确定性（无随机），可安全重跑；先删旧 `/app/work/*.json` |

## 自查清单（交付前）

- [ ] result.json 含 case_id 与 output_contract 全部字段
- [ ] 每条关键结论都有 evidence（quote/page/block_id/bbox），且 `evidence.py verify` 全部 `verified`
- [ ] unreported / uncertainty 与 status 一致（partial/failed 时说明原因与接管位置）
- [ ] 页眉页脚未混入正文；阅读顺序按栏输出
- [ ] 示例与本案例产物分开；本案例 result.json 无 `synthetic` 标记
- [ ] `/app/output/` 下产物齐备（result.json、document.json、document.md、核验报告、预览图）
