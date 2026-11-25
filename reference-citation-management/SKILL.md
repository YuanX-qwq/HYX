---
name: reference-citation-management
description: "Manage citations and references: place citations at the claim that needs support, keep in-text numbering and the reference list synchronized after insert/delete/reorder, deduplicate records (bilingual titles, preprint vs published, database exports), convert between BibTeX/RIS/EndNote/CNKI and target styles (e.g. GB/T 7714-2015, APA), and verify source authenticity and claim-reference match. Use for citation placement, numbering update, dedup, format conversion and consistency checks."
---

# 写作04｜参考文献与引用管理

## 用途与触发条件

在 Bohrium Playground（Harbor 评测）环境中，对组织方给定的固定科研案例完成参考文献与引用管理任务：把引用挂到该挂的句子、把编号与文献表同步、把重复条目合并、按目标规范渲染、逐句核验"论断—文献"对应。
Skill 被安装到 `/skills/weekly-skill`，输入 `/input/case.json` 与 `task.md`，过程产物放 `/app/work`，最终结果放 `/app/output`。

**适用**：引用插入与定位；插入/删除/调序后的编号连锁更新与交叉引用同步；文献去重与条目归并；BibTeX/RIS/EndNote/CNKI 与 GB/T 7714-2015、APA 之间的转换与字段补齐；条目真实性与正文—文献一致性核验。
**不适用**：不预置答案，不解释题面未要求的科学结论，不编造运行日志、DOI 或测试成绩。

## 核心关注点

- **挂得对**：引用贴在真正需要来源支撑的论断后（数值断言、结论句、对比句），不是整段末尾；一句多引用逗号分开、连续编号用 `1-3` 压缩。
- **编得顺**：按正文首次出现重排，正文标记、文献表序号、图表注引用同源；编号连续、区间压缩、超范围标记报 dangling。
- **收得净**：DOI 相同、题名规范化后相同、预印本对正式版三类可合并；作者姓氏或年份差 >1 年且无同刊同题证据时不合并，宁可留着让人看。
- **对得上**：每条引用落到真实条目；中文论断与英文题名可比（概念桥），逐句给出 strong / weak / mismatch / dangling 与词重叠得分。

## 执行流程

1. **读取输入**：读 `/input/case.json` 与 `task.md`，确认目标规范、稿件范围、文献库格式与证据范围；`case_id` 原样保留。
2. **解析材料**：`parse` 自动识别 BibTeX / RIS / EndNote / CNKI 并输出结构化记录；字段缺失如实记下，不补造。
3. **去重核验**：`dedup` 给出合并组与判据（`R-DOI` / `R-TITLE-NORM` / `R-TITLE-FUZZY` / `R-PREPRINT` / `R-BILINGUAL`）；`verify` 标出 DOI 形态非法、缺年份/作者、占位题名。
4. **编号与定位**：`renumber` 按首次出现重排、压缩区间、报 dangling 与未被引条目；`audit` 汇总引用位置、逐句匹配与缺引用句。
5. **渲染交付**：`convert`/`audit` 按目标规范输出文献表文本；`audit --out` 落盘草稿，`serialize_result.py` 生成 `/app/output/result.json`。
6. **自检**：`python3 tests/selftest.py`（28 项），并对照 `templates/checklist.md` 六项逐条确认。

## 输出契约（result.json）

顶层九字段 `case_id, task_id, status, results, sources, uncertainty, changes, artifacts, metadata`（定义见 `resources/output_contract.json`，通用规范见 `resources/conventions.md`）。

```json
{
  "citations": [{"claim_span": "句子原文", "ref_keys": "k1", "placement": "after-numeric-claim", "style": "GB/T 7714-2015"}],
  "reference_list": [{"key": "k1", "metadata": "渲染后的条目", "doi": "10.1016/…", "source": "原条目 key", "status": "verified_shape"}],
  "dedup": [{"merged_keys": "k1, k2", "basis": "R-DOI; R-PREPRINT", "kept_key": "k1"}],
  "consistency_checks": [{"claim": "论断原文", "ref_key": "k1", "match": "strong", "evidence": "词重叠得分 0.375 | 题名…"}],
  "format_notes": {"target_style": "GB/T 7714-2015", "converted_from": "bibtex", "kept_fields": ["DOI", "volume", "issue", "pages"]}
}
```

`status`：`success | partial | undetermined | refused`。`match`：`strong | weak | mismatch | dangling | undetermined`。

## 题面特殊约定

通过 DOI 形态、题名占位特征与原文比对核验条目真实性，检出编造条目与元数据错配；证据不足的句子写入 `uncertainty` 并在 `citations` 中不臆造引用编号。

## 资源与依赖

- `scripts/cite.py`：解析/渲染/重排/去重/核验/审计，纯标准库。
- `scripts/serialize_result.py`：草稿 → 契约 `result.json`，校验九字段与本题 results 结构。
- `resources/`：字段定义与通用规范；`templates/rules.md`：合并判据、样式映射、六项自查；`examples/`：合成示例（标注为示例）。

## 最小调用示例

```bash
python3 scripts/cite.py audit --manuscript examples/manuscript.md --library examples/library.bib \
    --style "GB/T 7714-2015" --out /app/work/audit.json
python3 scripts/serialize_result.py --input examples/case.json --draft examples/draft.json \
    --out examples/example_result.json --skill-name reference-citation-management
```

`examples/example_result.json` 即输出形态（`case_id=EXAMPLE-CASE-W04`，`metadata.example_only=true`，非正式案例答案）。

## 限制与失败处理

| 情况 | 处置 |
|---|---|
| 文献库格式未识别 | `detect_format` 返回 `plain` 时报错退出，不猜字段；提示改用 `--format` 显式指定 |
| DOI 无法解析/在线核验不可用 | 只做形态与字段一致性检查，`status` 记 `verified_shape`，网络核验写入 `uncertainty` |
| 正文用著者-出版年或脚注制 | `renumber` 报 `non_numeric_marker`，不强行改成顺序编码制 |
| 编号超出文献表范围 | 报 `dangling_intext`，保留原编号不静默重排 |
| 期刊/预印本同名但作者不同 | 拒绝合并（`merge_basis` 返回 None），列入人工复核 |
| 稿件/条目乱码或字段缺失 | 原样保留并写 `uncertainty`，`status=partial` |
