# pdf-literature-parser — 科研 PDF 文献解析 Skill

把科研 PDF 解析成**可复核的结构化结果**：文字逐字保真、多栏阅读顺序正确、表格/章节/公式拆得清，每段文字、每张表格都能指回原文页码与区块；读不出的部分如实标注，不靠猜补齐。

- 入口：[SKILL.md](SKILL.md)（Agent 加载后照此执行）
- 方法：[METHOD.md](METHOD.md)（关键方法、创新点、与基础 Agent 的差异、已知边界）
- 接口：[schemas/document.schema.json](schemas/document.schema.json)、[schemas/result.schema.json](schemas/result.schema.json)
- 示例：[examples/](examples/)（合成示例，**不是**任何正式案例结果）
- 自测：[tests/selftest.py](tests/selftest.py)

## 依赖与后端

| 组件 | 必需 | 说明 |
|---|---|---|
| Python ≥ 3.8 | 必需 | 核心仅标准库 |
| PyMuPDF (`pymupdf`) | 可选 | 首选后端：词/span 坐标 + 字号 + 上下标标志 |
| pdfplumber | 可选 | 次选后端 |
| poppler (`pdftotext`/`pdftoppm`) | 可选 | 第三后端（无 Python 依赖） |
| tesseract（+语言包） | 可选 | 无文字层页面 OCR（`--ocr`） |
| 平台工具 `pdf-text-tool`/`pdf-render-tool`/`ocr-tool` | 可选 | 以上全缺时由 Agent 手动组合使用 |

安装（本地验证用）：

```bash
python3 -m pip install pymupdf pdfplumber   # 可选
```

版本/来源：脚本随本目录提交（见各文件头）；PyMuPDF/pdfplumber 为 PyPI 公开包；无其他隐藏依赖；不依赖任何个人文件或手工操作。

## 最小调用（完整流程）

```bash
# 0) 输入：/input/case.json + /input/task.md + 材料 PDF（路径从 case.json 读）
# 1) 诊断
python3 scripts/pdfprobe.py --pdf paper.pdf --out work/probe.json
# 2) 解析
python3 scripts/parse_document.py --pdf paper.pdf --work work \
  --out work/document.json --md work/document.md [--ocr] [--render]
# 3) Agent 依据 document.md 作答，写 work/answers.json（见 SKILL.md 第 3 步）
# 4) 核验 + 组装
python3 scripts/evidence.py check   --document work/document.json --answers work/answers.json --out work/quote_check.json
python3 scripts/make_result.py      --case /input/case.json --answers work/answers.json \
  --document work/document.json --probe work/probe.json --out output/result.json
python3 scripts/evidence.py verify  --document work/document.json --result output/result.json --out work/verify_report.json
```

示意输出见 [examples/result.example.json](examples/result.example.json)（**示例**，synthetic，不冒充正式案例结果）。

## 输入输出

| 项 | 内容 |
|---|---|
| 输入 | `case.json`（case_id + output_contract）、`task.md`（任务与证据范围）、科研 PDF |
| 中间 | `probe.json`（诊断）、`document.json`（文档模型）、`document.md`（阅读顺序渲染）、`answers.json`（Agent 答案）、`quote_check.json` / `verify_report.json`（核验） |
| 输出 | `result.json`：case_id + output_contract 全部字段 + status + evidence_check + uncertainty + unreported + sources + change_log |

## 适用范围与限制

- 适用：有文字层的科研论文/报告 PDF（单栏、双栏、三栏），含表格、公式、脚注、参考文献；英文/中文；重复运行确定性输出。
- 已知边界（如实报告，不静默降级）：
  - 加密且需口令的 PDF：拒答并说明；
  - 无文字层且无 OCR：对应页 `unreadable`；
  - 跨栏巨型表格：按栏拆成两段输出，题注给出定位（不猜合并）；
  - 表格合并单元格：输出网格以空串表示缺格，合并关系以 bbox 佐证；
  - 版式罕见的文档（如海报式排版）：栏检测置信度低时按单栏输出并在 warnings 说明。
- 机械解析只保证"结构正确 + 逐字保真"，不判断科学含义；科学结论仍需人复核。

## 失败处理与自查

- 失败即写 warnings/status，不抛异常掩盖：解析错误在 `PARSE_ERROR` 中带原因；部分页失败不影响其余页。
- 自查：`python3 tests/selftest.py`（fixture 15 项必跑；环境有 LaTeX + 任一侧后端时另跑 9 项真实 PDF 端到端，退出码 0 = 全过）。
- 人工接管位置：任何 `unverified` 证据、`unreadable` 页、`image-table` 表格都在 result.json 的 uncertainty/change_log 中标明页码与块 id。

## 版本与维护

- 版本：1.0.0（2026-11-25）
- 改动解析逻辑时重跑 `tests/selftest.py`；改动接口时同步 `schemas/` 与 SKILL.md 速查表。
- 反馈请附 case_id、出问题的块 id（`pNbM`）与 `quote_check.json` 片段。
