#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 文档解析 Skill 自测

两个层次:
  A. 纯 Python 版面逻辑测试（fixture，无第三方依赖，永远运行）:
     多栏检测、band-walk 阅读顺序、页眉页脚分离、段落续接、
     章节/方程/表格/参考文献识别、证据引文检索。
  B. 真实 PDF 端到端（可选，需 pdflatex 与任一后端）:
     生成合成双栏 PDF -> 解析 -> 校验关键不变量。

用法:
  python3 tests/selftest.py [--workdir DIR] [--latex] [--no-real-pdf]
退出码 0 = 全部通过；1 = 有失败。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

import pdftool  # noqa: E402
from pdftool import (Block, Word, Line, words_to_lines, lines_to_blocks,  # noqa: E402
                     detect_columns, band_order, zone_of_block,
                     classify_headers_footers, is_heading, is_display_equation,
                     locate_quote, merge_continuations, norm_for_search)

RESULTS = []
FAILURES = []


def check(name, cond, detail=""):
    RESULTS.append({"name": name, "pass": bool(cond), "detail": str(detail)})
    if not cond:
        FAILURES.append(name)
    return bool(cond)


def make_block(page, text, x0, y0, x1, y1, size=10.0, bold=False):
    b = Block(page, "paragraph", text=text, bbox=[x0, y0, x1, y1])
    b.size = size
    b.bold = bold
    return b


def test_layout_logic():
    """A. fixture 逻辑测试"""
    pw, ph = 612.0, 792.0
    # 模拟一个双栏页面（正文 54..558，栏间隙 ~20pt）
    blocks = [
        make_block(1, "Journal of Synthetic Science 12 (2024) 1-9", 54, 30, 558, 44, 8.0),   # 页眉
        make_block(1, "A Synthetic Paper Title for Parsing Tests", 54, 60, 558, 84, 18.0, True),  # 标题(full)
        make_block(1, "Abstract. This paper presents a synthetic method.", 54, 92, 558, 108),  # 摘要(full)
        make_block(1, "1. Introduction", 54, 118, 200, 130, 12.0, True),
        make_block(1, "Multi-column documents are common in scientific literature and pose reading order challenges.", 54, 136, 300, 160),
        make_block(1, "We propose a band-walk algorithm that stitches columns without mixing lines.", 54, 164, 300, 188),
        make_block(1, "2. Methods", 320, 118, 420, 130, 12.0, True),
        make_block(1, "The parser projects word boxes onto the horizontal axis to find column gaps.", 320, 136, 558, 160),
        make_block(1, "Reading order follows vertical bands sorted by column index and x0.", 320, 164, 558, 188),
        make_block(1, "The pipeline keeps verbatim text and anchors every block to its page and bbox.", 320, 192, 558, 216),
        make_block(1, "Tables are rebuilt as grids with column alignment and repeated headers.", 320, 220, 558, 244),
        make_block(1, "E = mc2", 140, 230, 230, 242),  # 居中方程（栏内）
        make_block(1, "(1)", 255, 230, 295, 242),      # 方程编号（右对齐到栏右缘）
        make_block(1, "Fig. 1. Synthetic architecture overview.", 320, 260, 558, 274, 10.0, True),
        make_block(1, "Table 1. Synthetic results", 54, 280, 260, 292, 11.0, False),
        make_block(1, "Method  A  B  C", 54, 298, 300, 310),
        make_block(1, "alpha  1  2  3", 54, 314, 300, 326),
        make_block(1, "beta   4  5  6", 54, 330, 300, 342),
        make_block(1, "3. Conclusion", 54, 420, 160, 432, 12.0, True),
        make_block(1, "The method parses two-column papers correctly.", 54, 438, 300, 450),
        make_block(1, "References", 54, 480, 130, 492, 12.0, True),
        make_block(1, "[1] A. Author, A synthetic citation, J. Synth. 1 (2024) 1-9.", 54, 498, 540, 512),
        make_block(1, "1Supported by the synthetic fund.", 54, 700, 200, 714),  # 脚注
        make_block(1, "Page 1", 290, 766, 330, 778),  # 页脚
    ]
    # 页眉页脚（第 2 页近似重复以触发持续性判定）
    pages = [blocks, [
        make_block(2, "Journal of Synthetic Science 12 (2024) 1-9", 54, 30, 558, 44, 8.0),
        make_block(2, "Some body text on page two.", 54, 100, 300, 114),
        make_block(2, "More body text continuing the discussion", 320, 100, 558, 114),
        make_block(2, "Page 2", 290, 766, 330, 778),
    ]]
    hdrs, ftrs = classify_headers_footers(pages, ph)
    check("header_classified", any(b.text.startswith("Journal of Synthetic") for b in hdrs),
          "页眉跨页重复被识别")
    check("footer_classified", any("Page 1" in b.text or "Page 2" in b.text for b in ftrs),
          "页码被识别为页脚")

    body = [b for b in blocks if b.zone != "header" and b.zone != "footer"]
    text_x0, text_x1 = pdftool.detect_text_width(body, pw)
    span = max(text_x1 - text_x0, 1.0)
    narrow = []
    for b in body:
        if (b.bbox[2] - b.bbox[0]) > 0.6 * span:
            b.zone = "full"
        else:
            narrow.append(b)
    ncols, col_bboxes, conf = detect_columns(narrow, pw, text_x0, text_x1)
    check("two_columns_detected", ncols == 2, "ncols=%d conf=%.2f" % (ncols, conf))
    for b in body:
        if b.zone != "full":
            b.zone = zone_of_block(b, pw, ph, text_x0, text_x1, ncols, col_bboxes)
    order = band_order(body)
    # 先分类、后合并（与真实流程一致，避免把标题/方程/表格并入上一段）
    med = 10.0

    def classify(b, l0, l1):
        if is_heading(b, med, l0, l1)[0]:
            b.kind = "heading"
        elif pdftool.EQ_NUM_RE.match(b.text.strip()) and (l1 - b.bbox[2]) <= 14:
            b.kind = "equation_number"
        elif is_display_equation(b, l0, l1):
            b.kind = "equation"
        else:
            b.kind = "paragraph"

    for b in order:
        l0, l1 = pdftool.col_range(b, text_x0, text_x1, col_bboxes)
        classify(b, l0, l1)
    order = merge_continuations(order)
    texts = [b.text for b in order]
    # 标题在摘要前；左栏 Intro 在右栏 Methods 前（同一 band）
    check("title_first", texts[0].startswith("A Synthetic Paper Title"),
          "标题块排最前: %s" % texts[0][:40])
    i_intro = next(i for i, t in enumerate(texts) if t.startswith("1. Introduction"))
    i_methods = next(i for i, t in enumerate(texts) if t.startswith("2. Methods"))
    check("band_order_left_before_right", i_intro < i_methods,
          "同一带内左栏先于右栏: %d < %d" % (i_intro, i_methods))
    # 段落续接单元测试（跨栏/同带）
    p1 = make_block(1, "The algorithm stitches columns", 54, 100, 300, 112)
    p1.zone = "col-1"
    p2 = make_block(1, "without mixing lines.", 320, 100, 558, 112)
    p2.zone = "col-2"
    merged = merge_continuations([p1, p2])
    check("continuation_cross_column_merged",
          len(merged) == 1 and "stitches columns without mixing lines." in merged[0].text,
          merged[0].text if merged else "EMPTY")
    q1 = make_block(1, "First column text", 54, 120, 300, 132)
    q1.zone = "col-1"
    q2 = make_block(1, "Second column text.", 320, 120, 558, 132)
    q2.zone = "col-2"
    q3 = make_block(1, "More first column.", 54, 136, 300, 148)
    q3.zone = "col-1"
    out3 = merge_continuations([q1, q2, q3])
    check("continuation_no_false_merge", len(out3) == 3,
          "同带相邻栏普通段不被拼成一句: %d 块" % len(out3))
    r1 = make_block(1, "The list follows", 54, 150, 300, 162)
    r1.zone = "col-1"
    r2 = make_block(1, "1) alpha", 320, 150, 420, 162)
    r2.zone = "col-2"
    outr = merge_continuations([r1, r2])
    check("continuation_list_guard", len(outr) == 2, "列表标记块不被并入上段")

    # 结构识别断言（kind 已在合并前赋好）
    headings = [b for b in order if b.kind == "heading"]
    check("headings_found", len(headings) >= 3,
          "标题数=%d: %s" % (len(headings), [h.text[:20] for h in headings]))
    eqs = [b for b in order if b.kind == "equation"]
    check("equation_found", any("E = mc" in b.text for b in eqs),
          "方程: %s" % [b.text[:12] for b in eqs])
    eqnum = [b for b in order if b.kind == "equation_number"]
    check("equation_number_found", len(eqnum) == 1, "编号行=%s" % [b.text for b in eqnum])

    # 表格启发式：直接构造词级行测 table_grid
    def mkline(text, x0, y0):
        words = []
        parts = text.split()
        w = 8.0
        for i, p in enumerate(parts):
            x = x0 + i * 90.0
            words.append(Word(p, x, y0, x + 6.0 * len(p), y0 + 10.0))
        return Line(words)

    tlines = [mkline("Method A B C", 54, 232),
              mkline("alpha 1 2 3", 54, 248),
              mkline("beta 4 5 6", 54, 264)]
    grid, col_x = pdftool.table_grid_from_lines(tlines)
    check("table_grid_3cols", len(col_x) >= 3 and len(grid) >= 3,
          "列数=%d 行数=%d" % (len(col_x), len(grid)))
    check("table_grid_cells", grid[0][0] == "Method" and grid[1][0] == "alpha",
          "单元格归属: %s / %s" % (grid[0][:3], grid[1][:3]))

    # 参考文献
    refs = [b for b in order if pdftool.REF_ITEM_RE.match(b.text.strip())]
    check("reference_item_found", len(refs) == 1, str([r.text[:20] for r in refs]))

    # 证据检索
    doc_model = {
        "pages": [{
            "page": 1,
            "blocks": [{"id": "p1b1", "kind": "paragraph", "zone": "col-1",
                        "page": 1, "bbox": [54, 136, 300, 160],
                        "text": "Multi-column documents are common in scientific "
                                "literature and pose reading order challenges."}]
        }]
    }
    hits = locate_quote(doc_model, "reading order challenges")
    check("quote_located", len(hits) == 1 and hits[0]["page"] == 1,
          "命中=%d" % len(hits))


LATEX_TEX = r"""
\documentclass[10pt,twocolumn]{article}
\usepackage[a4paper,margin=2cm]{geometry}
\usepackage{fancyhdr}
\usepackage{amsmath}
\pagestyle{fancy}
\fancyhead[L]{Journal of Synthetic Science}
\fancyhead[R]{Vol. 12, No. 4}
\fancyfoot[C]{\thepage}
\title{A Synthetic Two-Column Paper for Parser Validation}
\author{Test Author and Co Author}
\date{2024}
\begin{document}
\maketitle
\thispagestyle{fancy}
\begin{abstract}
This synthetic paper validates multi-column reading order, section hierarchy,
table parsing and equation extraction. The parser must not mix column text.
\end{abstract}
\section{Introduction}
Two-column layouts are widely used in scientific journals. Naive text extraction
often interleaves the left and right columns, producing unreadable text. Our
pipeline restores the original reading order using a band-walk algorithm.
Section detection uses both numbering patterns and typographic signals such as
font size and boldness, so that unnumbered headings are not lost.
\section{Methods}
The parser projects word boxes onto the horizontal axis, finds column gaps, and
orders blocks by vertical bands. Evidence anchors record page and bounding box
for every structural element so results can be verified against the original.
Table rows are grouped by column alignment and cross-page tables are merged
when repeated headers match.
\begin{equation}
E = m c^{2}
\label{eq:energy}
\end{equation}
The energy equation relates mass and the speed of light. Greek letters such as
$\alpha$, $\beta$ and $\gamma$ must survive extraction without distortion.
Subscripts such as $x_{i}$ and superscripts such as $10^{3}$ are marked in the
structured output instead of being silently flattened.
\begin{table}[h]
\centering
\begin{tabular}{lcc}
\hline
Method & Precision & Recall \\
\hline
Baseline & 0.61 & 0.58 \\
Ours & 0.93 & 0.91 \\
\hline
\end{tabular}
\caption{Synthetic evaluation results.}
\label{tab:results}
\end{table}
\section{Results}
The proposed pipeline correctly restores the reading order on the synthetic
document. Paragraph breaks are detected from vertical gaps and first-line
indents, and running headers are separated from body text by their repetition
across pages. Footnotes are anchored to the bottom of the page and references
are extracted as numbered items.
\section{Discussion}
The main limitation is the reliance on a text layer. Scanned pages are handled
by rendering followed by OCR with per-word confidence, and unreadable words are
marked honestly rather than guessed. Encrypted documents are refused with a
clear reason unless an empty password opens them.
\section{Conclusion}
The parser handles two-column scientific PDFs and anchors every claim back to
the original page and block. Future work includes image-only tables and
equation re-typesetting through the LaTeX compiler.
\section{Related Work}
Prior extraction tools either ignore layout geometry or rely on fragile
heuristics. Raster-only pipelines lose glyph fidelity, while naive text dumps
interleave columns and break reading order. Our approach keeps a deterministic
geometry layer and lets the language model consume a faithful reconstruction.
The following paragraphs add volume so that the document spans two pages, which
is required to exercise running-header detection and cross-page continuation.
Several design decisions deserve emphasis. First, verbatim fidelity: no Unicode
normalization is applied that would collapse distinct glyphs such as the minus
sign, the en dash and the em dash. Second, honesty: content that cannot be read
is marked as unreadable instead of being filled in with plausible text. Third,
verifiability: every extracted element carries a page and bounding-box anchor
so that a claim can be traced back to the exact region of the original file.
\section{Extended Evaluation}
We evaluate the parser on documents with one, two and three columns, with and
without running headers, with floating tables and with display equations. The
error metric is the edit distance between the reconstructed reading order and
the order a human would read. Column stitching reduces the error by an order of
magnitude compared with naive y-then-x sorting. Table grids are compared cell
by cell, and equation fidelity is measured character by character including
superscripts, subscripts and Greek letters. OCR pages are scored with word
confidence so low-quality regions are flagged instead of silently corrupted.
The evaluation harness records the backend that produced each block, making the
provenance of every character auditable. This property matters for scientific
verification, where a reviewer must be able to distinguish extracted text from
inferred text. All synthetic fixtures used for local self-testing are generated
by this script itself, so the test suite has no hidden dependencies and can be
re-run on any machine with a LaTeX installation and one PDF backend.
\section{Appendix Notes}
Running headers are detected by their repetition across pages. A line that
appears at the top of most pages is a header even when its style matches the
body text. Page numbers are recognized by pattern and position. Footnotes are
anchored to the bottom zone and marked with their marker character. References
are extracted after the bibliography heading and each item keeps its number.
These small rules accumulate into a document model that supports citation and
re-checking, which is the core requirement of literature parsing challenges.
\begin{thebibliography}{9}
\bibitem{ref1} A. Author, A synthetic citation, J. Synth. Sci. 1 (2024) 1--9.
\bibitem{ref2} B. Writer, Another synthetic citation, Proc. Synth. 2 (2023) 10--19.
\bibitem{ref3} C. Scribe, Yet another citation, Acta Synth. 3 (2022) 20--29.
\end{thebibliography}
\end{document}
"""


def test_real_pdf(workdir):
    """B. 真实 PDF 端到端（需要 pdflatex 与任一后端）"""
    if shutil.which("pdflatex") is None:
        RESULTS.append({"name": "real_pdf_e2e", "pass": None,
                        "detail": "skipped: no pdflatex"})
        return
    tex = os.path.join(workdir, "synthetic.tex")
    with open(tex, "w", encoding="utf-8") as f:
        f.write(LATEX_TEX)
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                        "synthetic.tex"], cwd=workdir, capture_output=True,
                       text=True, timeout=120)
    pdf = os.path.join(workdir, "synthetic.pdf")
    if r.returncode != 0 or not os.path.exists(pdf):
        check("real_pdf_generated", False, r.stdout[-400:] if r.stdout else "no pdf")
        return
    check("real_pdf_generated", True, "")
    try:
        parser = pdftool.Parser(pdf, workdir=workdir)
        document = parser.parse()
    except Exception as e:
        check("real_pdf_parsed", False, str(e))
        return
    check("real_pdf_parsed", True, "backend=%s pages=%s" % (
        document["source"]["backend"], document["source"]["pages"]))
    check("real_pdf_pages_ge_2", document["source"]["pages"] >= 2)
    sects = [s["title"] for s in document.get("sections", [])]
    check("real_pdf_sections", any("Introduction" in s for s in sects), str(sects[:6]))
    check("real_pdf_equation",
          any("mc2" in pdftool.norm_for_search(e.get("text", ""))
              for e in document.get("equations", [])),
          "方程包含 E = m c^2: %s" % [e.get("text", "")[:40] for e in document.get("equations", [])])
    check("real_pdf_references", len(document.get("references", [])) >= 1,
          "参考文献 %d 条" % len(document.get("references", [])))
    # 页眉检测（fancyhdr 跨页重复；行内多空格不影响匹配）
    hdrs = [b.get("text", "") for p in document["pages"] for b in p.get("header", [])]
    check("real_pdf_header_detected",
          any("JournalofSynthetic" in pdftool.norm_for_search(h) for h in hdrs),
          "页眉: %s" % hdrs[:2])
    # 阅读顺序中不得出现明显串栏（Methods 标题应在 Introduction 之后）
    all_text = "\n".join(b.get("text", "") for p in document["pages"] for b in p.get("blocks", []))
    i_intro = all_text.find("Introduction")
    i_methods = all_text.find("Methods")
    check("real_pdf_order_ok", 0 <= i_intro < i_methods,
          "intro=%d methods=%d" % (i_intro, i_methods))
    # 引文核验
    hits = locate_quote(document, "band-walk")
    check("real_pdf_quote_anchored", len(hits) >= 1 and hits[0].get("page"),
          "命中页=%s" % [h.get("page") for h in hits])


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--no-real-pdf", action="store_true")
    a = ap.parse_args()

    test_layout_logic()
    workdir = a.workdir or tempfile.mkdtemp(prefix="litparse-selftest-")
    os.makedirs(workdir, exist_ok=True)
    if not a.no_real_pdf:
        test_real_pdf(workdir)

    npass = sum(1 for r in RESULTS if r["pass"])
    nfail = len(FAILURES)
    nskip = sum(1 for r in RESULTS if r["pass"] is None)
    summary = {"total": len(RESULTS), "passed": npass, "failed": nfail,
               "skipped": nskip, "results": RESULTS}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
