# Task · LaTeX writing and compilation (EXAMPLE)

> 示例任务书（EXAMPLE ONLY），用于演示输入形状与约束，不是任何正式案例的答案。

## 1. 任务

`examples/draft/` 是一篇投稿论文的 LaTeX 源码（`main.tex` + `sections/*.tex` + `refs.bib`）。
它现在编译不过、部分交叉引用和文献键对不上、有一张表超出正文宽度。请把它修到能编译、能交付：

1. 源码结构与宏包：preamble 加载正文真正用到的宏包，不留缺失命令。
2. 数学公式：多行公式用 `align`，每个需引用的编号行有且仅有一个 `\label`，正文用 `\eqref` 引用。
3. 表格：宽表用 `tabularx` + `X` 列或 `p{宽}` 折行，**不得用 `\resizebox`/`\scalebox` 硬压**；采用 booktabs 三线表。
4. 引用与文献：`\cite` 键与 `refs.bib` 完全一致，无悬空引用，多遍编译收敛。
5. 浮动体：`[tbp]` 放置，图表都要在正文被 `\ref` 引用。
6. 模板适配与可重复构建：给出发行版、宏包与字体版本、引擎、遍数与命令。

## 2. 验收

- 在 `pdflatex` 下 **≤3 遍**编译成功，日志无 `Rerun`、无 undefined references/citations。
- 无 `Overfull \hbox`（>5pt）导致的裁切；宽表不被缩放掩盖。
- 交付**可编辑源码 + 真实 PDF + 构建记录**三者齐全；不能在 PDF 之后手工改图。
- `result.json` 的 `build.errors` 必须来自真实 log，每条给 `file/line/cause/fix`。

## 3. 证据要求

每条结论回指源码位置或 log 行段；不可编译、宏包缺失等限制写进 `uncertainty`，不得伪造成功。
