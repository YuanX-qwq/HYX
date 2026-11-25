# 译文自检清单（提交前逐项打勾）

由 `verify.py` 自动检查的项标 **[auto]**；需要人判断的项标 **[manual]**。

## 覆盖与结构

- [ ] **[auto]** `scope.pids` 全部有非空译文，`coverage.rate = 1.0`
- [ ] **[auto]** 无重复 pid、无超出 scope 的 pid
- [ ] **[auto]** 每段 `pid/page/kind` 与 `segments.json` 一致，未合并/拆分段落
- [ ] **[manual]** 跨页续段（`page_end`）译文读起来连贯，没有半句衔接错误
- [ ] **[manual]** 图注、表注、脚注都已翻译，未混入正文

## 术语

- [ ] **[auto]** `glossary` 检查 0 FAIL（锁定词条在每处出现都使用锁定译名）
- [ ] **[manual]** 缩写与专名（CNN、t-SNE、TensorFlow、人名）保留原文且前后一致
- [ ] **[manual]** 首次出现的术语可附英文原词，后续不重复括号

## 事实保真

- [ ] **[auto]** `numbers` 0 FAIL：数字、百分数、科学计数、范围、误差全部保留
- [ ] **[auto]** `units` 0 FAIL：单位与 `%` 未被省略
- [ ] **[auto]** `citations` 0 FAIL：`[n]`、`[n, m]`、`[n-m]` 原样
- [ ] **[auto]** `cross_refs` 0 FAIL：图/表/式/节/文献编号与原文一致
- [ ] **[auto]** `negation` 0 FAIL：否定未被删除、未被添加
- [ ] **[auto]** `symbols` 0 FAIL：希腊字母与数学符号未丢失
- [ ] **[auto]** `untranslated` 0 FAIL：没有照抄原文的段落

## 质量与边界

- [ ] **[auto]** `length` / `sentences` 的 WARN 已逐条确认（不是漏译/添译）
- [ ] **[manual]** 公式段落保持原记号，未被“意译”成错误的数学
- [ ] **[manual]** 不确定处使用 `[待确认]` 且在 `uncertainty` 写明原因
- [ ] **[manual]** 参考文献段保持原文，未翻译作者/刊名/编号
- [ ] **[manual]** 领域内可读性抽查：摘要、结论各读一遍，无机器翻译腔造成的事实歧义

## 交付物

- [ ] `result.json` 含 `case_id`、`status`、`result`、`coverage`、`evidence`、`uncertainty`、`sources`、`change_log`
- [ ] `bilingual.md` / `bilingual.csv` / `glossary.csv` 与 `result.json` 内容一致
- [ ] `status=partial` 时 `status_note` 与 `uncertainty` 写明限制与人工接管位置
