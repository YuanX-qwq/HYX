# 通用工作规范

- 产物位置：过程文件放 `/app/work`，最终 `result.json` 放 `/app/output`；`artifacts` 里的路径相对 `/app/output`。
- 证据：每条结论必须有可回查来源（`source_id` + `locator` + 逐字 `quote`）；转述与自述分开标注。
- 诚实：读不出、未报告、冲突一律进 `uncertainty`；`status` 与内容一致，`partial` 要写明缺什么。
- 不编造：不得虚构数值、页码、图表、运行日志与测试成绩。
- 资源：≤50 个 UTF-8 文本文件、单文件 ≤500 KB、总 ≤2 MB、无符号链接。
- 语言：跟随原文语言记录，术语保留原文写法，中文笔记不改变原句语义。
