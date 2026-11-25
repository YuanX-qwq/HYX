# 示例任务（synthetic，非正式案例）

> 这是一组**合成示例**，用来演示接口与完整流程。材料是 `examples/sample_pages.json`
> （2 页 / 10 段 / 20 句，由 `examples/build_example.py` 确定性生成），不是任何真实论文。

## 任务

读完 `sample_pages.json`，把其中每句可判断真假的结论抽成一条断言，并：

1. 每条断言给出主体、受控关系（`vocab/predicates.json` 的 id）、客体与条件限定；
2. 为每条断言绑定原文中**同时包含主体与客体**的逐字片段，并给出页码、段落 id、字符偏移；
3. 填 `source` 元数据（本示例的 `source_id` 用 `sha256:synthetic-example-0001`）；
4. 跑 `qc.py`，把 `fail` 修到 0；`warn` 需说明理由；
5. 导出 `assertion_set.json` / `assertions.csv` / `nanopub.trig`。

## 期望（结果示例）

`examples/output/` 下三份文件就是用本任务跑出来的示例产物：

- `assertion_set.example.json`：20 条断言，`status=success`，`qc` 全部 pass；
- `assertions.example.csv`：20 行 + 表头（19 列）；
- `nanopub.example.trig`：assertion / provenance / pubInfo 三子图。

## 复现

```bash
python3 examples/build_example.py        # 重新生成上面三份示例产物
python3 tests/selftest.py                # 31 项 fixture 断言（含质检与确定性）
```
