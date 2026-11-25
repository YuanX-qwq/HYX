# 示例任务（synthetic，仅作最小调用示意）

阅读附件 `example-paper.pdf`（示例论文，双栏排版，含公式与表格），完成：

1. 用一句话说明论文的核心主张（main claim）。
2. 提取 Table 1 的全部数值结果，按"行 × 列"结构输出，并给出每个数值所在页码与区块位置。
3. 若原文未报告某信息（如样本量、置信区间），必须在"未报告"清单中列明，不得编造。

## 输出契约（output_contract 摘要）

- `result.questions[]`：每个问题给出 `answer` 与 `evidence[]`（含 quote/page/block_id/bbox）。
- `result.unreported[]`：原文未报告项。
- `result.status`：success / partial / failed / unable / refused。

## 约束

- 答案必须逐字引用原文作为依据，引用由 `evidence.py` 机械核验。
- 材料缺失、无法判断、运行失败分别说明。
