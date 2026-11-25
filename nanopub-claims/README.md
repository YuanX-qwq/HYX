# nanopub-claims — 断言级 Nanopublication 抽取 Skill

把论文结论拆成**可逐条判定真假**的断言，为每条断言绑定最小充分证据和可回原文的坐标，附来源元数据，经机械质检后导出 JSON / CSV / TriG。

- 入口：[SKILL.md](SKILL.md)（Agent 加载后照此执行）
- 字段字典：[FIELD_DICTIONARY.md](FIELD_DICTIONARY.md)
- 方法与创新：[METHODS.md](METHODS.md)
- 受控关系词表：[vocab/predicates.json](vocab/predicates.json)
- 接口：[schemas/assertion_set.schema.json](schemas/assertion_set.schema.json)
- 示例：[examples/](examples/)（**全为合成示例，synthetic，不是任何正式案例结果**）
- 自测：[tests/selftest.py](tests/selftest.py)

## 依赖

| 组件 | 必需 | 说明 |
|---|---|---|
| Python ≥ 3.8 | 必需 | 全部脚本仅标准库，无网络 |
| 平台 `pdf-text-tool` / `pdf-render-tool` | 可选 | PDF → 页面文本；图片表格渲染复核 |
| 姊妹 Skill `pdf-literature-parser` | 可选 | 需要多栏阅读顺序/表格网格时先解析成 `document.json` |

版本/来源：脚本随本目录提交（见各文件头）；无第三方包；不依赖个人文件或手工操作。

## 最小调用（完整流程）

```bash
# 0) 输入：/input/case.json + /input/task.md + 材料（pages.json 或 PDF）
# 1) 页面 → 段落（带页/字符偏移）
python3 scripts/segment.py --pages work/pages.json --out work/paragraphs.json
# 2) 段落 → 候选断言（机械切分，两层）
python3 scripts/decompose.py --paragraphs work/paragraphs.json --out work/candidates.json
# 3) Agent 逐条填 subject / relation / object / qualifiers，写 work/assertions.json
# 4) 证据绑定 + 机械核验
python3 scripts/evidence.py bind   --assertions work/assertions.json --paragraphs work/paragraphs.json
python3 scripts/evidence.py verify --assertions work/assertions.json --paragraphs work/paragraphs.json
# 5) 质检（Q001–Q013）
python3 scripts/qc.py --assertions work/assertions.json --paragraphs work/paragraphs.json \
  --vocab vocab/predicates.json --out work/qc_report.json
# 6) 三态导出
python3 scripts/export.py --assertions work/assertions.json --out-dir output --case-id CASE_ID
```

示意输出见 `examples/output/assertion_set.example.json`、`examples/output/assertions.example.csv`、`examples/output/nanopub.example.trig`（**示例**，由 `examples/build_example.py` 从合成文档生成，共 20 条断言）。

## 输入输出

| 项 | 内容 |
|---|---|
| 输入 | `case.json`（case_id + output_contract）、`task.md`、材料（PDF 或 `pages.json`） |
| 中间 | `paragraphs.json`（段落+坐标）、`candidates.json`（候选）、`assertions.json`（断言+证据）、`qc_report.json` |
| 输出 | `assertion_set.json`（规范 JSON，符合 schema）、`assertions.csv`（19 列）、`nanopub.trig`（三子图） |

## 适用范围与限制

- 适用：英文/中文科研论文，单栏/双栏，有文字层；一个案例通常产出 10–60 条断言。
- 已声明边界：
  - 断言**语义**由 Agent 判断，脚本只做切分、定位、校验；脚本不"理解"科学含义。
  - 极长表格与跨页续表建议先用 `pdf-literature-parser` 解析成网格再引用表行。
  - 纯图片表格数值需人工对照渲染图转录，标 `source: manual`。
  - TriG 是可解析序列化，不含 nanopub 正式发布所需的密钥签名。
  - 判定依赖词表 cue，缩写/同义改写可能漏检；漏检不等于通过，需 Agent 复核。

## 失败处理与自查

- 失败即写 `status` + `uncertainty`，不抛异常掩盖；单页失败不影响其余页。
- 自查：`python3 tests/selftest.py`（31 项 fixture 断言，退出码 0 = 全过）。
- 人工接管位置：所有 `unbound` 引文、`fail` 的 Q 代码、`unreadable` 页都会在 `qc_report.json` 与 `uncertainty` 中标明断言 id / 页码 / 段落 id。

## 版本与维护

- 版本：1.0.0（2026-11-25）
- 改判定规则：同步 `scripts/claimlib.py` 与 SKILL.md 的 Q 代码表，并重跑 `tests/selftest.py`。
- 改字段：同步 `schemas/assertion_set.schema.json`、`FIELD_DICTIONARY.md`、CSV 列。
- 反馈请附 `case_id`、断言 id、`qc_report.json` 中的 code 与 detail。
