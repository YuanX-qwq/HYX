# 通用工作规范（litkg-builder 遵循）

以下规范与赛题提交约定一致；若网页通用提示与本题 task.md 冲突，以本题提交约定为准。

## 1. 读取真实输入
- 运行时原始输入为 `/input/case.json` 与 `task.md`，材料文件按题面提供（常见：`corpus-manifest.json`、`material.json`、`primary-material.json`、`secondary-material.json`）。
- 先读真实文件，不按标签或领域名称猜内容；`case_id` 原样写入 `result.json`。
- 根级 `doi` / `title` / `authors` 属于第一篇材料，不得套到第二篇。

## 2. 证据与回链
- 每个节点、每条边都要有 `source_id` + JATS `paragraph_id` + 原文短引。
- 位置是组织方段落 ID，不是 PDF 页码；本 Skill 不写页码，也不把自建分页称作原 PDF 页。
- 区分直接证据与间接推论（`strength`），区分作者自述与他人转述（`attribution`）。
- 未报告、冲突、无法定位的引文一律进 `uncertainty`，不靠猜补齐。

## 3. 诚实状态
- `status` 取值：`success` / `partial` / `undetermined` / `refused`。
- 部分完成必须写边界；材料不足或段落无法解析时用 `undetermined` 并说明缺什么。
- 不编造软件状态、科学数据、运行日志或测试成绩。

## 4. 产物位置
- 过程产物 `/app/work`；最终结果与被查询/导出产物 `/app/output`，其中 `result.json` 必须含全部契约字段与 `case_id`。
- 图谱导出物（`kg.json` / `nodes.csv` / `edges.csv` / `kg.graphml` / `kg.cypher` / `kg.html`）与 `queries.json` 与 `result.json` 同目录。

## 5. 资源与体积约束
- Skill 资源：≤50 个 UTF-8 文本文件、单文件 ≤500KB、总量 ≤2MB、不允许符号链接。
- 运行时产物可为二进制，独立于最终 JSON 有效性保留。
- 执行预算：64 次模型请求、900 秒、每响应 16384 token（含推理）；尽早保存诚实的部分结果。

## 6. 禁止事项
- 不提交预制正式答案、隐藏测试或白板；正式案例与对照由平台提供。
- 不在回复或提交文件中输出 Token。
- 不把示意示例冒充正式案例结果：`resources/output_contract.json` 的 `example_only` 与 `examples/` 均标注为示例。
- 不把两篇论文的不同条件、样本或数值合成为一个结论。
