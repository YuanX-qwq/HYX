# academic-language-polishing

学术语言润色 Skill：改语言层不改结论层，每处修改可回原文，改完用脚本机械验证"没改坏"。

## 快速开始

```bash
python3 scripts/polish_check.py --original examples/before.txt --revised examples/after.txt \
    --revisions examples/draft.json --out examples/check.json
python3 scripts/serialize_result.py --case examples/case.example.json \
    --draft examples/draft.json --out examples/example_result.json
python3 tests/selftest.py
```

纯标准库，Python ≥3.8，无网络与第三方依赖。

## 文件

```
SKILL.md                      用途、流程、输出契约、限制
scripts/polish_check.py       10 类机械守恒检查（数值/单位/引用/指向/否定/限定/条件/量词/缩写/术语）+ 修改记录落位
scripts/serialize_result.py   草稿 → 契约 result.json（必填与枚举校验）
resources/output_contract.json  result.json 字段定义（含 example_only 示例值）
resources/conventions.md      通用工作规范（证据、诚实状态、产物位置、体积、禁止事项）
templates/registers.md        五种文体规则、中式英语高频问题、限定强度对照
examples/                     合成示例：before/after/draft/case + 生成结果（示例，非正式答案）
tests/selftest.py             24 项断言（含 4 类"改坏了"的负例）
```

## 关键字段

- `revisions[].original` 必须逐字出现在原文，`revised` 必须逐字出现在改文；`preserves_meaning` 必须为 `true` 才会被序列化器接受。
- `revisions[].type` 枚举：`grammar | syntax | collocation | punctuation | terminology | register | clarity | redundancy | cohesion | bilingual | other`。
- `status`：`success | partial | undetermined | refused`。
- `glossary` 记录中英写法、缩写首现、大小写与连字符约定；`unresolved` 记录需作者确认、本轮未改的项。

## 机械检查判 FAIL 的五种情形

1. 数值或单位被改（含单位大小写以外改动）；
2. 引用编号或图表/公式指向集合变化；
3. 否定标记减少（结论方向可能反转）；
4. 限定被升级（`may`→`prove`、`suggest`→`demonstrate`、`可能`→`证明`）；
5. 条件句或量词被删（`all`↔`some` 一类替换）。

WARN：限定词减少、缩写未见首次展开、术语存在非规范变体、修改记录覆盖率不足 60%。

## 限制

- 只覆盖可机读的文本层；扫描件、公式图片、表格图片不推断内容。
- 词表基于中英常见学术表达，专业领域新造词需在 `glossary` 显式登记。
- 示例文本全部为合成文本，`case_id=EXAMPLE-CASE-000`，不得当作正式案例结果。

自研，无第三方代码；示例 CC0-1.0。
