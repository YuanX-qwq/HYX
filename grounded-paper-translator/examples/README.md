# 示例（example，不是正式案例结果）

本目录是**最小调用示例**，用于说明输入、调用方式与输出形态。所有产物都由本 Skill 在
`paper.example.txt`（自写短文，非真实论文）上实际运行得到，并统一标注 `example: true`。

| 文件 | 说明 |
|---|---|
| `paper.example.txt` | 示例材料：标题 + 摘要 + 2 段正文（含数字、引用、图号、否定句） |
| `case.example.json` | 示例输入契约：`case_id`、`output_contract`（translation / verification） |
| `glossary.example.csv` | 示例术语表（4 条），`term_zh` 已填好并锁定 |
| `translations.example.jsonl` | 逐段译文（4 段），带 `notes` |
| `segments.example.json` | 切分结果（4 段，含 pid/page/bbox/sentences） |
| `result.example.json` | 组装后的结果（含双语段落、术语表、核验摘要、证据、变更记录） |
| `bilingual.example.md` | 段落级双语对照 |
| `verify.example.json` | 机械核验报告（0 FAIL / 0 WARN） |

## 调用方式

```bash
S=path/to/grounded-paper-translator
python3 $S/scripts/segment.py --pdf $S/examples/paper.example.txt \
  --out work/segments.json --md work/segments.md \
  --todo work/translate.todo.jsonl --scope work/scope.json
python3 $S/scripts/gloss.py lock --glossary $S/examples/glossary.example.csv \
  --segments work/segments.json --out work/glossary.lock.json
cp $S/examples/translations.example.jsonl work/translations.jsonl
python3 $S/scripts/verify.py --segments work/segments.json --translations work/translations.jsonl \
  --glossary work/glossary.lock.json --scope work/scope.json --out work/verify_report.json
python3 $S/scripts/assemble.py --segments work/segments.json --translations work/translations.jsonl \
  --glossary work/glossary.lock.json --scope work/scope.json --verify work/verify_report.json \
  --case $S/examples/case.example.json --out-dir output/
```

示意输出（节选，完整内容见 `result.example.json`）：

```json
{
  "case_id": "example-translation-001",
  "status": "success",
  "result": {
    "title": {"source": "Example: A calibration protocol ...", "translation": "示例：低温输运测量的一种校准流程"},
    "bilingual_paragraphs": [
      {"pid": "P0002", "page": 1, "kind": "abstract",
       "source": "We describe a calibration protocol ... 0.5%.",
       "translation": "我们描述一种用于 1.5 K 至 300 K 之间四端输运测量的校准流程……报告不确定度为 0.5%。",
       "status": "translated"}
    ],
    "metrics": {"coverage": 1.0, "glossary_terms_locked": 4, "verification_fail": 0}
  }
}
```

> 示例仅用于说明接口与输出形态，不代表任何正式案例的答案或评分。
