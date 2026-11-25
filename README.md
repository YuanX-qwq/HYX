# HYX

本仓库用于存放 AI/科研工具作品。

## litkg-builder

证据绑定的文献知识图谱 Skill：从多篇论文材料建图，每个节点/边都带 `source_id` + JATS 段落 ID + 原文短引；跨篇按规则区分"合并 / 不合并"（通用方法可合并，材料样品/数据集/指标/条件不合并），跨篇数值冲突保留不合并不取均值；内置 11 类受控关系、K001–K012 质检、≥3 条可执行查询、JSON/CSV/GraphML/Cypher/HTML 导出，以及 Agent 补关系时的引文定位强校验。

- 入口：[litkg-builder/SKILL.md](litkg-builder/SKILL.md)
- 词表：[litkg-builder/vocab/](litkg-builder/vocab/)（10 类实体 / 11 类关系）
- Schema：[litkg-builder/schemas/kg.schema.json](litkg-builder/schemas/kg.schema.json)
- 合成示例产物：[litkg-builder/examples/output/](litkg-builder/examples/output/)（合成语料，非正式案例结果）
- 自测：`python3 litkg-builder/tests/selftest.py`（32 项）

同步自 Bohrium 挑战「阅读15｜文献知识图谱构建」（product-arena-10-760d1a0b）的提交包。

## nanopub-claims

断言级 Nanopublication 抽取 Skill：把论文段落拆成单一可判断真假的断言（主体–受控关系–客体 + 条件限定），为每条断言绑定最小充分证据（逐字引文 + 页码 + 段落 id + 字符偏移），记录论文/作者/年份/版本/标识符来源，跑 Q001–Q013 机械质检，导出 JSON / CSV / TriG 三态可机读结构。

- 入口：[nanopub-claims/SKILL.md](nanopub-claims/SKILL.md)
- 字段字典：[nanopub-claims/FIELD_DICTIONARY.md](nanopub-claims/FIELD_DICTIONARY.md)
- 方法与判据：[nanopub-claims/METHODS.md](nanopub-claims/METHODS.md)
- 20 条断言示例：[nanopub-claims/examples/](nanopub-claims/examples/)（合成示例，非正式案例结果）
- 自测：`python3 nanopub-claims/tests/selftest.py --workdir /tmp/nanopub-selftest`（31 项）

同步自 Bohrium 挑战「阅读14｜Nanopublication」（product-arena-09-0e8befd4）的提交包。

## grounded-paper-translator

科研文献英译中 Skill：把 PDF/文本切成带页码锚点的段落，先抽术语并锁定译名，再逐段翻译，最后用脚本机械核验数字、单位、引用、图表编号、公式符号、否定与限定是否保留，输出段落级双语对照与可复核的 `result.json`。

- 入口：[grounded-paper-translator/SKILL.md](grounded-paper-translator/SKILL.md)
- 方法：[grounded-paper-translator/METHOD.md](grounded-paper-translator/METHOD.md)
- 运行示例：[grounded-paper-translator/examples/](grounded-paper-translator/examples/)
- 真实论文运行产物：[grounded-paper-translator/demo/](grounded-paper-translator/demo/)（arXiv:1605.01735v1，43 段双语对照，核验 0 FAIL）
- 自测：`python3 grounded-paper-translator/tests/selftest.py --workdir /tmp/translate-selftest`

同步自 Bohrium 挑战「阅读03｜文献翻译」（product-arena-01-5a9928c1）的提交包。

## pdf-literature-parser

科研 PDF 文献解析 Skill：把论文 PDF 解析成带证据锚点的结构化模型（多栏阅读顺序、章节层级、表格网格、公式编号、参考文献、OCR 回退），并据此完成解析/翻译/问答/提取/核验/知识结构化任务。

- 入口：[pdf-literature-parser/SKILL.md](pdf-literature-parser/SKILL.md)
- 方法：[pdf-literature-parser/METHOD.md](pdf-literature-parser/METHOD.md)
- 自测：python3 pdf-literature-parser/tests/selftest.py --workdir /tmp/litparse-selftest

同步自 Bohrium 挑战「阅读01｜文献文档解析」（product-arena-08-3027d350）的提交包。

## academic-language-polishing

学术语言润色 Skill：改语言层不改结论层，逐句记录原文/改文/类型/理由，并用脚本机械验证数字、单位、引用、图表指向、否定、限定强度、条件与量词未被改坏。

- 入口：[academic-language-polishing/SKILL.md](academic-language-polishing/SKILL.md)
- 检查脚本：[academic-language-polishing/scripts/polish_check.py](academic-language-polishing/scripts/polish_check.py)
- 自测：python3 academic-language-polishing/tests/selftest.py（24 项）

同步自 Bohrium 挑战「写作02｜学术语言润色」（product-arena-02-7051d92d）的提交包。