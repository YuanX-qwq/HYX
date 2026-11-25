# methods-experiments-writing

把散落的配置、运行日志与步骤记录整理成可执行、可核对的方法与实验章节；正文数值必须能回查到配置或日志，缺口与冲突显式标出。

## 快速开始

```bash
python3 scripts/mew.py run --config examples/config.yaml --log examples/run.log \
    --steps examples/steps.md --draft examples/draft.md --out examples/draft_result.json
python3 scripts/serialize_result.py --input examples/case.json --draft examples/draft_result.json \
    --out examples/example_result.json
python3 tests/selftest.py
```

纯标准库，Python ≥3.8，无第三方依赖与网络访问。

## 文件

```
SKILL.md                        用途、流程、输出契约、限制
scripts/mew.py                  解析/参数/步骤/检查/成稿/一键（parse params steps check assemble run）
scripts/serialize_result.py     九字段契约序列化 + 语义校验（来源绑定、步骤升序、success 不得带待确认项）
resources/output_contract.json  result.json 字段定义（含 example_only 示例值）
resources/conventions.md        通用工作规范
templates/methods_checklist.md  六要素自查表 + 追问清单
examples/                       合成材料与示例结果（示例，非正式答案）
tests/selftest.py               34 项断言
```

## 判据速查

- **参数表**：每条必须有 `source`（`config.yaml:行号` 或 `log` 中的 key=value）；无来源的参数不得入表。
- **正文对齐**：数值命中配置 → `sourced`；同键不同值且同分句 → `conflict`；带度量线索（学习率/准确率/epoch…）但材料里没有 → `unsourced`。
- **步骤**：≥2 步、按 order 升序、每步给出输入与输出（缺失步骤进限制清单）。
- **状态**：有 `conflict` / `unsourced` / 需确认限制 → `status=partial`，序列化器拒绝 `success`。

## 限制

- YAML 解析只覆盖两层缩进与 `key: value` / 行内列表；复杂锚点、多文档请先转 JSON。
- 参数单位由键名后缀（`_ms/_gb/_ratio` 等）或末段名（`lr/epochs` 等）推断，推断不出记 `—`，不臆造。
- 基线"是否同预算"无法从材料判定时一律写"未说明"，不假设同等预算。
- 示例材料全部为合成内容（`EXAMPLE-CASE-000`），不得当作正式案例结果。

自研，无第三方代码；示例 CC0-1.0。
