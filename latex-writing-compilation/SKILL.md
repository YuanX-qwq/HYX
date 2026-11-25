---
name: latex-writing-compilation
description: "Author and compile LaTeX for academic submissions: organize main/child files and preamble with correct package loading, align multi-line equations with numbering and references, handle wide tables, floats and three-line tables, resolve \\cite/\\ref and BibTeX correspondence, adapt to journal/conference/thesis templates, and fix compile errors with file/line/cause. Deliver editable source plus a real rendered PDF/PNG and a reproducible build record (distro, package/font versions, engine, passes, commands)."
---

# 写作13｜LaTeX 写作与编译

在 Bohrium Playground（Harbor 评测）中，对官方提供的固定科研案例完成 LaTeX 写作与编译任务。
评测时本 Skill 安装到 `/skills/weekly-skill`；输入 `/input/case.json` 与 `task.md`，过程产物 `/app/work`，最终结果 `/app/output`。

## 用途与触发条件

**适用**（可聚焦其一，本 Skill 六项都覆盖）：源码结构与宏包加载；多行公式对齐、编号与引用；宽表、浮动体与三线表；`\cite`/`\ref` 与 BibTeX 对应；期刊/会议/学位论文模板适配；编译报错定位与可重复构建。

**不适用**：不产出预制答案；不解释题面未要求的科学结论；不编造编译成功、日志或测试成绩。

## 执行流程

1. **读取输入**：读 `/input/case.json` 与 `task.md`，确认任务边界、材料路径、模板要求与证据范围；`case_id` 原样保留。
2. **结构扫描**（`latexkit.py scan`）：主文件/子文件/参考文献图的真实结构、preamble 已加载宏包、正文实际用到的命令，产出 `latex_sources`（path + role）。
3. **静态诊断**（`latexkit.py lint`）：宏包缺失、未定义/重复标签、悬空 `\ref`/`\eqref`、`\cite` 与 `.bib` 不匹配、宽表溢出、非三线表、浮动体未被正文引用、`[h]` 放置、模板必填项缺失。每条都给 `file/line/code/fix`。
4. **真实编译**（`latexkit.py build`）：按指定引擎跑多遍直到交叉引用收敛；解析 log 的 `Overfull \hbox`、`! LaTeX Error`、`! Undefined control sequence` 并归到具体文件与行；记录引擎、遍数、发行版、宏包/字体版本、命令。
5. **改稿**（`latexkit.py apply`）：用 `patches.json`（`file/find/replace/reason`）做确定性文本替换，产出可编译的定稿目录；不能机械修复的项写进 `uncertainty`，不猜。
6. **模板合规**（`latexkit.py check`）：对照模板必填项与版式约束（不溢出、三线表、图表被引用、引用收敛）。
7. **序列化交付**：`python3 scripts/serialize_result.py` 生成 `/app/output/result.json`（字段见 `resources/output_contract.json`），同时交付可编辑源码 + 真实 PDF/PNG 预览 + 构建记录。

## 输出契约（result.json）

顶层 `case_id, task_id, status, results, sources, uncertainty, changes, artifacts, metadata`。`results` 结构：

```json
{
  "latex_sources": [{"path": "string", "role": "string"}],
  "build": {"engine": "", "passes": "", "status": "", "logs": "", "errors": [{"file": "", "line": "", "cause": "", "fix": ""}]},
  "artifacts": [{"path": "", "type": ""}],
  "template_compliance": {"required_fields": [], "layout_ok": true},
  "reproduction_notes": {"distro": "", "package_versions": "", "font_versions": "", "commands": ""}
}
```

## 题面特殊约定

- 宽表跨页、列宽对齐、合并单元格、图表位置约束都要避免溢出裁切；**不靠缩放掩盖问题**（不用 `\resizebox`/`\scalebox` 硬压，改用 `tabularx`/`p{}` 列宽或拆表）。
- 多行公式用 `align` 且每个带号公式一个 `\label`，正文用 `\eqref` 引用；编号连续、无 multiply defined。
- 引用必须多遍编译收敛：`\ref`/`\cite` 全部解析，日志无 `Rerun`、无 undefined。
- 交付物是**可继续编辑的源码 + 真实产物**，不能用 PDF 或截图顶替源码，也不能给编译不过我片段。

## 资源与依赖

- `scripts/latexkit.py`（标准库，调用本机 TeX 引擎）；`scripts/serialize_result.py`（标准库）。
- `resources/output_contract.json`、`resources/conventions.md`、`templates/template_required.json`、`examples/`（标注示例）。
- 编译需要本机 TeX 发行版（TeX Live/MiKTeX）；引擎缺失时 `build.status=engine_unavailable`，如实记录，不伪造成功。

## 限制与失败处理

- 材料不足或冲突无法判定 → `status=undetermined` 并在 `uncertainty` 说明原因与待确认项。
- 引擎缺失、宏包缺失、字体不可用 → 记录异常、可人工接管位置与替代建议，状态降为 `partial`。
- 体积约束：≤50 个 UTF-8 文本文件，单文件 ≤500 KB，总量 ≤2 MB，无符号链接。
