# reference-citation-management

参考文献与引用管理 Skill：一眼看清"引用挂得对不对、编号顺不顺、重复条目收没收干净、条目和论断对不对得上"，并把四件事都做成可回查的结构化结果。

## 快速开始

```bash
python3 scripts/cite.py parse  --library examples/library.bib
python3 scripts/cite.py renumber --manuscript examples/manuscript.md --library examples/library.bib
python3 scripts/cite.py dedup  --library examples/library.bib
python3 scripts/cite.py convert --library examples/library.bib --style apa
python3 scripts/cite.py verify --library examples/library.bib
python3 scripts/cite.py audit  --manuscript examples/manuscript.md --library examples/library.bib \
    --style "GB/T 7714-2015" --out /app/work/audit.json
python3 scripts/serialize_result.py --input examples/case.json --draft examples/draft.json \
    --out /app/output/result.json --skill-name reference-citation-management
python3 tests/selftest.py      # 28 项断言
```

纯标准库，Python ≥3.8，无网络与第三方依赖。

## 文件

```
SKILL.md                        用途、流程、输出契约、限制与失败处理
scripts/cite.py                 单文件核心：解析 / 渲染 / 重排 / 去重 / 核验 / 审计（CLI 六子命令）
scripts/serialize_result.py     草稿 → 契约 result.json（九字段 + results 结构校验）
resources/output_contract.json  result.json 字段定义（含 example_only 标记）
resources/conventions.md        通用工作规范（证据、诚实状态、产物位置、体积、禁止事项）
templates/rules.md              去重判据、样式字段映射、六项自查表、常见失败模式
examples/                       合成示例：稿件 / 文献库 / case / 草稿 / 审计 / 契约结果
tests/selftest.py               28 项断言
```

## 能做什么

| 能力 | 命令 | 判据 |
|---|---|---|
| 多格式解析 | `parse` | BibTeX / RIS / EndNote / CNKI 自动识别，字段映射到统一记录 |
| 编号连锁更新 | `renumber` | 按首次出现重排、`1-3` 压缩、dangling 与未被引条目告警 |
| 条目去重 | `dedup` | `R-DOI` / `R-TITLE-NORM` / `R-TITLE-FUZZY` / `R-PREPRINT` / `R-BILINGUAL`，五条不合并的护栏 |
| 样式转换 | `convert` | GB/T 7714-2015、APA 7；保留 DOI、卷、期、页 |
| 来源核验 | `verify` | DOI 形态、缺年份/作者、占位题名、`needs_check` |
| 论断—文献匹配 | `audit` | strong / weak / mismatch / dangling + 词重叠得分；中文论断经概念桥与英文题名可比 |

## 实测（示例数据，可复跑）

6 条输入 → 4 条输出（DOI 与预印本两条重复合并为 1 条）；正文 6 处引用全部定位，1 处 `[6]` 判定 dangling，1 处论断无引用被列为 gap；编造条目 `fake2022ghost` 因 DOI 形态非法与占位题名被标 `needs_check`。

## 限制

- 在线核验（DOI 解析、数据库检索）不在 Skill 内做，网络不可用时只给形态与字段级结论，并写入 `uncertainty`。
- 概念桥为中英常见学术词表（约 20 组），领域新词需在 `templates/rules.md` 的 `CONCEPT` 段补充。
- 示例全部为合成文本，`case_id=EXAMPLE-CASE-W04`，`example_only=true`，不得冒充正式案例结果。

自研，无第三方代码；示例 CC0-1.0。
