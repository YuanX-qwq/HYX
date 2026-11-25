# 通用工作规范 · latex-writing-compilation

## 1. 读真实输入
- 输入在 `/input/case.json` 与 `task.md`；源码目录按题面给定。先读真实文件，不按标签猜内容。
- `case_id` 原样写入 `result.json`，不改写、不编造。

## 2. 证据与回链
- 每条关键结论回指到源码位置：文件 + 行号（编译诊断）或 log 中的 `Overfull \hbox` 行段。
- 区分「静态诊断推断」与「编译实测」：LIST 里 `source=lint` 是推断，`source=build` 是实测，两者不可混用。

## 3. 诚实状态
- `build.status` 只有 `success`（rc=0、无错误、无 Overfull）/ `warnings`（能出 PDF 但仍有 Overfull 或未定义引用）/ `failed`（rc≠0）/ `engine_unavailable`（本机无 TeX）。
- 引擎缺失时不得写 `success`，`result.json` 的 `status` 降为 `partial`，并在 `uncertainty` 写清"本机不可编译 + 建议在含 TeX Live 的镜像中重跑"。

## 4. 宽表与版式
- 不靠缩放掩盖问题：禁止用 `\resizebox`/`\scalebox` 把超宽表压进版面；改 `tabularx`+`X`、`p{宽}` 折行，或拆成两表。
- 三线表：`\toprule`/`\midrule`/`\bottomrule`（booktabs），不要混用 `\hline`。
- 浮动体：`[tbp]` 优先于 `[h]`；每个 `table`/`figure` 必须被正文 `\ref` 引用。

## 5. 引用与文献
- `\cite` 键必须与 `.bib` 完全一致；未被引用的条目要么在正文引用，要么删掉。
- 多遍编译直到日志不再出现 `Rerun`/`undefined references`；不收敛就写进 `uncertainty`。

## 6. 产物位置与体积
- 过程放 `/app/work`，最终源码与 PDF/PNG 放 `/app/output`，结构化结果 `/app/output/result.json`。
- Skill 资源 ≤50 个 UTF-8 文本文件，单文件 ≤500 KB，总量 ≤2 MB，无符号链接。
- 二进制产物（PDF/PNG）独立于 JSON 有效性保留，不能只给 base64 或截图代替。

## 7. 禁止事项
- 不提交预制答案、不伪造编译日志、不虚构宏包/字体版本。
- 不在任何输出中回显 API Token。
