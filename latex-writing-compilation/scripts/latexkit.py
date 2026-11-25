#!/usr/bin/env python3
"""latexkit — LaTeX 写作与编译的机械层（仅标准库）。

子命令：
  scan      结构扫描：主文件/子文件/参考文献、preamble 宏包、命令→宏包映射
  lint      静态诊断：宏包缺失、标签/引用/文献对应、宽表、三线表、浮动体
  build     真实编译：多遍收敛、解析 log 的报错与 Overfull，记录发行版/版本/命令
  apply     patches.json 确定性改稿，产出定稿目录
  check     模板必填项与版式约束
  assemble  汇总为 result.json 的 results 部分

用法示例：
  python3 scripts/latexkit.py build --root examples/draft --engine pdflatex --out build.json
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- 常量与映射

# 命令 → 所需宏包（preamble 未加载即为缺包）
CMD_PKG = {
    "toprule": "booktabs", "midrule": "booktabs", "bottomrule": "booktabs",
    "cmidrule": "booktabs", "addlinespace": "booktabs",
    "multirow": "multirow", "makecell": "makecell",
    "textcolor": "xcolor", "colorbox": "xcolor", "definecolor": "xcolor",
    "bm": "bm", "mathbb": "amssymb", "mathcal": "amsmath", "text": "amsmath",
    "boldsymbol": "amsmath", "align": "amsmath", "eqref": "amsmath",
    "SI": "siunitx", "num": "siunitx", "qty": "siunitx",
    "includegraphics": "graphicx", "rotatebox": "graphicx",
    "tabularx": "tabularx", "resizebox": "graphicx",
    "citep": "natbib", "citet": "natbib",
    "href": "hyperref", "url": "hyperref", "autoref": "hyperref",
    "algorithm": "algorithm", "algorithmic": "algorithmic",
    "usepackage": None,
}

ENV_PKG = {
    "tabularx": "tabularx", "tikzpicture": "tikz", "algorithm": "algorithm",
    "algorithmic": "algorithmic", "pspicture": "pstricks",
}

# 报错 → 修复建议（按关键字匹配）
FIX_RULES = [
    (r"Undefined control sequence", "命令未定义：若为 \\toprule/\\multirow/\\textcolor 等，preamble 加载对应宏包"),
    (r"File `(.+?)' not found", "缺少宏包/字体文件：安装对应 TeX 发行版宏包集合，或改用已装宏包"),
    (r"Reference `(.+?)' on page", "交叉引用悬空：标签名与 \\ref 不一致、或 \\label 未写在该环境内"),
    (r"Citation `(.+?)' undefined", "文献键未解析：与 .bib 键拼写不一致，或条目缺失"),
    (r"Missing \\$ inserted", "数学符号出现在文本模式：补 $...$ 或改用 \\(...\\)"),
    (r"Extra alignment tab", "列数多于 tabular 列格式：核对 & 数量与列声明"),
    (r"Misplaced \\noalign", "规则命令位置错误：\\toprule/\\midrule 必须在 tabular 首行或 \\\\ 之后"),
    (r"PGF Math Error: Unknown function", "tikz 库未加载：right=of 等相对定位语法需 \\usetikzlibrary{positioning}"),
    (r"Runaway argument", "花括号未闭合：从报错行向前回溯未配平的花括号"),
    (r"There were undefined references", "引用未收敛：补多一遍编译并核对标签/文献键"),
    (r"Too many unprocessed floats", "浮动体积压：调整 [tbp]、缩短队列或改用 \\clearpage"),
]

ERR_LINE_RE = re.compile(r"^(.+?\.(?:tex|sty|cls|bib)):(\d+):\s*(.+)$")
BANG_RE = re.compile(r"^!\s+(.+)$")
LNNUM_RE = re.compile(r"^l\.(\d+)\s")
OVERFULL_RE = re.compile(
    r"Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\)"
    r"(?: in paragraph at lines (\d+)--(\d+))?"
    r"(?: in alignment at lines (\d+)--(\d+))?"
)
INPUT_RE = re.compile(r"\\(?:input|include|subfile)\{(.+?)\}")
USEPKG_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}")
DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{([^}]*)\}")
LABEL_RE = re.compile(r"\\label\{(.+?)\}")
REF_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref|Cref|cref)\{(.+?)\}")
CITE_RE = re.compile(r"\\(?:cite|citep|citet|citeauthor|citeyear|nocite)\*?(?:\[[^\]]*\])?\{([^}]*)\}")
BIBKEY_RE = re.compile(r"@[A-Za-z]+\{([^,\s]+)\,")
ROW_RE = re.compile(r"\\begin\{(table|figure)\}")


def read(p):
    return Path(p).read_text(encoding="utf-8", errors="replace")


def walk_tex(root):
    return sorted(p for p in Path(root).rglob("*.tex") if "build" not in p.parts)


def rel(p, root):
    return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()


def find_main(root):
    for p in walk_tex(root):
        if DOCCLASS_RE.search(read(p)):
            return p
    return None


def strip_comments(text):
    return re.sub(r"(?<!\\)%.*", "", text)


# ---------------------------------------------------------------- scan

def scan(root):
    root = Path(root).resolve()
    main = find_main(root)
    if not main:
        return {"error": "no \\documentclass found", "root": str(root)}
    files = walk_tex(root)
    main_text = read(main)
    preamble = main_text.split(r"\begin{document}")[0]

    sources, graph = [], {}
    for p in files:
        role = "main" if p == main else "section"
        sources.append({"path": rel(p, root), "role": role})
    # \input / \include 图：父文件 → 子文件（按实际声明解析）
    for p in files:
        for inc in INPUT_RE.findall(strip_comments(read(p))):
            cand = root / inc if inc.endswith(".tex") else root / (inc + ".tex")
            if not cand.exists():
                cand = root / "sections" / (inc if inc.endswith(".tex") else inc + ".tex")
            if cand.exists():
                graph.setdefault(rel(p, root), []).append(rel(cand, root))

    bibs = sorted(rel(b, root) for b in root.rglob("*.bib"))
    for b in bibs:
        sources.append({"path": b, "role": "bibliography"})
    figures = sorted(rel(f, root) for f in root.rglob("*") if f.suffix.lower() in {".pdf", ".png", ".jpg", ".eps"})
    images = [{"path": f, "role": "figure"} for f in figures]
    sources.extend(images)

    packages = []
    for m in USEPKG_RE.finditer(preamble):
        packages.extend(x.strip() for x in m.group(1).split(",") if x.strip())
    docclass = DOCCLASS_RE.search(preamble)

    body = strip_comments(main_text)
    child = "\n".join(strip_comments(read(p)) for p in files if p != main)
    full = body + "\n" + child

    used_cmds = sorted({
        m.group(1) for m in re.finditer(r"\\([A-Za-z@]+)", full)
        if m.group(1) in CMD_PKG and CMD_PKG[m.group(1)]
    })
    used_envs = sorted({e for e in re.findall(r"\\begin\{([A-Za-z*]+)\}", full) if e in ENV_PKG})
    required = sorted({CMD_PKG[c] for c in used_cmds} | {ENV_PKG[e] for e in used_envs})
    missing = [p for p in required if p not in packages]

    labels = collect(full, LABEL_RE)
    ref_list = []
    for m in REF_RE.finditer(full):
        for k in re.findall(r"[^,{}]+", m.group(1)):
            ref_list.append({"key": k.strip(), "line": line_of(full, m.start())})
    cites = []
    for m in CITE_RE.finditer(full):
        for k in m.group(1).split(","):
            if k.strip():
                cites.append({"key": k.strip(), "line": line_of(full, m.start())})

    bib_keys = []
    for b in bibs:
        bib_keys.extend(BIBKEY_RE.findall(read(root / b)))

    return {
        "root": str(root),
        "main": rel(main, root),
        "documentclass": docclass.group(1) if docclass else "",
        "sources": sources,
        "graph": graph,
        "packages": packages,
        "used_commands": used_cmds,
        "required_packages": required,
        "missing_packages": missing,
        "labels": labels,
        "refs": ref_list,
        "cites": cites,
        "bib_keys": sorted(set(bib_keys)),
        "bib_files": bibs,
    }


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def collect(full, regex):
    out = []
    for m in regex.finditer(full):
        out.append({"key": m.group(1), "line": line_of(full, m.start())})
    return out


# ---------------------------------------------------------------- lint

def brace_groups(s):
    """按配平的花括号取出所有顶层分组内容。"""
    out, i = [], 0
    while i < len(s):
        if s[i] == "{":
            depth, j = 0, i
            while j < len(s):
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            out.append(s[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out


def count_cols(spec):
    """展开 *{n}{tok} 后统计列数；忽略 @{}、>{}/<{} 前缀。"""
    cols, i = [], 0
    while i < len(spec):
        ch = spec[i]
        if ch in "lcrXS":
            cols.append(ch)
            i += 1
        elif ch in "pm":
            g = brace_groups(spec[i + 1:])[:1]
            cols.append(ch + "{%s}" % g[0] if g else ch)
            i += 1 + (len(g[0]) + 2 if g else 0)
        elif ch == "*":
            gs = brace_groups(spec[i + 1:])[:2]
            if len(gs) == 2:
                cols.extend(count_cols(gs[1]) * int(gs[0] or 0))
                i += 1 + sum(len(x) + 2 for x in gs)
            else:
                i += 1
        elif ch in "@><":
            g = brace_groups(spec[i + 1:])[:1]
            i += 1 + (len(g[0]) + 2 if g else 0)
        else:
            i += 1
    return cols


def parse_table(block):
    head = re.search(r"\\begin\{(tabularx|tabular|longtable)\*?\}(.*?)\n", block, re.S)
    spec, env = "", ""
    if head:
        env = head.group(1)
        groups = brace_groups(head.group(2))
        spec = groups[1] if (env == "tabularx" and len(groups) >= 2) else (groups[0] if groups else "")
    cols = count_cols(spec) if spec else []
    rows = [r for r in re.split(r"\\\\", block) if "&" in r]
    col_counts = sorted({len(r.split("&")) for r in rows}) if rows else []
    return {"spec": spec, "cols": cols, "n_cols": len(cols), "rows": len(rows),
            "col_counts": col_counts,
            "booktabs": ("\\toprule" in block and "\\bottomrule" in block and "\\midrule" in block),
            "has_label": "\\label{" in block}


def estimate_width_pt(block, tbl, font_pt=10.0):
    """按列数/最长单元格字符数估算表宽（l/c/r 列按字符，p{} 按声明宽度，X 视作 0）。"""
    body = block.split("\\midrule", 1)[1] if "\\midrule" in block else block
    lines = [r.replace("\\hline", "").replace("\\toprule", "").replace("\\midrule", "").replace("\\bottomrule", "")
             .replace("\\", "").strip() for r in re.split(r"\\\\", body)]
    rows_txt = []
    for r in lines:
        if "&" not in r or "\\caption" in r or "begin{tabular" in r or "end{tabular" in r:
            continue
        cells = [c.strip().strip(",") for c in r.split("&")]
        rows_txt.append(cells)
    widths = [0.0] * max(1, tbl["n_cols"] or (max(len(r) for r in rows_txt) if rows_txt else 1))
    for cells in rows_txt:
        for i, c in enumerate(cells):
            if i >= len(widths):
                continue
            w = len(re.sub(r"\\[A-Za-z]+|[{}$]", "", c)) * font_pt * 0.48
            widths[i] = max(widths[i], w)
    fixed = 0.0
    for i, col in enumerate(tbl["cols"]):
        if i >= len(widths):
            break
        if col == "X":
            widths[i] = 0.0
        elif col.startswith("p{") or col.startswith("m{"):
            num = re.search(r"(\d+(?:\.\d+)?)\s*(cm|mm|in|pt|em)", col)
            if num:
                v, u = float(num.group(1)), num.group(2)
                widths[i] = {"cm": v * 28.45, "mm": v * 2.845, "in": v * 72.27, "pt": v, "em": v * font_pt}[u]
        fixed += widths[i]
    return sum(widths)


def lint(root, textwidth_pt=453.0):
    root = Path(root).resolve()
    info = scan(root)
    if "error" in info:
        return {"ok": False, "diagnostics": [{"file": "", "line": 0, "code": "NO_MAIN", "severity": "error",
                                              "message": info["error"], "fix": "确认主文件含 \\documentclass"}]}
    diags = []

    def add(f, line, code, sev, msg, fix):
        diags.append({"file": f, "line": line, "code": code, "severity": sev, "message": msg, "fix": fix})

    # 1) 缺宏包
    for pkg in info["missing_packages"]:
        cmds = [c for c in info["used_commands"] if CMD_PKG.get(c) == pkg]
        hit = None
        for p in walk_tex(root):
            t = read(p)
            for c in cmds:
                m = re.search(r"\\" + c + r"(?![A-Za-z])", t)
                if m:
                    hit = (rel(p, root), line_of(t, m.start()), c)
                    break
            if hit:
                break
        if hit:
            f, ln, c = hit
            add(f, ln, "MISSING_PACKAGE", "error",
                "使用了 \\%s 但 preamble 未加载 %s" % (c, pkg),
                "在 %s 的 preamble 加 \\usepackage{%s}" % (info["main"], pkg))

    # 2) 标签重复 / 悬空引用
    seen = {}
    for lab in info["labels"]:
        seen.setdefault(lab["key"], []).append(lab["line"])
    for k, lines in seen.items():
        if len(lines) > 1:
            add(info["main"], lines[1], "DUP_LABEL", "error", "标签 %s 重复定义" % k,
                "删除或重命名重复的 \\label{%s}（先出现在第 %s 行）" % (k, lines[0]))
    for r in info["refs"]:
        if r["key"] not in seen:
            add(info["main"], r["line"], "UNDEFINED_REF", "error",
                "\\ref/\\eqref{%s} 没有对应 \\label" % r["key"],
                "核对标签名拼写，或在被引对象内补 \\label{%s}" % r["key"])

    # 3) 文献键
    bibset = info["bib_keys"]
    for c in info["cites"]:
        if bibset and c["key"] not in bibset:
            add(info["main"], c["line"], "MISSING_BIB_KEY", "error",
                "\\cite{%s} 在 .bib 中无此键" % c["key"],
                "与 .bib 键对齐（现有：%s）" % ", ".join(bibset[:6]))
    cited = {c["key"] for c in info["cites"]}
    for k in bibset:
        if k not in cited:
            add(info["main"], 0, "UNCITED_BIB", "warn", "文献 %s 未被正文引用" % k,
                "在相关工作处补 \\cite{%s} 或从 .bib 删除" % k)

    # 4) 表格：宽表 / 三线表 / 标签 / 引用
    refkeys = {r["key"] for r in info["refs"]}
    for p in walk_tex(root):
        t = read(p)
        f = rel(p, root)
        for m in re.finditer(r"\\begin\{(table|longtable)\*?\}(.*?)\\end\{\1\*?\}", t, re.S):
            block = m.group(0)
            line = line_of(t, m.start())
            if "tabular" not in block:
                continue
            tbl = parse_table(block)
            w = estimate_width_pt(block, tbl)
            if w > textwidth_pt:
                add(f, line, "WIDE_TABLE", "error",
                    "表宽估算 %.0fpt > 文本宽 %.0fpt（%d 列）" % (w, textwidth_pt, tbl["n_cols"]),
                    "改用 tabularx + X 列或 p{宽度} 折行，或拆表；不要用 resizebox 硬压")
            elif w > 0.92 * textwidth_pt:
                add(f, line, "WIDE_TABLE", "warn",
                    "表宽接近文本宽（%.0f/%.0fpt）" % (w, textwidth_pt), "预留列间距余量或改 X 列")
            if tbl["n_cols"] >= 4 and not tbl["booktabs"]:
                add(f, line, "NOT_THREE_LINE", "warn", "多列表未使用 booktabs 三线表",
                    "补 \\toprule/\\midrule/\\bottomrule")
            if tbl["col_counts"] and max(tbl["col_counts"]) > tbl["n_cols"] and tbl["n_cols"]:
                add(f, line, "COLUMN_MISMATCH", "error",
                    "行内 & 数（%d）多于列声明（%d）" % (max(tbl["col_counts"]), tbl["n_cols"]),
                    "补列声明或删多余 &")
            lab = LABEL_RE.search(block)
            key = lab.group(1) if lab else ""
            if not key:
                add(f, line, "UNLABELED_TABLE", "warn", "表无 \\label", "补 \\label{tab:...}")
            elif key not in refkeys:
                add(f, line, "FLOAT_NOT_REFERENCED", "warn", "表 %s 未被正文引用" % key,
                    "在正文补 \\ref{%s}" % key)

        for m in re.finditer(r"\\begin\{(figure)\*?\}(.*?)\\end\{\1\*?\}", t, re.S):
            block = m.group(0)
            line = line_of(t, m.start())
            lab = LABEL_RE.search(block)
            key = lab.group(1) if lab else ""
            if key and key not in refkeys:
                add(f, line, "FLOAT_NOT_REFERENCED", "warn", "图 %s 未被正文引用" % key,
                    "在正文补 \\ref{%s}" % key)
            if re.search(r"\\begin\{figure\}\[h\]", block):
                add(f, line, "FLOAT_PLACEMENT", "warn", "只用 [h] 易被挤走或裁切",
                    "改为 [tbp] 或在 \\clearpage 后放置")

        # 公式：align 内每个编号行应有 label，且 label 在 $*$ 环境内
        for m in re.finditer(r"\\begin\{(align|equation|gather)\*?\}(.*?)\\end\{\1\*?\}", t, re.S):
            env, block = m.group(1), m.group(0)
            line = line_of(t, m.start())
            if env.endswith("*") is False and "\\begin{%s*}" % env in block:
                continue
            numbered_rows = len([r for r in re.split(r"\\\\", block) if re.search(r"[^\\]\S", r)]) if env == "align" else 1
            labs = LABEL_RE.findall(block)
            if env in ("align", "gather") and numbered_rows > 1 and len(labs) == 0:
                add(f, line, "EQ_UNLABELED", "warn", "多行公式无 \\label，正文无法 \\eqref",
                    "为需引用的行补 \\label{eq:...}")
            elif env in ("align", "gather") and len(labs) > len([r for r in re.split(r"\\\\", block) if "\\nonumber" not in r]):
                add(f, line, "EQ_LABEL_COUNT", "warn", "标签数多于编号行", "删除多余 \\label 或去掉 \\nonumber")

    errors = [d for d in diags if d["severity"] == "error"]
    return {"ok": not errors, "diagnostics": diags,
            "counts": {"error": len(errors), "warn": len(diags) - len(errors)},
            "scan": {k: info[k] for k in ("main", "documentclass", "sources", "packages",
                                          "missing_packages", "labels", "bib_keys", "graph")}}


# ---------------------------------------------------------------- build

def engine_available(engine):
    return shutil.which(engine) is not None


def distro_info(engine):
    if not engine_available(engine):
        return "", ""
    try:
        v = subprocess.run([engine, "--version"], capture_output=True, text=True, timeout=20).stdout
        first = v.strip().splitlines()[0] if v.strip() else ""
    except Exception:
        first = ""
    osinfo = ""
    try:
        p = Path("/etc/os-release")
        if p.exists():
            d = dict(l.split("=", 1) for l in read(p).splitlines() if "=" in l)
            osinfo = d.get("PRETTY_NAME", "").strip('"')
    except Exception:
        osinfo = ""
    return first, osinfo


def pkg_versions(packages):
    out = []
    for pkg in packages:
        try:
            f = subprocess.run(["kpsewhich", pkg + ".sty"], capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            f = ""
        ver = ""
        if f and Path(f).exists():
            head = read(f)[:4000]
            m = re.search(r"\\ProvidesPackage\{\s*" + re.escape(pkg) + r"\s*\}\s*\[([^\]]+)\]", head)
            ver = m.group(1).strip() if m else ""
        out.append({"package": pkg, "version": ver or "unknown"})
    return out


def font_versions(pdf):
    try:
        r = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, timeout=20)
        return r.stdout.strip()[:2000] if r.returncode == 0 else ""
    except Exception:
        return ""


def parse_log(log, root, main):
    root = Path(root)
    errors, overfull, cur_file = [], [], main
    lines = log.splitlines()
    for i, raw in enumerate(lines):
        m = ERR_LINE_RE.match(raw)
        if m:
            f, ln, msg = m.group(1).lstrip("./"), int(m.group(2)), m.group(3).strip()
            if f.endswith((".tex", ".sty", ".cls", ".bib")):
                errors.append({"file": f, "line": ln, "cause": msg, "fix": fix_for(msg, raw, lines, i)})
                cur_file = f
                continue
        m = BANG_RE.match(raw)
        if m:
            msg = m.group(1).strip()
            ln = 0
            for j in range(i, min(i + 6, len(lines))):
                mm = LNNUM_RE.match(lines[j])
                if mm:
                    ln = int(mm.group(1))
                    break
            errors.append({"file": cur_file, "line": ln, "cause": msg, "fix": fix_for(msg, raw, lines, i)})
        m = OVERFULL_RE.search(raw)
        if m:
            too = float(m.group(1))
            a = int(m.group(2) or m.group(4) or 0)
            b = int(m.group(3) or m.group(5) or 0)
            overfull.append({"file": cur_file, "line": a, "end_line": b, "too_wide_pt": too,
                             "cause": "Overfull \\hbox %.1fpt too wide" % too})
    return errors, overfull


def fix_for(msg, raw, lines, i):
    ctx = "\n".join(lines[max(0, i - 2):i + 3])
    for pat, fix in FIX_RULES:
        m = re.search(pat, msg) or re.search(pat, ctx)
        if m:
            if m.groups():
                return fix + "（对象：%s）" % m.group(1)
            return fix
    return "按 log 上下文定位该行并修正"


def build(root, engine="pdflatex", max_passes=3, take_pdf=True):
    root = Path(root).resolve()
    main = find_main(root)
    if not main:
        return {"status": "no_main", "engine": engine, "errors": [], "passes": 0}
    outdir = root / "build"
    outdir.mkdir(exist_ok=True)
    if not engine_available(engine):
        return {"status": "engine_unavailable", "engine": engine, "passes": 0, "errors": [],
                "bibtex_runs": 0, "converged": False,
                "logs": "%s not found on PATH" % engine,
                "note": "本机未安装 TeX 发行版：无法给出编译结论，不伪造成功",
                "distro": "", "distro_os": "", "commands": ""}

    cmd = [engine, "-interaction=nonstopmode", "-file-line-error", "-output-directory", str(outdir), main.name]
    passes, log, rc, bibtex_runs = 0, "", 1, 0
    commands = []
    converged = False
    while passes < max_passes:
        passes += 1
        commands.append("%s -interaction=nonstopmode -file-line-error -output-directory build %s" % (engine, main.name))
        r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=600)
        rc = r.returncode
        log = (r.stdout or "") + (r.stderr or "")
        (outdir / (main.stem + ".log")).write_text(log, encoding="utf-8", errors="replace")
        undef_cit = bool(re.search(r"Citation .+ undefined|There were undefined citations", log))
        undef_ref = bool(re.search(r"Reference .+ undefined|There were undefined references|Rerun to get", log))
        converged = not (undef_cit or undef_ref)
        if rc != 0 and not (undef_cit or undef_ref):
            break
        if undef_cit and bibtex_runs == 0 and shutil.which("bibtex"):
            bx = subprocess.run(["bibtex", main.stem], cwd=str(root), capture_output=True, text=True, timeout=120)
            bibtex_runs += 1
            commands.append("bibtex %s" % main.stem)
            (outdir / (main.stem + ".blg")).write_text((bx.stdout or "") + (bx.stderr or ""),
                                                      encoding="utf-8", errors="replace")
            continue
        if converged:
            break

    errors, overfull = parse_log(log, root, rel(main, root))
    pdf = outdir / (main.stem + ".pdf")
    if rc != 0:
        status = "failed"
    elif errors or overfull or not converged:
        status = "warnings"
    else:
        status = "success"
    first, osinfo = distro_info(engine)
    info = scan(root)
    pkgv = pkg_versions(info.get("packages", [])[:12])
    return {
        "status": status, "engine": engine, "passes": passes, "exit_code": rc,
        "bibtex_runs": bibtex_runs, "converged": converged,
        "errors": errors[:20], "overfull": overfull[:20],
        "logs": log[-4000:],
        "pdf": str(pdf) if pdf.exists() else "",
        "distro": first, "distro_os": osinfo,
        "package_versions": pkgv,
        "font_versions": font_versions(pdf) if pdf.exists() else "",
        "commands": "; ".join(commands),
    }


# ---------------------------------------------------------------- apply

def apply_patches(src, patches_path, dest):
    src, dest = Path(src).resolve(), Path(dest).resolve()
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("build", "*.aux", "*.log", "*.pdf", "*.png"))
    patches = json.loads(read(patches_path))
    items = patches["patches"] if isinstance(patches, dict) else patches
    applied, failed = [], []
    for p in items:
        f = dest / p["file"]
        if not f.exists():
            failed.append({"file": p["file"], "reason": "file not found", "reason_label": p.get("reason", "")})
            continue
        t = read(f)
        n = t.count(p["find"])
        if n != 1:
            failed.append({"file": p["file"], "reason": "find matched %d times" % n,
                           "reason_label": p.get("reason", "")})
            continue
        f.write_text(t.replace(p["find"], p["replace"]), encoding="utf-8")
        applied.append({"file": p["file"], "reason": p.get("reason", ""), "code": p.get("code", "")})
    return {"dest": str(dest), "applied": applied, "failed": failed,
            "ok": not failed and bool(applied)}


# ---------------------------------------------------------------- check

def check(root, template_path=None, build_json=None, overfull_tol=5.0):
    root = Path(root).resolve()
    req = {"required_fields": [], "entries": []}
    if template_path and Path(template_path).exists():
        t = json.loads(read(template_path))
        req = t
    main = find_main(root)
    full = "\n".join(strip_comments(read(p)) for p in walk_tex(root)) if main else ""
    present, missing = [], []
    for e in req.get("entries", []):
        ok = bool(re.search(e["regex"], full))
        (present if ok else missing).append({"field": e["field"], "regex": e["regex"]})
    layout_ok = True
    notes = []
    b = json.loads(read(build_json)) if build_json and Path(build_json).exists() else None
    if b:
        over = [o for o in b.get("overfull", []) if o.get("too_wide_pt", 0) > overfull_tol]
        if over:
            layout_ok = False
            notes.append("%d 处 Overfull > %.1fpt（文字被挤出边界）" % (len(over), overfull_tol))
        if b.get("status") not in ("success",):
            layout_ok = False
            notes.append("build.status=%s" % b.get("status"))
    l = lint(root)
    errs = l["counts"]["error"]
    if errs:
        layout_ok = False
        notes.append("静态诊断仍有 %d 个 error" % errs)
    return {"required_fields": [x["field"] for x in present],
            "missing_fields": [x["field"] for x in missing],
            "layout_ok": layout_ok, "notes": notes}


def assemble(case_path, struct, lint_res, build_res, tpl):
    case = json.loads(read(case_path)) if Path(case_path).exists() else {}
    b = build_res or {}
    return {
        "latex_sources": struct.get("sources", []),
        "build": {
            "engine": b.get("engine", ""),
            "passes": str(b.get("passes", "")),
            "status": b.get("status", ""),
            "logs": (b.get("logs", "") or "")[-1200:],
            "errors": [{"file": e["file"], "line": str(e["line"]), "cause": e["cause"], "fix": e["fix"]}
                       for e in b.get("errors", [])],
        },
        "artifacts": [{"path": p, "type": "pdf" if p.endswith(".pdf") else "source"} for p in
                      ([b.get("pdf")] if b.get("pdf") else [])],
        "template_compliance": {"required_fields": tpl.get("required_fields", []),
                                "layout_ok": bool(tpl.get("layout_ok", False))},
        "reproduction_notes": {
            "distro": ("%s; %s" % (b.get("distro", ""), b.get("distro_os", ""))).strip("; "),
            "package_versions": "; ".join("%s %s" % (p["package"], p["version"]) for p in b.get("package_versions", []))[:600],
            "font_versions": (b.get("font_versions", "") or "").replace("\n", " | ")[:600],
            "commands": b.get("commands", ""),
        },
    }


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description="LaTeX writing & compilation kit")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan"); s.add_argument("--root", required=True); s.add_argument("--out")
    l = sub.add_parser("lint"); l.add_argument("--root", required=True); l.add_argument("--textwidth-pt", type=float, default=453.0); l.add_argument("--out")
    b = sub.add_parser("build"); b.add_argument("--root", required=True); b.add_argument("--engine", default="pdflatex")
    b.add_argument("--max-passes", type=int, default=3); b.add_argument("--out")
    a = sub.add_parser("apply"); a.add_argument("--root", required=True); a.add_argument("--patches", required=True); a.add_argument("--dest", required=True); a.add_argument("--out")
    c = sub.add_parser("check"); c.add_argument("--root", required=True); c.add_argument("--template"); c.add_argument("--build-json"); c.add_argument("--out")
    m = sub.add_parser("assemble"); m.add_argument("--case", required=True); m.add_argument("--struct", required=True)
    m.add_argument("--lint", dest="lint_json", required=True); m.add_argument("--build", dest="build_json", required=True)
    m.add_argument("--tpl", required=True); m.add_argument("--out", required=True)

    args = ap.parse_args(argv)

    if args.cmd == "scan":
        res = scan(args.root)
    elif args.cmd == "lint":
        res = lint(args.root, args.textwidth_pt)
    elif args.cmd == "build":
        res = build(args.root, args.engine, args.max_passes)
    elif args.cmd == "apply":
        res = apply_patches(args.root, args.patches, args.dest)
    elif args.cmd == "check":
        res = check(args.root, args.template, args.build_json)
    else:
        struct = json.loads(read(args.struct))
        lint_res = json.loads(read(args.lint_json))
        build_res = json.loads(read(args.build_json))
        tpl = json.loads(read(args.tpl))
        res = assemble(args.case, struct, lint_res, build_res, tpl)

    out = getattr(args, "out", None)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", out)
    else:
        print(json.dumps(res, ensure_ascii=False, indent=2)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
