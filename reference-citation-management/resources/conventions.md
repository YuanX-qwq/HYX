# 通用工作规范

## 1. 读取真实输入
- 原始输入在 `/input/case.json` 与 `task.md`；稿件与文献库是真实文件，不按题名或领域标签假设内容。
- `case.json` 的 `case_id` 原样写入 `result.json`，不改写、不编造。
- 题面约束以本次 `task.md` 为准。

## 2. 证据与回链
- 每条结论指回原文位置：来源标识 + 段落/条目位置 + 原文短引（`sources[].locator`、`quote`）。
- 区分直接证据（条目原文、DOI）与间接推论（题名词元重合推得的匹配强度）。
- 读不出、未报告、冲突、同形异义的部分写入 `uncertainty`，不靠猜补齐。

## 3. 诚实状态
- `status`：`success`（完成）/ `partial`（部分完成并写明边界）/ `undetermined`（材料不足）/ `refused`（超范围）。
- 只在格式与字段层面确认的条目标 `verified_shape`，不得写成"已核验真实"。
- 不编造 DOI、页码、在线检索结果或运行日志。

## 4. 产物位置
- 过程产物在 `/app/work`（audit.json、中间解析结果），最终结果在 `/app/output/result.json`。
- 可继续编辑的稿件写 `/app/output/manuscript_revised.md`（编号已重排）。

## 5. 体积与预算
- Skill 资源 ≤50 个 UTF-8 文本文件、单文件 ≤500 KB、总量 ≤2 MB、无符号链接。
- 执行预算 64 次请求 / 900 秒 / 单响应 16384 token；先落盘诚实的部分结果再改进。

## 6. 禁止事项
- 不提交预制答案或隐藏测试；不把示例冒充正式案例结果（示例必须带 `example_only=true`）。
- 不输出 Token；不依赖作者本机的私有文件或手工操作。
