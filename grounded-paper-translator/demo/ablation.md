## 6. 对照实验（本会话实测，6 段）

为说明“术语锁定 + 机械核验”相对“单遍直译”的增益，在同一模型、同一原文、同一 6 段
（`P0007/P0021/P0037/P0042/P0077/P0106`，含术语、数字、引用与否定）上做了一次真实对照：

| 条件 | 术语一致率 | FAIL | WARN | 说明 |
|---|---|---|---|---|
| 单遍直译（不查术语表、不做自检） | 27/32 = **84.4%** | 10 | 1 | 6 个术语出现漂移：`Monte Carlo`→“蒙特卡罗”、`hidden layer`→“隐层”、`accuracy`→“精度”、`feed-forward neural network` 未用“前馈神经网络”、`training set` 与 `neural network` 段内不一致 |
| 本 Skill（先锁 37 条术语，再译，verify 返修至 FAIL=0） | 32/32 = **100%** | 0 | 1 | 同一核验口径下全部术语合规 |

两组在**数字、单位、引用**上没有出现 FAIL——单遍直译通常会保留数字，因此差异主要集中在
**术语一致性**与**否定关系**（对照组另有 1 条否定 FAIL）。这一对照只支持“术语与否定层面的
可验证增益”，不应外推为全面质量提升。两组的 1 条 WARN 相同（“是否”类否定启发式误报），
说明核验规则对两组口径一致。

数据文件：`demo/ablation.json`（含逐词漂移段号与 FAIL 明细），可复现：

```bash
python3 "$SKILL_DIR/scripts/verify.py" --segments demo/segments.json \
  --translations demo/translations.jsonl --glossary demo/glossary.lock.json \
  --scope <6 段 scope> --out skill.verify.json
```
