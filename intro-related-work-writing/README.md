# intro-related-work-writing

把"写引言/相关工作"拆成**证据层**（可机械核对）与**表达层**（Agent 写作），每条结论都能回到文献库记录或本文图表编号。

## 快速开始

```bash
# 1) 文献库 → 结构化记录
python3 scripts/introkit.py parse --library examples/library.bib --out /app/work/records.json

# 2) 分组、空白、贡献、覆盖四步
python3 scripts/introkit.py group --records /app/work/records.json --out /app/work/groups.json
python3 scripts/introkit.py gap --groups /app/work/groups.json --out /app/work/gap.json
python3 scripts/introkit.py coverage --text examples/intro.md --library examples/library.bib --out /app/work/cov.json

# 3) 一步汇总出草稿
python3 scripts/introkit.py assemble --case examples/case.json --library examples/library.bib \
    --intro examples/intro.md --paper examples/paper.json --out /app/work/results_draft.json
python3 scripts/serialize_result.py --input examples/case.json \
    --draft /app/work/results_draft.json --out /app/output/result.json

# 4) 自测
python3 tests/selftest.py
```

纯标准库，Python ≥3.8，无网络与第三方依赖。

## 文件

```
SKILL.md                      用途、流程、输出契约、限制
scripts/introkit.py           六个子命令：parse / group / gap / contrib / coverage / assemble
scripts/serialize_result.py   草稿 → 契约 result.json（维度≥2、空白证据、贡献定位、覆盖字段校验）
resources/output_contract.json  result.json 字段定义（标注 example_only）
resources/conventions.md      通用工作规范
templates/related_work.md     分组叙述规则、空白句式、贡献写法、禁用语
examples/                     合成文献库、示例引言、paper.json、case.json、draft.json、example_result.json
tests/selftest.py             31 项断言（含未归类、单一局限、定位失败、无引用句、库外引用等负例）
```

## 三个硬判据

1. **空白成立**：同一局限的词元相似度 ≥0.25 且支撑工作 ≥2 条，否则降级为 `insufficient` / `no_evidence`。
2. **贡献对得上**：`evidence_locator` 必须是本文真实存在的 `fig:` / `tab:` / `res:` 编号，且与图表说明词元重合 ≥0.15。
3. **引用覆盖**：事实句（含数字或结果动词）无 `[key]` 即列出；近 3 年工作与关键工作未引即列入 `missing`；库里没有的键进 `unknown_citations`。

## 限制

- 结论/条件/局限由摘要句规则抽取，摘要缺失时退化为题名级证据并标记 `title_only`。
- 维度分组靠词表命中，跨学科新词需在 `DIM_LEX` 增补；未命中记录不硬塞。
- 示例文献库与示例稿件全部为合成内容，`case_id=EXAMPLE-CASE-000`，不是正式案例答案。

自研，无第三方代码；示例 CC0-1.0。
