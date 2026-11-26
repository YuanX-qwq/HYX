# literature-structured-notes

阅读10｜文献总结与结构化笔记的 Skill 本体（Bohrium Playground 作品）。

## 运行

```bash
python3 scripts/notes.py build --case examples/case.example.json --out examples/output/results_draft.json
python3 scripts/serialize_result.py --input examples/case.example.json \
  --draft examples/output/results_draft.json --out examples/output/result.json \
  --task-id product-arena-06-6d8cf72b
python3 tests/selftest.py
```

- `build`：按章节切句，抽研究问题/数据/方法/发现/局限，生成章节笔记与知识点草稿。
- `serialize_result`：按官方契约校验收口（章节顺序、字段齐备、定位可反查、来源回链），不合规直接失败。
- 自测 23 项：章节顺序、卡片五字段、小数不切句、术语去重、每条笔记回链、确定性，以及 5 类坏输入必须被拒。

## 目录

```
scripts/notes.py            章节切分 + 线索词抽取 + 笔记生成
scripts/serialize_result.py 官方 result.json 组装与校验
resources/                  官方 output_contract.json、field_definitions.md、conventions.md
examples/                   合成案例（4 段式论文，含 Limitations）+ 产物
tests/selftest.py           23 项断言
```

## 边界

- 只有文本层：图表数值、页码、图像不推断，缺什么写进 `uncertainty`。
- 卡片缺字段即 `status=partial`，不用常识补齐。
- 示例语料为自造，不含任何正式案例答案。
