# grounded-paper-translator

科研文献英译中 Skill：**术语先锁定、段落带锚点、译文机械核验**。  
输入一篇英文论文（PDF / TXT / MD），输出段落级双语对照、锁定术语表、核验报告与 `result.json`。

本目录既是 Skill 本体（可被 Agent 直接加载），也是提交材料（说明、脚本、词表、示例、自测）。

## 1. 安装与依赖

```bash
# 作为 Skill 安装（复制目录即可，无需构建）
cp -r grounded-paper-translator ~/.dsh/skills/            # 本地
# 评测环境：平台会把本目录安装到 /skills/weekly-skill
```

- Python 3.8+，脚本只依赖标准库。
- PDF 文本后端按顺序自动尝试：`PyMuPDF` → `pdfplumber` → `pdftotext -bbox-layout`。三者都没有时，用平台 `pdf-text-tool` 取文本后以 `--backend text` 输入 `.txt`。
- 无需网络、无需 GPU；同一输入重复运行结果一致（无随机数）。

## 2. 快速开始

```bash
export SKILL_DIR=$PWD/grounded-paper-translator

# 1) 切分：段落 + 页码锚点 + 待译清单
python3 $SKILL_DIR/scripts/segment.py --pdf paper.pdf \
  --out work/segments.json --md work/segments.md \
  --todo work/translate.todo.jsonl --scope work/scope.json

# 2) 抽术语 → 填 term_zh → 锁定
python3 $SKILL_DIR/scripts/gloss.py extract --segments work/segments.json \
  --out work/glossary.candidates.csv
cp work/glossary.candidates.csv work/glossary.csv     # 编辑 term_zh 列
python3 $SKILL_DIR/scripts/gloss.py lock --glossary work/glossary.csv \
  --segments work/segments.json --out work/glossary.lock.json

# 3) 按 segments.md 逐段翻译，写入 work/translations.jsonl
#    {"pid":"P0007","zh":"……","notes":"术语选择/句式处理"}

# 4) 机械核验（FAIL=0 才进入组装）
python3 $SKILL_DIR/scripts/verify.py --segments work/segments.json \
  --translations work/translations.jsonl --glossary work/glossary.lock.json \
  --scope work/scope.json --out work/verify_report.json

# 5) 组装交付物
python3 $SKILL_DIR/scripts/assemble.py --segments work/segments.json \
  --translations work/translations.jsonl --glossary work/glossary.lock.json \
  --scope work/scope.json --verify work/verify_report.json \
  --case input/case.json --out-dir output/
```

## 3. 输入 / 输出

| 输入 | 说明 |
|---|---|
| `--pdf` | 论文 PDF，或已抽好的 `.txt/.md`（按空行分段） |
| `case.json`（可选） | 含 `case_id`、`output_contract`；组装时把契约字段并入 `result` |
| `translations.jsonl` | 每行 `{"pid","zh","notes"?, "uncertainty"?}`，pid 必须来自 `segments.json` |

| 输出 | 说明 |
|---|---|
| `result.json` | `case_id / status / result{title,abstract,glossary,bilingual_paragraphs,metrics,verification,scope} / coverage / evidence / uncertainty / sources / change_log` |
| `bilingual.md` / `bilingual.csv` | 段落级双语对照，含 pid、页码、章节、原文、译文 |
| `glossary.csv` | 可复用术语表 |
| `verify_report.json` | 逐条问题（pid + 检查项 + 严重度 + 原文/译文片段）与统计指标 |

## 4. 适用范围与限制

**适用**：英文科研论文（STEM 优先）、有文字层、单栏/双栏/多栏、含公式与图注、需要证据定位与术语一致性的场景。

**限制**：

1. 只做英译中；中译英、文学翻译不适用。
2. 纯扫描件需先 OCR；OCR 质量差时只能给 `partial` 并标注不可读页。
3. 图内文字（坐标轴、图例）按结构元素保留，不翻译。
4. 参考文献表保留原文，不翻译（避免编号与作者名失真）。
5. 显示公式按记号保留，译文中以文字衔接；不重排公式版式。
6. 核验是启发式规则：`WARN` 可能是假阳性（如“未极化”对应 unpolarized），需人工确认后放行；`FAIL` 默认必须修或明确记入 `uncertainty`。
7. 术语译名由译者（Agent）确定，脚本只保证“同一术语始终同一译名”，不保证译名本身最优。

## 5. 失败处理

| 情况 | 行为 |
|---|---|
| 加密 PDF | 直接失败，写明“需要口令”，不尝试破解 |
| 无文字层 | 提示用平台 `ocr-tool` 转文本后按 `.txt` 输入；不可用则 `failed` |
| 材料缺失 / 路径错误 | `failed`，`change_log` 记录实际查找过的路径 |
| 部分段落无法翻译 | `partial`，`uncertainty` 列出 pid 与原因，`status_note` 说明接管位置 |
| 核验 FAIL 无法修复 | `partial`，FAIL 条目全部进 `uncertainty`，不静默通过 |

## 6. 目录结构

```
grounded-paper-translator/
├── SKILL.md              # Skill 本体：触发条件、工作流、铁律、异常矩阵
├── README.md             # 本文件：安装、用法、输入输出、限制
├── METHOD.md             # 方法说明、指标定义、实测结果、对比协议
├── scripts/
│   ├── pdfwords.py       # PDF/TXT → 行（bbox/字号/旋转）
│   ├── layout.py         # XY-cut 阅读顺序 + 段落重建 + 连字符处理
│   ├── segment.py        # 段落切分 → segments/todo/scope
│   ├── gloss.py          # 术语候选、锁定、统计
│   ├── verify.py         # 13 类机械核验
│   └── assemble.py       # 组装 result.json + 双语对照
├── resources/
│   ├── glossary.seed.csv # 通用科研术语种子（120+ 条，可扩充）
│   ├── conventions.md    # 段号/标注/双语对照约定
│   ├── prompt-translate.md
│   └── prompt-selfcheck.md
├── schemas/              # segments / glossary / result 的 JSON Schema
├── examples/             # 最小调用示例（全部标 example，不是正式结果）
├── demo/                 # 真实论文的完整运行产物（arXiv:1605.01735v1）
└── tests/selftest.py     # 合成 + 真实 PDF 自测（含负例）
```

## 7. 版本与来源

- 版本：1.0（2026-11）
- 术语种子：自建通用科研词表（见 `resources/glossary.seed.csv`），可替换为学科词表。
- 示例论文：Carrasquilla & Melko, *Machine learning phases of matter*, arXiv:1605.01735v1（公开预印本，仅用于演示流程）。
