# METHODS — 方法、判据与创新边界

本文件说明本 Skill 如何回应题目的四个考察点（拆得细 / 对得上 / 追得回 / 读得懂），
相对基础 Agent 的增益，以及**可以复现**的判定依据。所有数值与流程都能由
`tests/selftest.py`（31 项断言）与 `examples/build_example.py`（20 条合成断言）重复得到。

## 1. 拆得细：两级机械切分 + 语义粒度判据

**两级切分**（`scripts/decompose.py`）：

1. 句级：按句末标点（`。！？；;?!`）与 `. ` + 大写/汉字 切句；
2. 连接级：在并列/因果/转折连接词（并且/同时/此外/但是/因此/因为/and/while/because…）处再切一段，
   仅当连接词前后各有 ≥4 字符（避免把 "而且"、"because of" 这类词切碎）。

切分只给候选，语义由 Agent 填。粒度判据（写进 SKILL.md 第 3 步，且可被 Q001 复核）：

- **一句一关系**：`text` 里出现 ≥3 个关系 cue（增加/降低/抑制/激活/相关/导致/结合…）即判"过宽"；
- **条件外置**：温度、pH、剂量、时长、样本进 `qualifiers`，不留在 `text` 里当形容词；
- **复合句拆开**：并列（A 抑制 B，并使 C 下降）与因果（A 因 B 而升高）各成一条，因果用
  `causes`/`caused_by`，相关用 `correlates_with`，两者不混用；
- **可判断性门槛**：方法描述、背景铺垫、致谢不产生断言，进 `unreported` 并写原因。

相对"整段塞进一个 text"的做法，这套判据把"是否拆够"从主观感受变成可计数的事实（cue 数、句数）。

## 2. 对得上：最小充分证据的机械定义

`evidence.py` 做三件事：

- **定位**（`locate`）：两级匹配——先按空白折叠，再按去全部空白（应对 PDF 断行/软连字符）；
  返回命中的段落 id 与 `char_start/char_end`（相对段落文本，0 基、右开）。
- **绑定**（`bind`）：按 `quote` 回填 `page/paragraph_id/char_start/char_end`，失败逐条列出。
- **核验**（`verify`）：`paragraph_text[char_start:char_end]` 去空白后必须等于 `quote`，
  否则 Q010；quote 不是任何段落子串则 Q003。

**最小充分性判据**（Q004）：证据片段必须同时包含 `subject.name` 与 `object.name`。
只含结论、缺主体的片段（如只引"使反应速率下降 40%"）判为不足，必须扩到含主体的最小窗口，
或降级为 `inferred` 并在 `uncertainty` 说明。`minimal_span()` 提供了"包含全部 token 的最短连续窗口"，
Agent 可直接采用该窗口而不是整段照抄。

**直接 vs 间接**：原文直述 → `direct`；需要跨段/跨表拼接才能成立 → `indirect`，且
`modality` 至少为 `inferred`（Q012 检出"推论性断言却标直接证据"）。

## 3. 追得回：来源元数据与回链

- 必填四项（title/authors/year/source_id）缺失即 Q006 fail；`source_id` 优先 DOI，无 DOI 用
  `sha256:<文件哈希>`，保证同一材料在多次运行、多人复用时落到同一个键，可去重。
- 断言 → `provenance_ref` → `source`；断言 → `evidence` → 页码/段落 id/字符偏移。三段链路在
  JSON、CSV、TriG 三态里都保留，TriG 里分别落到 `sub:assertion`、`sub:provenance`、`sub:pubinfo`。
- 冲突处理：原文自相矛盾时两条断言都保留，`uncertainty.kind=conflict` 列出两处位置，不擅自选边。

## 4. 读得懂：固定字段 + 三态导出 + 确定性

- JSON 走 `schemas/assertion_set.schema.json`（draft 2020-12）；CSV 19 列、列序固定；
  TriG 三子图、前缀固定。
- **确定性**：无随机、无时间戳、无自增 UUID；同一输入重复导出逐字节一致（`determinism` 断言）。
  这让"结果可复核"不依赖运行环境。
- 下游可直接解析：CSV 给表格工具，JSON 给程序，TriG 给 RDF 栈。

## 5. 质检的可复现性（Q001–Q013）

每条 issue 都带 `criterion` 字段，写的就是脚本里执行的判定式（例如"句末标点数>1 或关系动词
cue 命中数>=3"、"quote 去空白后不是任何段落子串"）。因此第三方拿到同样的输入与脚本，能复现
同一个判定，而不需要相信作者的描述。

## 6. 相对基础 Agent 的增益（可验证）

基础 Agent 直接读 PDF 做"nanopublication"的典型失败：

| 失败 | 本 Skill 的确定性处置 | 可复核证据 |
|---|---|---|
| 整段塞进一条"断言" | 两级切分 + Q001 cue 计数 | `decompose.py` 输出候选数；Q001 |
| 引文是转述不是原文 | `verify` 强制逐字，失败即 Q003 | `evidence.py verify` 退出码 |
| 证据缺主体、无法判断谁对谁 | Q004 最小充分判据 | `qc_report.json` |
| 页码/段落指不到原文 | char 偏移与原文切片比对（Q010） | `evidence.py verify` |
| 来源只有一个标题 | Q006 四字段硬检 | `qc_report.json` |
| 每次输出不一样 | 全流程确定性 | `determinism` 断言 |
| 推论当事实 | `modality` + Q012 | `qc_report.json` |

**效率**：分段/切分/绑定/核验/导出各一次脚本调用；Agent 只需在候选上做语义判断，不必反复
回读全文找坐标。按 SKILL.md 的预算规划 ≤40 次模型请求（限额 64）。

**边界**：语义判断仍由 Agent 完成，脚本不理解科学含义；cue 词表对缩写与同义改写可能漏检，
漏检不等于合格；TriG 不含签名。

## 7. 复用与维护

- `vocab/predicates.json` 是唯一的关系词表入口，扩展只改这一处。
- 改判定式 → 同步 `scripts/claimlib.py`、SKILL.md 的 Q 表、`tests/selftest.py`。
- `examples/build_example.py` 可从合成文档重建 20 条断言样例，用于回归与对外演示。
