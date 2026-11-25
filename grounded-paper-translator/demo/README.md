# demo — 真实论文完整运行产物

**材料**：Carrasquilla & Melko, *Machine learning phases of matter*, arXiv:1605.01735v1（18 页，含图版页、公式与参考文献）。
**用途**：证明整条流水线在真实 PDF 上可运行、产物可复核；本目录不是示例，也不是平台正式案例。

## 实测数据

| 项目 | 数值 |
|---|---|
| 页数 / 抽取行数 | 18 / 1101 |
| 段落单元 | 118 |
| 可译段（scope） | 43（标题 1、摘要 1、小标题 4、正文 30、图注 9、脚注 1） |
| 逐字保留 | 公式 16、参考文献 4、图内文字 16、页眉页脚/边注 29、碎片 6 |
| 翻译词量 | 4832 词 |
| 覆盖率 | 43/43 = 100% |
| 锁定术语 | 37 条；35 条在文中出现，术语一致率 100%（按出现段计） |
| 机械核验 | FAIL 0；WARN 3（2 条公式行的句数启发式、1 条“是否”类否定启发式，均在 `verify_report.json` 中可见） |

## 文件

| 文件 | 内容 |
|---|---|
| `segments.json` | 118 段的结构化文档模型（pid、页码、bbox、章节、类型、原文、句子） |
| `glossary.lock.json` / `glossary.csv` | 锁定术语表（37 条） |
| `translations.jsonl` | 43 段译文（含译注，未译段不在其中） |
| `verify_report.json` | 逐条核验问题、术语一致率、覆盖率 |
| `result.json` | 交付结果（`status=success`，含双语段落、指标、证据、变更记录） |
| `bilingual.md` / `bilingual.csv` | 段落级双语对照 |

## 复现命令

```bash
curl -L -o ml.pdf https://arxiv.org/pdf/1605.01735v1
S=path/to/grounded-paper-translator

python3 $S/scripts/segment.py --pdf ml.pdf --out work/segments.json \
  --md work/segments.md --todo work/translate.todo.jsonl --scope work/scope.json

python3 $S/scripts/gloss.py extract --segments work/segments.json --out work/cand.csv
# 依据 cand.csv 与领域知识填写 term_zh（本 demo 的成品见 glossary.csv）
python3 $S/scripts/gloss.py lock --glossary glossary.csv --segments work/segments.json \
  --out work/glossary.lock.json

# 逐段翻译（可用 resources/prompt-translate.md 的分批提示词），写入 work/translations.jsonl

python3 $S/scripts/verify.py --segments work/segments.json \
  --translations work/translations.jsonl --glossary work/glossary.lock.json \
  --scope work/scope.json --out work/verify_report.json
python3 $S/scripts/assemble.py --segments work/segments.json \
  --translations work/translations.jsonl --glossary work/glossary.lock.json \
  --scope work/scope.json --verify work/verify_report.json --out-dir output/
```

> 说明：不同 PDF 后端（pymupdf / pdfplumber / pdftotext）得到的行框略有差异，段落切分可能相差 ±2 段；pid 在同一后端、同一文件下稳定。`standalone` 复现时请固定后端（`--backend pymupdf` 或 `--backend pdftotext`）。
