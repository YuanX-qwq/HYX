# 通用工作规范（academic-language-polishing 遵循）

若网页通用提示与本案例 task.md 冲突，以本题提交约定为准。

## 1. 读取真实输入
- 运行时输入为 `/input/case.json` 与 `task.md`，稿件按题面提供；`case_id` 原样写入 `result.json`。
- 先读真实文本，不按标题或领域标签假设内容；章节、段落、行号以输入中的实际结构为准。
- 长稿按章节顺序逐段处理，不删段、不并段、不改变编号与交叉引用。

## 2. 证据与回链
- 每条修改记录 `span / original / revised / type / reason / preserves_meaning`，`original` 必须逐字出现在原文，`revised` 必须逐字出现在改文。
- 术语决策（缩写首现、大小写、连字符、中英对应）写入 `glossary`，并说明依据。
- 数字、单位、引用编号、图表/公式指向如有改动，必须在 `sources` 或 `uncertainty` 中给出原文定位与理由。

## 3. 诚实状态
- `status`：`success` / `partial` / `undetermined` / `refused`。
- 无法确认原意保持的句子，不写入 `revisions`，改列 `unresolved`；部分完成必须写边界。
- 不编造软件状态、评分或运行日志。

## 4. 产物位置
- 过程产物 `/app/work`；最终 `/app/output`，其中 `result.json` 必须含全部契约字段与 `case_id`。
- 双语对照、术语表、修改清单与检查报告放在 `result.json` 同目录。

## 5. 资源与体积约束
- ≤50 个 UTF-8 文本文件、单文件 ≤500KB、总量 ≤2MB、无符号链接。
- 执行预算：64 次模型请求、900 秒、每响应 16384 token（含推理）；先保存可用的部分结果。

## 6. 禁止事项
- 不提交预制答案、隐藏测试或白板。
- 不在回复或提交文件中输出 Token。
- 不把示例冒充正式案例结果：`examples/` 与 `resources/output_contract.json` 的 `example_only` 均为示意。
- 不偷偷加强或削弱结论：限定词强度、否定范围、因果与相关性、条件与量词必须守恒。
