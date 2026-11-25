# latex-writing-compilation · 写作13｜LaTeX 写作与编译

对官方固定科研案例完成 LaTeX 写作与编译：结构/宏包、多行公式、宽表与三线表、浮动体、
`\cite`/`\ref` 与 BibTeX 对应、模板适配、编译报错定位与可重复构建。
交付**可编辑源码 + 真实 PDF/PNG + 构建记录**。

## 目录

```
SKILL.md                      流程、输出契约、限制
scripts/latexkit.py           六个子命令（仅标准库）
scripts/serialize_result.py   result.json 组装与语义校验
resources/output_contract.json / conventions.md
templates/template_required.json
examples/draft/               示例稿件（含 7 处真实缺陷，仅示例）
examples/patches.json         与诊断一一对应的确定性补丁
examples/case.json / task.md  示例输入
tests/selftest.py             51 项断言（不依赖 TeX）
```

## 用法

```bash
python3 scripts/latexkit.py scan  --root examples/draft --out work/struct.json
python3 scripts/latexkit.py lint  --root examples/draft --out work/lint.json
python3 scripts/latexkit.py build --root examples/draft --engine pdflatex --out work/build_draft.json
python3 scripts/latexkit.py apply --root examples/draft --patches examples/patches.json --dest work/fixed --out work/apply.json
python3 scripts/latexkit.py build --root work/fixed  --engine pdflatex --out work/build_fixed.json
python3 scripts/latexkit.py check --root work/fixed --template templates/template_required.json --build-json work/build_fixed.json --out work/tpl.json
python3 scripts/latexkit.py assemble --case examples/case.json --struct work/struct.json \
    --lint work/lint.json --build work/build_fixed.json --tpl work/tpl.json --out work/results.json
python3 scripts/serialize_result.py --input examples/case.json --draft work/draft_result.json --out result.json
```

## 机制（不是提示词，是判据）

- **宏包**：正文用到的命令/环境 → 所需宏包（`\toprule`→booktabs、`tabularx` 环境→tabularx 等），preamble 缺则 `MISSING_PACKAGE`（error）。
- **引用**：`\label` 重复、`\ref`/`\eqref` 悬空、`\cite` 键不在 `.bib`、`.bib` 条目未被引用，各自成码；每条带 `file/line/fix`。
- **宽表**：按列格式与最长单元格估算表宽（`X`/`p{}` 折算），超文本宽 → `WIDE_TABLE`（error），补丁改 `tabularx`+`X`，**不允许 `\resizebox` 硬压**。
- **版式**：多列表无 booktabs 三线表、`[h]` 单放、表格/图未被正文引用，各成一条 warn。
- **编译**：真实跑 `pdflatex`（可换 xelatex/lualatex），多遍直到 `Rerun` 与 undefined 消失；解析 log 的 `file:line: msg`、`! ...`+`l.N`、`Overfull \hbox (Xpt too wide)` 并归到文件行；记录发行版、宏包/字体版本、命令、遍数。
- **无引擎**：`build.status=engine_unavailable`，状态降 `partial`，不写成功。

## 自测

```bash
python3 tests/selftest.py     # 51/51，无需 TeX
```
