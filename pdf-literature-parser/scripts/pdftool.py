#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdftool.py — 科研 PDF 结构化解析核心库（文档解析 Skill 的确定性后端）

目标（对应本题四个考察点）:
  提得全: 正文、图表题注、脚注、参考文献逐字提取；页眉页脚单独归档，不混入正文。
  排得对: 多栏阅读顺序还原（band-walk 列拼接）、跨页段落续接、跨页表格合并。
  拆得清: 章节层级、表格行列、公式与上下标/希腊字母按结构还原。
  核得回: 每个结构元素携带 {page, bbox, zone, source} 证据锚点；读不出的部分如实标注。

依赖策略（优雅降级，全部可选）:
  1. PyMuPDF (fitz)   -> 词/span 级坐标 + 字号 + superscript 标志（最丰富）
  2. pdfplumber      -> 词级坐标 + 表格 (find_tables)
  3. pdftotext/pdftoppm (poppler) -> 词级 bbox (-bbox-layout)，渲染页面
  4. tesseract (OCR)  -> 无文字层页面识别，带词级置信度
Python 3.8+ 兼容，除可选第三方库外仅用标准库。
"""

import argparse
import bisect
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

# ---------------------------------------------------------------------------
# 常量与正则
# ---------------------------------------------------------------------------

MATH_CHARS = set(
    "=+-*/<>≤≥≈≠±×÷∑∏∫∂∇√∞∝∈∉⊂⊃⊆∪∩∧∨¬→⇒⇔∀∃αβγδεζηθικλμνξπρστυφχψω"
    "ΓΔΘΛΞΠΣΦΨΩ₁₂₃₄₅₆₇₈₉₀²³⁴⁵⁶⁷⁸⁹⁰|()[]{}·⋅∘∙^_"
)

SENTENCE_ENDERS = ".!?;:。！？；：…"
SENTENCE_END = re.compile(r"[.!?;:。！？；：]\s*$")
ENDS_WITH_HYPHEN = re.compile(r"[-\u2010-\u2015]\s*$")

HEADING_RE = re.compile(
    r"^\s*("
    r"\d{1,3}(\.\d{1,3}){0,4}[.)\s]+"          # 1. / 2.3 / 3.2.1.
    r"|[IVXLC]{1,7}[.)\s]+"                     # IV. / I.
    r"|[A-Z]\.(\d{1,3})(\.\d{1,3})*[.)\s]*"     # A.2.3
    r"|(Abstract|Keywords|Introduction|Background|Related\s+Work|Methods?|Materials?"
    r"|Experimental|Results?|Discussion|Conclusion|Summary|Outlook|References?|Bibliography"
    r"|Appendix|Appendices|Acknowledgments?|Acknowledgements|Supplementary|Notation|Abbreviations"
    r"|摘要|关键词|引言|绪论|背景|方法|材料|实验|结果|讨论|结论|总结|展望|参考文献|致谢|附录|缩写|符号)"
    r")"
)
HEADING_PREFIX_RE = re.compile(
    r"^\s*(\d{1,3}(\.\d{1,3}){0,4}[.)]?\s+|[IVXLC]{1,7}[.)]\s*|[A-Z][.)]\s*)")
NAMED_HEADING_FULL_RE = re.compile(
    r"^\s*(Abstract|Keywords|Introduction|Background|Related\s+Work|Methods?|Materials?"
    r"|Experimental|Results?|Discussion|Conclusion|Summary|Outlook|References?|Bibliography"
    r"|Appendix|Appendices|Acknowledgments?|Acknowledgements|Supplementary|Notation|Abbreviations"
    r"|摘要|关键词|引言|绪论|背景|方法|材料|实验|结果|讨论|结论|总结|展望|参考文献|致谢|附录|缩写|符号)"
    r"\s*[:.\u3002]?\s*$", re.IGNORECASE)

CAPTION_FIG_RE = re.compile(
    r"^\s*(Fig(?:ure)?s?\.?|图)\s*(\d{1,3}(?:[.\-]\d{1,3})*)?\s*[:.\u3002\s-]", re.IGNORECASE)
CAPTION_TAB_RE = re.compile(
    r"^\s*(Table|Tab\.|表)\s*(\d{1,3}(?:[.\-]\d{1,3})*)?\s*[:.\u3002\s-]", re.IGNORECASE)
EQ_NUM_RE = re.compile(r"^\s*[\(\[](\d{1,3}(?:[.\-]\d{1,3})?[a-z]?)[\)\]]\s*$")
EQ_NUM_INLINE_RE = re.compile(r"[\(\[](\d{1,3}(?:[.\-]\d{1,3})?[a-z]?)[\)\]]\s*$")
PAGE_NUM_RE = re.compile(r"^\s*(page\s*)?([ivxlcdm]+|\d{1,4}|[A-Z]-\d{1,3})\s*$", re.IGNORECASE)
REF_ITEM_RE = re.compile(r"^\s*[\(\[]\d{1,3}[\)\]]\s*\S")
FN_MARK_RE = re.compile(r"^\s*(\*{1,3}|[0-9]{1,2}|[a-h])\s*[\)\].:]?\s+")

HASH_RE = re.compile(r"^\s*[0-9a-f]{2,}\s*$")


def norm_ws(s):
    """空白归一化（不改变字符本身，不吞掉减号/破折号/Unicode 数学符号）"""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def norm_for_search(s):
    """证据检索用的归一化：去空白、Unicode NFC，保留全部字符"""
    s = unicodedata.normalize("NFC", s or "")
    return re.sub(r"\s+", "", s)


def round2(x):
    return round(float(x), 2)


# ---------------------------------------------------------------------------
# 词 / 行 / 块 数据模型
# ---------------------------------------------------------------------------

class Word:
    __slots__ = ("text", "x0", "y0", "x1", "y1", "size", "font", "sup", "conf")

    def __init__(self, text, x0, y0, x1, y1, size=0.0, font="", sup=False, conf=None):
        self.text = text
        self.x0 = float(x0); self.y0 = float(y0); self.x1 = float(x1); self.y1 = float(y1)
        self.size = float(size or 0.0)
        self.font = font or ""
        self.sup = bool(sup)
        self.conf = conf

    def to_json(self):
        return {"t": self.text, "x0": round2(self.x0), "y0": round2(self.y0),
                "x1": round2(self.x1), "y1": round2(self.y1),
                "sz": round2(self.size) if self.size else None,
                "f": self.font or None, "sup": self.sup or None,
                "c": round2(self.conf) if self.conf is not None else None}


class Line:
    __slots__ = ("text", "bbox", "words", "size")

    def __init__(self, words):
        self.words = words
        self.text = " ".join(w.text for w in words)
        x0 = min(w.x0 for w in words); y0 = min(w.y0 for w in words)
        x1 = max(w.x1 for w in words); y1 = max(w.y1 for w in words)
        self.bbox = [round2(x0), round2(y0), round2(x1), round2(y1)]
        sizes = [w.size for w in words if w.size > 0]
        self.size = round2(sum(sizes) / len(sizes)) if sizes else 0.0

    def to_json(self):
        return {"t": self.text, "b": self.bbox,
                "sz": self.size or None,
                "w": [w.to_json() for w in self.words]}


_BLOCK_SEQ = [0]
_TMP_SEQ = [0]

class Block:
    __slots__ = ("id", "page", "kind", "text", "bbox", "zone", "lines", "size",
                 "bold", "meta")

    def __init__(self, page, kind="paragraph", text="", bbox=None, zone="body",
                 lines=None, size=0.0, bold=False, meta=None):
        _BLOCK_SEQ[0] += 1
        self.id = "p%db#%d" % (page, _BLOCK_SEQ[0])
        self.page = page
        self.kind = kind
        self.text = text
        self.bbox = list(bbox) if bbox else [0, 0, 0, 0]
        self.zone = zone
        self.lines = lines or []
        self.size = size
        self.bold = bold
        self.meta = meta or {}

    def to_json(self):
        d = {"id": self.id, "kind": self.kind, "text": self.text,
             "bbox": self.bbox, "zone": self.zone,
             "page": self.page, "lines": [l.to_json() for l in self.lines]}
        if self.size:
            d["size"] = self.size
        if self.bold:
            d["bold"] = True
        if self.meta:
            d["meta"] = self.meta
        return d


# ---------------------------------------------------------------------------
# 后端: 抽象 PDF 文档
# ---------------------------------------------------------------------------

class PDFDoc:
    """统一后端接口。text_only=True 表示页面没有文字层（需要 OCR）。"""

    def __init__(self, path):
        self.path = path
        self.backend = None
        self.pages = 0
        self.encrypted = False
        self.needs_password = False
        self.page_sizes = []
        self.producer = ""
        self._doc = None

    def open(self):
        raise NotImplementedError

    def close(self):
        pass

    def page_words(self, pno):
        """返回 (words, spans_rich)。words: [Word]; spans_rich 由后端决定。"""
        raise NotImplementedError

    def page_drawings_bboxes(self, pno):
        """返回页面中的图形/图像 bbox 列表（可选）。"""
        return []

    def render_page(self, pno, out_png, dpi=200):
        raise NotImplementedError


def _which(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


class FitzBackend(PDFDoc):
    def open(self):
        try:
            import pymupdf as fitz  # PyMuPDF >= 1.24 推荐名
        except ImportError:
            import fitz  # noqa: F401 旧名
        doc = fitz.open(self.path)
        self._doc = doc
        self.backend = "pymupdf"
        self.pages = doc.page_count
        self.encrypted = bool(doc.is_encrypted)
        self.needs_password = bool(doc.needs_pass)
        try:
            self.producer = doc.metadata.get("producer") or ""
        except Exception:
            self.producer = ""
        self.page_sizes = []
        for i in range(self.pages):
            r = doc[i].rect
            self.page_sizes.append([round2(r.width), round2(r.height)])
        return self

    def page_words(self, pno):
        page = self._doc[pno]
        words = []
        rich = []
        try:
            d = page.get_text("dict")
            for b in d.get("blocks", []):
                if b.get("type") != 0:
                    continue
                for ln in b.get("lines", []):
                    lw = []
                    for sp in ln.get("spans", []):
                        txt = sp.get("text", "")
                        if not txt:
                            continue
                        bbox = sp.get("bbox")
                        size = sp.get("size", 0.0)
                        flags = sp.get("flags", 0)
                        font = sp.get("font", "")
                        w = Word(txt, bbox[0], bbox[1], bbox[2], bbox[3],
                                 size=size, font=font, sup=bool(flags & 1))
                        words.append(w)
                        lw.append(w)
                    rich.append(lw)
        except Exception:
            words = []
        return words, rich

    def page_drawings_bboxes(self, pno):
        out = []
        try:
            for img in self._doc[pno].get_images(full=True):
                pass
            for d in self._doc[pno].get_text("dict").get("blocks", []):
                if d.get("type") == 1:
                    b = d.get("bbox")
                    out.append([round2(b[0]), round2(b[1]), round2(b[2]), round2(b[3])])
        except Exception:
            pass
        return out

    def render_page(self, pno, out_png, dpi=200):
        try:
            pix = self._doc[pno].get_pixmap(dpi=dpi, alpha=False)
            pix.save(out_png)
            return True
        except Exception:
            return False


class PdfPlumberBackend(PDFDoc):
    def open(self):
        import pdfplumber  # noqa: optional
        with pdfplumber.open(self.path) as pdf:
            self.pages = len(pdf.pages)
            self.encrypted = bool(getattr(pdf, "metadata", {}) and False)
            try:
                self.producer = (pdf.metadata or {}).get("Producer", "")
            except Exception:
                self.producer = ""
            for p in pdf.pages:
                self.page_sizes.append([round2(p.width), round2(p.height)])
        # keep a lazily-opened handle
        self._pdf = None
        self.backend = "pdfplumber"
        return self

    def _page(self, pno):
        import pdfplumber  # noqa
        if self._pdf is None:
            self._pdf = pdfplumber.open(self.path)
        return self._pdf.pages[pno]

    def page_words(self, pno):
        try:
            ws = self._page(pno).extract_words(extra_attrs=["size", "fontname"])
        except Exception:
            return [], []
        words = []
        for w in ws:
            words.append(Word(w["text"], w["x0"], w["top"], w["x1"], w["bottom"],
                              size=w.get("size") or 0.0, font=w.get("fontname") or ""))
        return words, []

    def render_page(self, pno, out_png, dpi=200):
        try:
            im = self._page(pno).to_image(resolution=dpi)
            im.save(out_png)
            return True
        except Exception:
            return False

    def close(self):
        if self._pdf is not None:
            try:
                self._pdf.close()
            except Exception:
                pass


class PdftotextBackend(PDFDoc):
    """poppler pdftotext -bbox-layout 后端（无第三方 Python 依赖）。"""

    def __init__(self, path, pdftotext=None, pdftoppm=None):
        super().__init__(path)
        self.pdftotext = pdftotext or _which("pdftotext")
        self.pdftoppm = pdftoppm or _which("pdftoppm")
        self._xml_cache = {}

    def _run_tool(self, args):
        """poppler 工具在本机某些沙箱下不能向被捕获的 stdout 管道写，统一写临时文件再读回。
        优先系统临时目录，失败回退到当前目录。"""
        _TMP_SEQ[0] += 1
        base = ".pdftool-tmp-%d-%d" % (os.getpid(), _TMP_SEQ[0])
        cands = [os.path.join(tempfile.gettempdir(), base),
                 os.path.join(os.getcwd(), base),
                 os.path.join(os.path.dirname(os.path.abspath(self.path)), base)]
        tmp = None
        for c in cands:
            try:
                with open(c, "wb"):
                    pass
                os.remove(c)
                tmp = c
                break
            except OSError:
                continue
        if tmp is None:
            return None, "no writable temp path"
        cmd = list(args)
        cmd.append(tmp)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0 or not os.path.exists(tmp):
                return None, (r.stderr or r.stdout or "")[:200]
            with open(tmp, "rb") as f:
                data = f.read()
            return data, ""
        except Exception as e:
            return None, str(e)[:200]
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass

    def open(self):
        if not self.pdftotext:
            raise RuntimeError("no pdftotext binary found")
        info = subprocess.run(
            [self.pdftotext, "-v"], capture_output=True, text=True, timeout=30)
        self.backend = "pdftotext"
        self.producer = (info.stderr or info.stdout or "").splitlines()[:1]
        self.producer = self.producer[0] if self.producer else ""
        data, err = self._run_tool([self.pdftotext, "-enc", "UTF-8", self.path])
        self._plain = data.decode("utf-8", "replace") if data else ""
        # 页数与尺寸通过 -bbox-layout 解析
        xml, err2 = self._run_tool([self.pdftotext, "-bbox-layout", "-enc", "UTF-8",
                                    self.path])
        if not xml:
            raise RuntimeError("pdftotext -bbox-layout failed: %s" % err2[:200])
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml.decode("utf-8", "replace"))
        except Exception as e:
            raise RuntimeError("pdftotext -bbox-layout produced no usable XML: %s" % e)
        pages = [p for p in root.iter() if p.tag == "page" or p.tag.endswith("}page")]
        self.pages = len(pages)
        for p in pages:
            self.page_sizes.append([float(p.get("width", 0)), float(p.get("height", 0))])
        self.encrypted = False
        self._word_counts = [len([w for w in p.iter()
                                  if w.tag == "word" or w.tag.endswith("}word")])
                             for p in pages]
        self._xml_root = root
        return self

    def _bbox_xml(self):
        return self._xml_root

    def page_words(self, pno):
        root = self._xml_root
        pages = [p for p in root.iter() if p.tag == "page" or p.tag.endswith("}page")]
        if pno >= len(pages):
            return [], []
        words = []
        for w in pages[pno].iter():
            if not (w.tag == "word" or w.tag.endswith("}word")):
                continue
            txt = (w.text or "")
            if not txt.strip():
                continue
            try:
                x0 = float(w.get("xMin")); y0 = float(w.get("yMin"))
                x1 = float(w.get("xMax")); y1 = float(w.get("yMax"))
            except (TypeError, ValueError):
                continue
            words.append(Word(txt, x0, y0, x1, y1))
        return words, []

    def render_page(self, pno, out_png, dpi=200):
        if not self.pdftoppm:
            return False
        tmp = out_png.rsplit(".", 1)[0] + "-tmp"
        try:
            r = subprocess.run(
                [self.pdftoppm, "-png", "-r", str(dpi), "-f", str(pno + 1),
                 "-l", str(pno + 1), self.path, tmp],
                capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                import glob
                cands = sorted(glob.glob(tmp + "*"))
                if cands:
                    shutil.move(cands[0], out_png)
                    for extra in glob.glob(tmp + "*"):
                        try:
                            os.remove(extra)
                        except OSError:
                            pass
                    return True
        except Exception:
            pass
        return False


# ---------------------------------------------------------------------------
# 行/块构建
# ---------------------------------------------------------------------------

def words_to_lines(words, y_tol=None, x_gap=None):
    """把词聚成行：同 y 带且 x 间距不超过阈值才算同一行。
    x 间距限制保证双栏中同一 y 带的左右栏词不会拼进同一行。"""
    if not words:
        return []
    ws = sorted(words, key=lambda w: (w.y0, w.x0))
    med_h = sorted(w.y1 - w.y0 for w in ws)[len(ws) // 2] or 8.0
    tol = y_tol if y_tol is not None else max(2.0, 0.4 * med_h)
    # 行内词距 vs 栏间跳变：取同 y 带相邻词的 x 间距中位数
    inter_x = []
    for i in range(len(ws) - 1):
        if abs(ws[i].y0 - ws[i + 1].y0) <= tol:
            d = ws[i + 1].x0 - ws[i].x1
            if 0.2 < d < 200:
                inter_x.append(d)
    med_x = sorted(inter_x)[len(inter_x) // 2] if inter_x else 6.0
    x_gap_max = x_gap if x_gap is not None else max(8.0, 2.2 * med_x)
    lines = []
    for w in ws:
        placed = False
        for ln in lines:
            lw = ln.words[-1]
            inter = min(lw.y1, w.y1) - max(lw.y0, w.y0)
            if inter > tol:
                dx = w.x0 - lw.x1
                if -2.0 <= dx <= x_gap_max:
                    ln.words.append(w)
                    placed = True
                    break
        if not placed:
            lines.append(Line([w]))
    for ln in lines:
        ln.words.sort(key=lambda w: w.x0)
        ln.__init__(ln.words)
    lines.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
    return lines


def _gap_threshold(gaps, med_line):
    """行间距通常呈双峰分布（行内 ~2pt vs 段落/结构 ~6-20pt）。
    找第一个显著跳变（>3pt）把两类分开，阈值取中点；无跳变则用保守阈值。"""
    gs = sorted(g for g in gaps if g > 0)
    if not gs:
        return 1.4 * med_line
    for i in range(len(gs) - 1):
        if gs[i + 1] - gs[i] > 3.0:
            return max(4.0, (gs[i] + gs[i + 1]) / 2.0)
    return max(1.4 * med_line, 2.5 * gs[0])


def lines_to_blocks_in_zone(lines, page, col_l, col_r):
    """同一栏（或 full 区）内的行聚成块。断块规则见 lines_to_blocks 注释。"""
    return _group_lines(lines, page, col_l, col_r)


def _group_lines(lines, page, col_l, col_r):
    if not lines:
        return []
    ys_sorted = sorted(lines, key=lambda l: l.bbox[1])
    gaps = [ys_sorted[i + 1].bbox[1] - ys_sorted[i].bbox[3]
            for i in range(len(ys_sorted) - 1)]
    gaps = [g for g in gaps if g > 0.5]
    med_line = sorted(l.bbox[3] - l.bbox[1] for l in lines)[len(lines) // 2] or 10.0
    thr = _gap_threshold(gaps, med_line)
    width = max(col_r - col_l, 1.0)
    para_indent = max(6.0, 0.035 * width)      # 首行缩进（新段）
    display_indent = max(8.0, 0.10 * width)    # 居中/大缩进（公式等）
    text_x0, text_x1 = col_l, col_r

    def starts_new(prev_lines, ln):
        prev = prev_lines[-1]
        gap = ln.bbox[1] - prev.bbox[3]
        if gap > thr:
            return True
        cur_indent = ln.bbox[0] - text_x0
        prev_indent = prev.bbox[0] - text_x0
        prev_full = (prev.bbox[2] > text_x1 - 8.0)
        cur_full = (ln.bbox[2] > text_x1 - 8.0)
        # 新段：当前行首行缩进，且上一行与当前行都接近行尾
        # （排除参考文献悬挂缩进的续行——续行 x1 短）
        if cur_indent > para_indent and prev_full and cur_full:
            return True
        # 大缩进的非满行（表格行/居中元素开头）跟在满行文本后 -> 断
        if cur_indent > display_indent and not cur_full and prev_full:
            return True
        # 上一行是大缩进短行（公式/表格行），当前行回到行首 -> 断
        if prev_indent > display_indent and cur_indent <= 8.0:
            return True
        t = ln.text.strip()
        if CAPTION_TAB_RE.match(t) or CAPTION_FIG_RE.match(t):
            return True
        if REF_ITEM_RE.match(t):
            return True
        if NAMED_HEADING_FULL_RE.match(t):
            return True
        if (HEADING_PREFIX_RE.match(t) and len(t) <= 120
                and not SENTENCE_END.search(t.rstrip())):
            return True
        # 上一行是独立标题行 -> 断（标题与正文分开，正文不被并入标题块）
        pt = prev.text.strip()
        if NAMED_HEADING_FULL_RE.match(pt):
            return True
        if (HEADING_PREFIX_RE.match(pt) and len(pt) <= 120
                and not SENTENCE_END.search(pt.rstrip())):
            return True
        return False

    blocks = []
    cur = [ys_sorted[0]]
    for ln in ys_sorted[1:]:
        if starts_new(cur, ln):
            blocks.append(cur)
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    out = []
    for ls in blocks:
        text = "\n".join(l.text for l in ls)
        bbox = [min(l.bbox[0] for l in ls), min(l.bbox[1] for l in ls),
                max(l.bbox[2] for l in ls), max(l.bbox[3] for l in ls)]
        sizes = [l.size for l in ls if l.size]
        size = sum(sizes) / len(sizes) if sizes else 0.0
        b = Block(page, "paragraph", text=text, bbox=bbox, lines=ls, size=round2(size))
        out.append(b)
    return out


def page_blocks_from_lines(lines, page, pw, ph):
    """行级版面分析：分栏 -> 按栏聚块 -> 返回 (blocks, ncols, col_bboxes, conf, text_x0, text_x1)。
    必须按栏分别聚块，否则相邻栏同一 y 带的标题行会被拼成一个块。"""
    if not lines:
        return [], 1, [[0, 0, pw, ph]], 0.0, 0, pw
    xs0 = sorted(l.bbox[0] for l in lines)
    xs1 = sorted(l.bbox[2] for l in lines)
    def pct(vals, p):
        return vals[min(len(vals) - 1, int(p * len(vals)))]
    text_x0 = pct(xs0, 0.10)
    text_x1 = pct(xs1, 0.90)
    span = max(text_x1 - text_x0, 1.0)
    full = [l for l in lines if (l.bbox[2] - l.bbox[0]) > 0.85 * span]
    narrow = [l for l in lines if (l.bbox[2] - l.bbox[0]) <= 0.85 * span]
    ncols, col_bboxes, conf = detect_columns(narrow, pw, text_x0, text_x1)
    zones = {}  # id(line) -> zone
    for l in full:
        zones[id(l)] = "full"
    for l in narrow:
        zones[id(l)] = zone_of_block(l, pw, ph, text_x0, text_x1, ncols, col_bboxes)
    # 按区聚块（保持区内 y 顺序）
    blocks = []
    order_of_zones = []
    for l in sorted(lines, key=lambda x: (x.bbox[1], x.bbox[0])):
        z = zones[id(l)]
        if z not in order_of_zones:
            order_of_zones.append(z)
    for z in order_of_zones:
        zlines = sorted([l for l in lines if zones[id(l)] == z],
                        key=lambda x: (x.bbox[1], x.bbox[0]))
        if z == "full":
            l0, l1 = text_x0, text_x1
        else:
            m = re.match(r"col-(\d+)", z)
            if m and col_bboxes:
                i = int(m.group(1)) - 1
                l0, l1 = col_bboxes[i][0], col_bboxes[i][2]
            else:
                l0, l1 = text_x0, text_x1
        for b in _group_lines(zlines, page, l0, l1):
            b.zone = z
            blocks.append(b)
    return blocks, ncols, col_bboxes, conf, text_x0, text_x1


def _y_lines(words, tol=None):
    """仅按 y 重叠聚行（不限制 x），用于行级/词级版面分析。"""
    if not words:
        return []
    ws = sorted(words, key=lambda w: (w.y0, w.x0))
    med_h = sorted(w.y1 - w.y0 for w in ws)[len(ws) // 2] or 8.0
    tol = tol if tol is not None else max(2.0, 0.4 * med_h)
    lines = []
    for w in ws:
        placed = False
        for ln in reversed(lines):
            lw = ln.words[-1]
            inter = min(lw.y1, w.y1) - max(lw.y0, w.y0)
            if inter > tol:
                ln.words.append(w)
                placed = True
                break
        if not placed:
            lines.append(Line([w]))
    for ln in lines:
        ln.words.sort(key=lambda w: w.x0)
        ln.__init__(ln.words)
    lines.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
    return lines


def detect_columns_from_words(words, pw, text_x0, text_x1):
    """词级 2-D 版面检测:
      - 对每个 x-bin 统计覆盖该 x 的词的 y 区间并集占全文高度的比例;
      - 比例 < 25% 的连续 x-run 是候选栏间隙（真正的栏间隙没有任何词跨越）;
      - 校验: 间隙两侧各有 >=5 个 y 带紧贴间隙的词，且两侧词的 y 跨度
        都 >= 全文高度的 30%（排除表格内部间隙与短文页面）。"""
    span = max(text_x1 - text_x0, 1.0)
    ymin = min(w.y0 for w in words)
    ymax = max(w.y1 for w in words)
    yext = max(ymax - ymin, 1.0)
    NB = 240
    intervals = [[] for _ in range(NB)]
    for w in words:
        i0 = max(0, int((w.x0 - text_x0) / span * NB))
        i1 = min(NB - 1, int((w.x1 - text_x0) / span * NB))
        for i in range(i0, i1 + 1):
            intervals[i].append((w.y0, w.y1))

    def coverage(ivs):
        if not ivs:
            return 0.0
        ivs = sorted(ivs)
        total = 0.0
        cs, ce = ivs[0]
        for s, e in ivs[1:]:
            if s <= ce:
                ce = max(ce, e)
            else:
                total += ce - cs
                cs, ce = s, e
        total += ce - cs
        return total / yext

    cov = [coverage(ivs) for ivs in intervals]
    min_gap = max(5.0, 0.012 * span)
    runs = []
    start = None
    for i, c in enumerate(cov):
        if c < 0.25 and start is None:
            start = i
        elif c >= 0.25 and start is not None:
            wpt = (i - start) / NB * span
            if wpt >= min_gap:
                runs.append((start, i))
            start = None
    if start is not None and (NB - start) / NB * span >= min_gap:
        runs.append((start, NB))

    def side_stats(x0, x1, band=16.0):
        sel = [w for w in words if x0 <= (w.x0 + w.x1) / 2.0 <= x1]
        bands = set()
        y0 = None
        y1 = None
        for w in sel:
            bands.add(int(w.y0 / band))
            if y0 is None or w.y0 < y0:
                y0 = w.y0
            if y1 is None or w.y1 > y1:
                y1 = w.y1
        return len(bands), ((y1 - y0) if y1 is not None else 0.0), len(sel)

    best = None
    for (s, e) in runs:
        gx0 = text_x0 + s / NB * span
        gx1 = text_x0 + e / NB * span
        mid = (gx0 + gx1) / 2.0
        if not (text_x0 + 0.20 * span <= mid <= text_x0 + 0.80 * span):
            continue
        lb, lext, lc = side_stats(gx0 - 18.0, gx0)
        rb, rext, rc = side_stats(gx1, gx1 + 18.0)
        if (lb >= 5 and rb >= 5 and lext >= 0.30 * yext and rext >= 0.30 * yext):
            best = (gx0, gx1)
            break
    if not best:
        return 1, [[text_x0, 0, text_x1, 99999]], 0.6
    gx0, gx1 = best
    cols = [[text_x0, 0, gx0, 99999], [gx1, 0, text_x1, 99999]]
    conf = 0.9
    # 三栏：在更宽一侧再查一次（简化：只在左栏查）
    for c in cols:
        w = c[2] - c[0]
        if w < 0.45 * span:
            continue
        sub = [wd for wd in words if c[0] <= (wd.x0 + wd.x1) / 2.0 <= c[2]]
        if len(sub) < 30:
            continue
        # 递归式检测（限一层）
        sub_x0 = min(wd.x0 for wd in sub)
        sub_x1 = max(wd.x1 for wd in sub)
        n2, c2, _c = detect_columns_from_words(sub, pw, sub_x0, sub_x1)
        if n2 == 2:
            gap2 = (c2[0][2] + c2[1][0]) / 2.0
            if gap2 < c[2] - 0.1 * w:
                cols2 = [[c[0], 0, gap2, 99999], [gap2, 0, c[2], 99999]]
                # 该栏被再分 -> 三栏
                if c[0] == cols[0][0]:
                    return 3, cols2 + [cols[1]], 0.75
                return 3, [cols[0]] + cols2, 0.75
    return 2, cols, conf


def page_blocks_from_words(words, page, pw, ph):
    """词级主流程: 2-D 栏检测 -> 词分带 -> 行重排 -> 按栏聚块。"""
    if not words:
        return [], 1, [[0, 0, pw, ph]], 0.0, 0, pw
    xs0 = sorted(w.x0 for w in words)
    xs1 = sorted(w.x1 for w in words)

    def pct(vals, p):
        return vals[min(len(vals) - 1, int(p * len(vals)))]

    text_x0 = pct(xs0, 0.02)
    text_x1 = pct(xs1, 0.98)
    span = max(text_x1 - text_x0, 1.0)
    raw_lines = _y_lines(words)
    ncols, col_bboxes, conf = detect_columns_from_words(words, pw, text_x0, text_x1)
    # 行级分带：按栏间隙把跨栏行拆开；词流连续（桥接）的行保持整行（如标题/作者行）
    zoned = []
    for ln in raw_lines:
        if ncols >= 2:
            groups = {}
            for w in ln.words:
                cx = (w.x0 + w.x1) / 2.0
                best = 0
                bd = None
                for i, c in enumerate(col_bboxes):
                    d = abs(cx - (c[0] + c[2]) / 2.0)
                    if bd is None or d < bd:
                        bd = d
                        best = i
                groups.setdefault(best, []).append(w)
            order = sorted(groups)
            merged = []
            cur_idx = None
            cur_ws = []
            for idx in order:
                ws = groups[idx]
                if cur_ws:
                    gap = min(w.x0 for w in ws) - max(w.x1 for w in cur_ws)
                    if gap < 6.0:
                        cur_ws += ws
                        continue
                    merged.append((cur_idx, cur_ws))
                cur_idx = idx
                cur_ws = ws
            merged.append((cur_idx, cur_ws))
            if len(merged) == 1:
                idx, ws = merged[0]
                z = "col-%d" % (idx + 1)
                if len(order) > 1:  # 词流连续跨栏：全宽行（标题/作者）
                    z = "full"
                zoned.append((z, Line(ws)))
            else:
                for idx, ws in merged:
                    zoned.append(("col-%d" % (idx + 1), Line(ws)))
            continue
        # 单栏页
        lw = ln.bbox[2] - ln.bbox[0]
        zoned.append(("full" if lw > 0.6 * span else "col-1", ln))
    # 按区聚块
    blocks = []
    seen_zones = []
    for z, _ln in zoned:
        if z not in seen_zones:
            seen_zones.append(z)
    for z in seen_zones:
        zlines = sorted([ln for zz, ln in zoned if zz == z],
                        key=lambda x: (x.bbox[1], x.bbox[0]))
        if z == "full":
            l0, l1 = text_x0, text_x1
        else:
            m = re.match(r"col-(\d+)", z)
            if m and col_bboxes:
                i = int(m.group(1)) - 1
                l0, l1 = col_bboxes[i][0], col_bboxes[i][2]
            else:
                l0, l1 = text_x0, text_x1
        for b in _group_lines(zlines, page, l0, l1):
            b.zone = z
            blocks.append(b)
    return blocks, ncols, col_bboxes, conf, text_x0, text_x1


def lines_to_blocks(lines, page, med_gap=None):
    """兼容入口：不做分栏，把行按整页宽度聚块（供单栏调试使用）。
    正式流程请用 page_blocks_from_lines（按栏聚块，避免相邻栏行粘连）。"""
    if not lines:
        return []
    xs0 = sorted(l.bbox[0] for l in lines)
    xs1 = sorted(l.bbox[2] for l in lines)
    l0 = xs0[0] if xs0 else 0.0
    l1 = xs1[-1] if xs1 else 100.0
    return _group_lines(sorted(lines, key=lambda x: (x.bbox[1], x.bbox[0])),
                        page, l0, l1)


# ---------------------------------------------------------------------------
# 版面分析
# ---------------------------------------------------------------------------

def detect_text_width(blocks, page_w):
    if not blocks:
        return 0.04 * page_w, 0.96 * page_w
    xs = [b.bbox[0] for b in blocks] + [b.bbox[2] for b in blocks]
    lo, hi = min(xs), max(xs)
    if hi - lo < 0.3 * page_w:
        # 只有一列：给一点余量
        pad = 0.04 * page_w
        return max(0, lo - pad), min(page_w, hi + pad)
    return lo, hi


def _peer_ratio(blocks_a, blocks_b, band=26.0):
    """blocks_a 中有多少比例在 blocks_b 中存在同 y 带（±band）的块。
    用于判定两栏是否在纵向交错排布（真多栏）而非上下堆叠的两段窄内容。"""
    if not blocks_a or not blocks_b:
        return 0.0
    ys_b = sorted(b.bbox[1] for b in blocks_b)
    cnt = 0
    for b in blocks_a:
        y = b.bbox[1]
        i = bisect.bisect_left(ys_b, y)
        near = None
        if i < len(ys_b):
            near = ys_b[i]
        if i > 0 and (near is None or y - ys_b[i - 1] < near - y):
            near = ys_b[i - 1]
        if near is not None and abs(y - near) <= band:
            cnt += 1
    return cnt / max(len(blocks_a), 1)


def detect_columns(blocks, page_w, text_x0, text_x1):
    """投影法 + 垂直重叠校验。返回 (ncols, [col bbox...], 置信度)。"""
    if not blocks:
        return 1, [[text_x0, 0, text_x1, 99999]], 0.0
    lo, hi = text_x0, text_x1
    span = max(hi - lo, 1.0)
    # 覆盖投影
    bins = [0] * 400
    for b in blocks:
        i0 = int((b.bbox[0] - lo) / span * 400)
        i1 = int((b.bbox[2] - lo) / span * 400)
        for i in range(max(0, i0), min(400, i1 + 1)):
            bins[i] += 1
    min_gap = max(6.0, 0.025 * span)
    runs = []
    start = None
    for i, v in enumerate(bins):
        if v == 0 and start is None:
            start = i
        elif v > 0 and start is not None:
            w_pt = (i - start) / 400.0 * span
            if w_pt >= min_gap:
                runs.append((start, i))
            start = None
    if start is not None and (400 - start) / 400.0 * span >= min_gap:
        runs.append((start, 400))
    if not runs:
        return 1, [[lo, 0, hi, 99999]], 1.0
    # 每个 gap 把块分成左右，验证：两侧块数足够、垂直重叠显著、gap 位于正文中部
    best = None
    for (s, e) in runs:
        gx0 = lo + s / 400.0 * span
        gx1 = lo + e / 400.0 * span
        mid_gap = (gx0 + gx1) / 2.0
        if not (lo + 0.20 * span <= mid_gap <= lo + 0.80 * span):
            continue
        left = [b for b in blocks if b.bbox[2] <= gx0 + 1]
        right = [b for b in blocks if b.bbox[0] >= gx1 - 1]
        if len(left) < 3 or len(right) < 3:
            continue
        # 纵向交错判定：两侧都有 >=40% 的块在对方存在同带块
        if _peer_ratio(left, right) >= 0.4 and _peer_ratio(right, left) >= 0.4:
            best = (gx0, gx1)
            break
    if not best:
        return 1, [[lo, 0, hi, 99999]], 0.6
    gx0, gx1 = best
    cols = [[lo, 0, gx0, 99999], [gx1, 0, hi, 99999]]
    # 三栏检查：继续在更宽的一栏里找 gap（简化：仅再检查一次）
    for c in cols:
        sub = [b for b in blocks if b.bbox[0] >= c[0] - 1 and b.bbox[2] <= c[2] + 1]
        if len(sub) < 6:
            continue
        w = c[2] - c[0]
        if w < 0.3 * span:
            continue
        cbins = [0] * 200
        for b in sub:
            i0 = int((b.bbox[0] - c[0]) / w * 200)
            i1 = int((b.bbox[2] - c[0]) / w * 200)
            for i in range(max(0, i0), min(200, i1 + 1)):
                cbins[i] += 1
        cstart = None
        for i, v in enumerate(cbins):
            if v == 0 and cstart is None:
                cstart = i
            elif v > 0 and cstart is not None:
                gw = (i - cstart) / 200.0 * w
                if gw >= max(8.0, 0.16 * w):
                    mid = c[0] + (cstart + i) / 2 / 200.0 * w
                    l2 = [b for b in sub if b.bbox[2] <= mid]
                    r2 = [b for b in sub if b.bbox[0] >= mid]
                    if len(l2) >= 3 and len(r2) >= 3:
                        return 3, [[lo, 0, mid, 99999], [mid, 0, c[2], 99999],
                                   [gx1, 0, hi, 99999]], 0.75
                    return 2, [[lo, 0, gx0, 99999], [gx1, 0, hi, 99999]], 0.85
                cstart = None
    return 2, [[lo, 0, gx0, 99999], [gx1, 0, hi, 99999]], 0.9


def zone_of_block(b, page_w, page_h, text_x0, text_x1, ncols, col_bboxes):
    w = b.bbox[2] - b.bbox[0]
    span = max(text_x1 - text_x0, 1.0)
    if ncols > 1 and w > 0.6 * span:
        return "full"
    if ncols == 1:
        return "col-1"
    cx = (b.bbox[0] + b.bbox[2]) / 2.0
    for i, c in enumerate(col_bboxes):
        if c[0] - 2 <= cx <= c[2] + 2:
            return "col-%d" % (i + 1)
    return "col-1"


def band_order(blocks):
    """band-walk 阅读顺序：同行(y0 接近)按列排序；full 块单独成带。"""
    if not blocks:
        return []
    med_h = sorted(b.bbox[3] - b.bbox[1] for b in blocks)[len(blocks) // 2] or 10.0
    eps = max(2.0, 0.45 * med_h)
    rest = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
    order = []
    while rest:
        b = rest.pop(0)
        if b.zone == "full":
            order.append(b)
            continue
        band = [b]
        rest2 = []
        for o in rest:
            if abs(o.bbox[1] - b.bbox[1]) <= eps and o.zone != "full":
                band.append(o)
            else:
                rest2.append(o)
        rest = rest2
        # 列内排序：col 编号 -> x0
        def colkey(x):
            m = re.match(r"col-(\d+)", x.zone)
            return (int(m.group(1)), x.bbox[0]) if m else (99, x.bbox[0])
        band.sort(key=colkey)
        order.extend(band)
    return order


LIST_MARKER_RE = re.compile(r"^\s*(\d{1,3}[.)]|[A-Za-z][.)]|[-•·*▪◦])\s+")

def merge_continuations(blocks_in_order):
    """跨栏/跨页段落续接。规则:
      - 仅当上一块无句末标点（或连字符结尾）时才可能续接；
      - 下一块以列表/编号标记开头时不合并；
      - 同栏内相邻（垂直间距小）: 合并；
      - 不同栏: 仅当上一块是其栏内最后一块、下一块是另一栏第一块时合并。
    """
    # 先计算每栏首末块
    first_of = {}
    last_of = {}
    for b in blocks_in_order:
        if b.kind != "paragraph":
            continue
        first_of.setdefault(b.zone, b)
        last_of[b.zone] = b
    out = []
    for b in blocks_in_order:
        if not out:
            out.append(b)
            continue
        prev = out[-1]
        if prev.kind != "paragraph" or b.kind != "paragraph":
            out.append(b)
            continue
        pt = prev.text.rstrip()
        if SENTENCE_END.search(pt) or LIST_MARKER_RE.match(b.text):
            out.append(b)
            continue
        gap = b.bbox[1] - prev.bbox[3]
        same_zone = prev.zone == b.zone
        can_merge = False
        if same_zone:
            can_merge = gap < 60
        else:
            can_merge = (last_of.get(prev.zone) is prev and
                         first_of.get(b.zone) is b)
        if not can_merge:
            out.append(b)
            continue
        if ENDS_WITH_HYPHEN.search(pt):
            prev.text = prev.text.rstrip()[:-1] + b.text.lstrip()
        else:
            prev.text = prev.text.rstrip() + " " + b.text.lstrip()
        prev.bbox = [min(prev.bbox[0], b.bbox[0]), min(prev.bbox[1], b.bbox[1]),
                     max(prev.bbox[2], b.bbox[2]), max(prev.bbox[3], b.bbox[3])]
        prev.meta.setdefault("merged_with", []).append(b.id)
    return out


# ---------------------------------------------------------------------------
# 页眉页脚 / 页码（跨页持续性判定）
# ---------------------------------------------------------------------------

def classify_headers_footers(pages_blocks, page_h):
    """pages_blocks: list[list[Block]]。把跨页重复出现的顶部/底部行归为页眉/页脚。
    只出现于单页的顶部内容（如首页标题）保留为正文。"""
    hz = 0.13 * page_h
    fz = 0.10 * page_h
    top_texts = {}   # norm text -> (count, y0 avg, zone)
    bot_texts = {}
    for blocks in pages_blocks:
        seen_t = set(); seen_b = set()
        for b in blocks:
            key = norm_ws(b.text)
            if not key:
                continue
            if b.bbox[3] <= hz and b.bbox[0] > 0 and b.bbox[2] < page_h * 0.99:
                if key not in seen_t:
                    seen_t.add(key)
                    d = top_texts.setdefault(key, [0, 0.0])
                    d[0] += 1
                    d[1] = (d[1] * (d[0] - 1) + b.bbox[1]) / d[0]
            if b.bbox[1] >= page_h - fz:
                if key not in seen_b:
                    seen_b.add(key)
                    d = bot_texts.setdefault(key, [0, 0.0])
                    d[0] += 1
                    d[1] = (d[1] * (d[0] - 1) + b.bbox[1]) / d[0]
    npages = max(len(pages_blocks), 1)
    # 跨页匹配：页眉可能因分栏而在不同页合并/拆分为不同块，用“包含”关系匹配
    all_top = []
    for blocks in pages_blocks:
        s = set()
        for b in blocks:
            if b.kind == "paragraph" and b.bbox[3] <= hz:
                s.add(norm_for_search(b.text))
        all_top.append(s)

    def pages_containing(text):
        cnt = 0
        for s in all_top:
            if any(text in t or t in text for t in s if t and text):
                cnt += 1
        return cnt

    top_keep = set()
    for blocks in pages_blocks:
        for b in blocks:
            if b.kind != "paragraph" or b.bbox[3] > hz:
                continue
            key = norm_for_search(b.text)
            if key and pages_containing(key) >= max(2, 0.6 * npages):
                top_keep.add(norm_ws(b.text))
    bot_keep = {k for k, v in bot_texts.items() if v[0] >= max(2, 0.6 * npages)}
    # 纯页码（Page N / 数字 / 罗马数字）即使不跨页重复也判为页脚
    for blocks in pages_blocks:
        for b in blocks:
            if b.kind != "paragraph":
                continue
            key = norm_ws(b.text)
            if b.bbox[1] >= page_h - fz and (PAGE_NUM_RE.match(key) or key.lower().startswith("page")):
                bot_keep.add(key)
            if b.bbox[3] <= hz and PAGE_NUM_RE.match(key):
                top_keep.add(key)
    # 应用判定
    header_blocks = []
    footer_blocks = []
    for blocks in pages_blocks:
        for b in blocks:
            if b.kind != "paragraph":
                continue
            key = norm_ws(b.text)
            if key in top_keep:
                b.zone = "header"
                header_blocks.append(b)
            elif key in bot_keep:
                b.zone = "footer"
                footer_blocks.append(b)
    return header_blocks, footer_blocks


# ---------------------------------------------------------------------------
# 结构识别
# ---------------------------------------------------------------------------

def is_heading(block, body_med_size, col_l=None, col_r=None):
    t = block.text.strip()
    if not t or len(t) > 180:
        return False, 0
    if HEADING_PREFIX_RE.match(t) and len(t) <= 120 and not SENTENCE_END.search(t.rstrip()):
        prefix = HEADING_PREFIX_RE.match(t).group(1).rstrip(".) ")
        depth = prefix.count(".") + 1 if prefix and prefix[0].isdigit() else 1
        return True, min(depth, 6)
    if NAMED_HEADING_FULL_RE.match(t):
        return True, 1
    # 无编号样式标题：字号明显大于正文的短行，或粗体短行
    words = t.split()
    if len(words) <= 12 and not SENTENCE_END.search(t.rstrip()):
        if col_l is not None and col_r is not None and (col_r - col_l) > 0:
            indent = (block.bbox[0] - col_l) / (col_r - col_l)
            if indent > 0.22 and not block.bold:
                return False, 0  # 居中的作者/日期/公式行不是标题
        if body_med_size and block.size and block.size >= body_med_size * 1.12:
            return True, 1
        if block.bold:
            return True, 1
    return False, 0


def col_range(b, text_x0, text_x1, col_bboxes):
    """返回块所在栏的 [左, 右] x 范围。"""
    if b.zone == "full":
        return text_x0, text_x1
    m = re.match(r"col-(\d+)", b.zone or "")
    if m:
        i = int(m.group(1)) - 1
        if col_bboxes and 0 <= i < len(col_bboxes):
            return col_bboxes[i][0], col_bboxes[i][2]
    return text_x0, text_x1


def is_display_equation(block, col_left, col_right):
    t = block.text.strip()
    if not t or len(t) > 220:
        return False
    if EQ_NUM_RE.match(t):
        return False  # 纯编号行单独处理
    cw = max(col_right - col_left, 1.0)
    left_indent = (block.bbox[0] - col_left) / cw
    # 右缘按方程体计算：排除行尾的方程编号 "(n)"（编号紧贴栏右缘）
    x1_eff = block.bbox[2]
    if block.lines:
        words_all = [w for ln in block.lines for w in ln.words]
        body = list(words_all)
        while body and EQ_NUM_RE.match(body[-1].text.strip()):
            body.pop()
        if body:
            x1_eff = max(w.x1 for w in body)
    right_pad = (col_right - x1_eff) / cw
    if left_indent < 0.12 or right_pad < 0.03:
        return False
    nmath = sum(1 for ch in t if ch in MATH_CHARS)
    words = len(t.split())
    if nmath >= 3 and words <= 24:
        return True
    if words <= 4 and ("=" in t or "≈" in t) and left_indent > 0.15:
        return True
    return False


def looks_like_table_block(lines, page_w):
    """启发式表格判定：>=2 行、多数行 >=2 词、词在行内呈列对齐。"""
    if len(lines) < 2:
        return False
    rows = [ln for ln in lines if ln.words]
    if len(rows) < 2:
        return False
    multi = sum(1 for ln in rows if len(ln.words) >= 2)
    if multi < 0.6 * len(rows):
        return False
    # 列 x 位置一致性：相邻行词 x0 聚类差
    xs = [w.x0 for ln in rows for w in ln.words]
    xs.sort()
    # 大空隙（列分隔）占比
    gaps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    big = sum(1 for g in gaps if g > 14)
    if big >= len(rows):
        return True
    return False


def table_grid_from_lines(lines):
    """把行词按 x 聚类成列槽 -> 网格。返回 (headers, rows, col_xs)。"""
    all_x = sorted(w.x0 for ln in lines for w in ln.words)
    # 聚类列起始 x
    clusters = []
    for x in all_x:
        if clusters and x - clusters[-1][-1] <= 14:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    col_x = [sum(c) / len(c) for c in clusters]
    grid = []
    for ln in lines:
        row = {}
        for w in ln.words:
            best = min(range(len(col_x)), key=lambda i: abs(w.x0 - col_x[i]))
            row.setdefault(best, []).append(w.text)
        cells = [""] * len(col_x)
        for i, ws in row.items():
            cells[i] = " ".join(ws)
        grid.append(cells)
    return grid, col_x


def group_table_rows(blocks):
    """把紧跟在表格题注后的对齐行合并成 kind='table' 块（保留行列结构）。
    对齐判定: 相邻行词 x0 平均最近距离 <= 14pt 且行词数 2..16。"""
    ordered = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
    out = []
    i = 0
    n = len(ordered)
    while i < n:
        b = ordered[i]
        out.append(b)
        if b.kind != "paragraph" or not CAPTION_TAB_RE.match(b.text.strip()):
            i += 1
            continue
        rows = []
        j = i + 1
        prev_xs = None
        while j < n:
            cand = ordered[j]
            if cand.kind != "paragraph" or not cand.lines:
                break
            if len(cand.lines) > 2:
                break
            xs = [w.x0 for w in cand.lines[0].words]
            if len(xs) < 2 or len(xs) > 16:
                break
            if prev_xs is None:
                prev_xs = xs
                rows.append(cand)
                j += 1
                continue
            diffs = [min(abs(x - px) for px in prev_xs) for x in xs]
            if sum(diffs) / len(diffs) > 14:
                break
            prev_xs = xs
            rows.append(cand)
            j += 1
        if len(rows) >= 2:
            tlines = [ln for r in rows for ln in r.lines]
            grid, col_x = table_grid_from_lines(tlines)
            text = "\n".join(l.text for l in tlines)
            bbox = [min(r.bbox[0] for r in rows), min(r.bbox[1] for r in rows),
                    max(r.bbox[2] for r in rows), max(r.bbox[3] for r in rows)]
            t = Block(b.page, "table", text=text, bbox=bbox,
                      zone=b.zone, lines=tlines)
            t.meta = {"header_row": grid[0] if grid else [],
                      "ncols": len(col_x), "grid": grid,
                      "column_xs": [round2(x) for x in col_x]}
            out.append(t)
            i = j
        else:
            i += 1
    return out


def jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


# ---------------------------------------------------------------------------
# OCR（无文字层页面）
# ---------------------------------------------------------------------------

def ocr_page(png_path, tesseract=None, langs="eng"):
    """tesseract TSV -> words with confidence。失败返回 None。"""
    t = tesseract or _which("tesseract")
    if not t:
        return None
    base = png_path.rsplit(".", 1)[0]
    out = base + "-ocr"
    langs = langs if langs else "eng"
    try:
        r = subprocess.run(
            [t, png_path, out, "-l", langs, "tsv", "--psm", "1"],
            capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not os.path.exists(out + ".tsv"):
            return None
        words = []
        with open(out + ".tsv", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 12 or parts[0] == "level":
                    continue
                try:
                    conf = float(parts[10])
                    if conf < 0:
                        continue
                    txt = parts[11]
                    if not txt.strip():
                        continue
                    x0, y0 = float(parts[6]), float(parts[7])
                    x1, y1 = float(parts[8]), float(parts[9])
                    words.append(Word(txt, x0, y0, x1, y1, conf=conf))
                except (ValueError, IndexError):
                    continue
        return words
    except Exception:
        return None


def mojibake_ratio(text):
    if not text:
        return 0.0
    bad = text.count("\ufffd") + len(re.findall(r"\(cid:\d+\)", text)) * 6
    return bad / max(len(text), 1)


# ---------------------------------------------------------------------------
# 证据检索
# ---------------------------------------------------------------------------

def dehyphenate(s):
    """去掉行尾连字符：'an-\nchors' / 'an- chors' -> 'anchors'。"""
    return re.sub(r"-\s+", "", s or "")


def locate_quote(document, quote):
    """在文档模型里检索引文。返回 [match...]。
    match: {page, block_id, zone, bbox, kind, context}
    先精确匹配，再尝试去行尾连字符匹配（引用跨断行时仍能命中）。"""
    q = norm_for_search(quote)
    if not q:
        return []
    q_dh = norm_for_search(dehyphenate(quote))
    hits = []

    def scan(text, qq):
        bt = norm_for_search(text)
        idx = bt.find(qq)
        if idx >= 0:
            return bt
        return None

    for p in document.get("pages", []):
        for b in p.get("blocks", []):
            text = b.get("text", "")
            matched = scan(text, q) is not None
            mode = "exact"
            if not matched:
                matched = scan(dehyphenate(text), q_dh) is not None
                mode = "dehyphenated"
            if matched:
                hits.append({
                    "page": b.get("page"),
                    "block_id": b.get("id"),
                    "zone": b.get("zone"),
                    "bbox": b.get("bbox"),
                    "kind": b.get("kind"),
                    "match": mode,
                    "context": text[:400],
                })
                if len(hits) >= 20:
                    return hits
    return hits


# ---------------------------------------------------------------------------
# 主解析流程
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, pdf_path, workdir=None, backend=None, ocr=False,
                 ocr_langs="eng", render=False, render_dpi=150, max_pages=None):
        self.pdf_path = pdf_path
        self.workdir = workdir or os.getcwd()
        self.backend = backend
        self.ocr = ocr
        self.ocr_langs = ocr_langs
        self.render = render
        self.render_dpi = render_dpi
        self.max_pages = max_pages
        self.warnings = []

    def _open_doc(self):
        errs = []
        if self.backend in (None, "pymupdf"):
            try:
                return FitzBackend(self.pdf_path).open()
            except Exception as e:
                errs.append("pymupdf: %s" % e)
        if self.backend in (None, "pdfplumber"):
            try:
                return PdfPlumberBackend(self.pdf_path).open()
            except Exception as e:
                errs.append("pdfplumber: %s" % e)
        if self.backend in (None, "pdftotext"):
            try:
                return PdftotextBackend(self.pdf_path).open()
            except Exception as e:
                errs.append("pdftotext: %s" % e)
        raise RuntimeError("no usable PDF backend: %s" % "; ".join(errs))

    def parse(self):
        doc = self._open_doc()
        try:
            document = self._build(doc)
        finally:
            doc.close()
        return document

    def _build(self, doc):
        docobj = {
            "schema": "document/v1",
            "source": {
                "file": os.path.basename(self.pdf_path),
                "sha256": self._sha256(),
                "pages": doc.pages,
                "producer": doc.producer[:200],
                "encrypted": doc.encrypted,
                "needs_password": doc.needs_password,
                "backend": doc.backend,
            },
            "pages": [],
            "sections": [],
            "tables": [],
            "figures": [],
            "equations": [],
            "references": [],
            "reading_order": [],
            "warnings": [],
        }
        if doc.needs_password:
            docobj["warnings"].append({
                "code": "encrypted-needs-password",
                "detail": "PDF 需要口令，无法解析内容。可尝试空口令；否则标记拒答。"})
            return docobj

        npages = doc.pages if not self.max_pages else min(doc.pages, self.max_pages)
        pages_blocks = []
        page_layouts = {}
        for pno in range(npages):
            pw, ph = doc.page_sizes[pno]
            words, rich = doc.page_words(pno)
            if not words:
                # 无文字层 -> 渲染 + OCR
                words = self._ocr_fallback(doc, pno, pw, ph)
                if words:
                    self.warnings.append({
                        "code": "page-scanned-ocr",
                        "page": pno + 1,
                        "detail": "页面无文字层，已用 OCR 识别（见各行置信度）。"})
                else:
                    self.warnings.append({
                        "code": "page-unreadable",
                        "page": pno + 1,
                        "detail": "页面无文字层且 OCR 不可用/失败，内容如实留空。"})
                    pages_blocks.append([])
                    page_layouts[pno] = (1, [[0, 0, pw, ph]], 0.0, 0, pw)
                    docobj["pages"].append({
                        "page": pno + 1, "label": str(pno + 1),
                        "width": pw, "height": ph,
                        "status": "unreadable", "blocks": []})
                    continue
            # mojibake 检查
            raw_text = " ".join(w.text for w in words)
            ratio = mojibake_ratio(raw_text)
            if ratio > 0.05:
                self.warnings.append({
                    "code": "text-degraded-mojibake",
                    "page": pno + 1,
                    "detail": "文字层疑似乱码（%.3f），建议对渲染图复核。" % ratio})
            lines = None
            blocks, ncols, col_bboxes, conf, text_x0, text_x1 = \
                page_blocks_from_words(words, pno + 1, pw, ph)
            page_layouts[pno] = (ncols, col_bboxes, conf, text_x0, text_x1)
            pages_blocks.append(blocks)
            docobj["pages"].append({
                "page": pno + 1, "label": str(pno + 1),
                "width": pw, "height": ph, "status": "ok", "blocks": []})
            if self.render:
                self._render_check(doc, pno, pw, ph)

        # 页眉页脚
        if pages_blocks:
            hdrs, ftrs = classify_headers_footers(pages_blocks, doc.page_sizes[0][1])
        else:
            hdrs, ftrs = [], []

        # 逐页结构分析（栏信息复用行级分析结果）
        for i, blocks in enumerate(pages_blocks):
            page = docobj["pages"][i]
            pw, ph = page["width"], page["height"]
            ncols, col_bboxes, conf, text_x0, text_x1 = page_layouts[i]
            body = [b for b in blocks if b.zone != "header" and b.zone != "footer"]
            if not body:
                page["blocks"] = []
                continue
            body = group_table_rows(body)
            order = band_order(body)
            # 先做结构标注、后合并续接（避免把标题/方程并入上一段）
            body_sizes = [b.size for b in body if b.size]
            med_size = sorted(body_sizes)[len(body_sizes) // 2] if body_sizes else 0.0
            for b in order:
                self._classify_block(b, med_size, text_x0, text_x1, col_bboxes, pw, ph, docobj)
            order = merge_continuations(order)
            # 跨页表格合并（基于 docobj.tables 最近两条目）
            self._merge_tables_across_pages(docobj, i + 1)
            # 输出页
            page["layout"] = {"columns": ncols,
                              "column_bboxes": [[round2(c[0]), round2(c[1]), round2(c[2]), round2(c[3])] for c in col_bboxes],
                              "confidence": round2(conf),
                              "text_x": [round2(text_x0), round2(text_x1)]}
            page["header"] = [b.to_json() for b in blocks if b.zone == "header"]
            page["footer"] = [b.to_json() for b in blocks if b.zone == "footer"]
            page["blocks"] = [b.to_json() for b in order]
            page["block_ids"] = [b.id for b in order]
            docobj["reading_order"].append([b.id for b in order])

        self._build_sections(docobj)
        self._build_references(docobj)
        self._finalize_ids(docobj)
        docobj["warnings"].extend(self.warnings)
        docobj["warnings"] = _dedup_warnings(docobj["warnings"])
        return docobj

    def _ocr_fallback(self, doc, pno, pw, ph):
        if not self.ocr:
            return []
        png = os.path.join(self.workdir, "page-%03d.png" % (pno + 1))
        if not doc.render_page(pno, png, dpi=self.render_dpi):
            return []
        words = ocr_page(png, langs=self.ocr_langs)
        if not words:
            return []
        scale = pw / (doc.page_sizes[pno][0] or 1)  # tesseract 输出即渲染像素; fitz 渲染按 dpi
        # 统一换算：把像素坐标换算为 PDF 点坐标（按 72/dpi 比例）
        # fitz/pdftoppm 渲染 dpi=render_dpi 时 1 点 = render_dpi/72 像素
        k = 72.0 / self.render_dpi
        for w in words:
            w.x0 *= k; w.y0 *= k; w.x1 *= k; w.y1 *= k
        return words

    def _render_check(self, doc, pno, pw, ph):
        png = os.path.join(self.workdir, "page-%03d.png" % (pno + 1))
        try:
            ok = doc.render_page(pno, png, dpi=self.render_dpi)
            if not ok:
                self.warnings.append({"code": "render-failed", "page": pno + 1,
                                      "detail": "页面渲染失败，无法人工复核。"})
        except Exception:
            pass

    def _classify_block(self, b, med_size, text_x0, text_x1, col_bboxes, pw, ph, docobj):
        t = b.text.strip()
        if not t:
            b.kind = "empty"
            return
        page = b.page
        if b.kind == "table":
            # 已由 group_table_rows 组好：挂到本页最近的表条目
            for tb in reversed(docobj["tables"]):
                if tb.get("page") == page and not tb.get("parts"):
                    tb["parts"].append({
                        "page": page, "block_id": b.id,
                        "bbox": b.bbox, "ncols": b.meta.get("ncols"),
                        "header_row": b.meta.get("header_row"),
                        "grid": b.meta.get("grid"),
                        "column_xs": b.meta.get("column_xs")})
                    break
            return
        col_l, col_r = col_range(b, text_x0, text_x1, col_bboxes)
        if CAPTION_FIG_RE.match(t):
            b.kind = "figure_caption"
            m = CAPTION_FIG_RE.match(t)
            b.meta["fig_index"] = m.group(2)
            b.meta["caption_text"] = t
            docobj["figures"].append({
                "index": m.group(2), "page": page, "block_id": b.id,
                "caption": t, "bbox": b.bbox, "zone": b.zone})
            return
        if CAPTION_TAB_RE.match(t):
            b.kind = "table_caption"
            m = CAPTION_TAB_RE.match(t)
            b.meta["table_index"] = m.group(2)
            docobj["tables"].append({
                "index": m.group(2), "caption": t, "page": page,
                "caption_block_id": b.id, "bbox": b.bbox,
                "parts": [], "merged": False})
            return
        if EQ_NUM_RE.match(t) and (col_r - b.bbox[2]) <= 14:
            b.kind = "equation_number"
            b.meta["number"] = EQ_NUM_RE.match(t).group(1)
            # 挂到上一个方程
            for eq in reversed(docobj["equations"]):
                if eq.get("page") == page and not eq.get("number"):
                    eq["number"] = b.meta["number"]
                    eq["number_block_id"] = b.id
                    break
            else:
                docobj["equations"].append({
                    "number": b.meta["number"], "page": page,
                    "text": "", "block_id": b.id, "bbox": b.bbox,
                    "number_only": True})
            return
        is_head, depth = is_heading(b, med_size, col_l, col_r)
        if is_head:
            b.kind = "heading"
            b.meta["level"] = depth
            if b.text.startswith("Abstract") or b.text.startswith("摘要"):
                b.meta["level"] = 0
            return
        if is_display_equation(b, col_l, col_r):
            b.kind = "equation"
            num = None
            m = EQ_NUM_INLINE_RE.search(t)
            if m:
                num = m.group(1)
            b.meta["number"] = num
            docobj["equations"].append({
                "number": num, "page": page, "block_id": b.id,
                "text": t, "bbox": b.bbox, "zone": b.zone})
            return
        if b.meta.get("_table"):
            b.kind = "table"
            return
        if FN_MARK_RE.match(t) and b.bbox[1] > 0.75 * ph:
            b.kind = "footnote"
            b.meta["marker"] = FN_MARK_RE.match(t).group(1)
            return
        b.kind = "paragraph"

    def _merge_tables_across_pages(self, docobj, pageno):
        """跨页续表合并：本页首表与前页末表列数一致且表头相似 -> 合并到同一逻辑表。"""
        tables = docobj["tables"]
        if len(tables) < 2:
            return
        cur = tables[-1]
        prev = tables[-2]
        if cur.get("page") != pageno or prev.get("page") != pageno - 1:
            return
        if not cur.get("parts") or not prev.get("parts"):
            return
        cp = cur["parts"][0]
        pp = prev["parts"][-1]
        hdr_cur = cp.get("header_row") or []
        hdr_prev = pp.get("header_row") or []
        ncol_cur = cp.get("ncols"); ncol_prev = pp.get("ncols")
        if not (ncol_cur and ncol_prev and ncol_cur == ncol_prev):
            return
        hdr_sim = jaccard(hdr_prev, hdr_cur) if hdr_prev and hdr_cur else 0.0
        if hdr_sim >= 0.6 or hdr_prev == hdr_cur:
            prev["parts"].append(cp)
            prev["merged"] = True
            cur["continuation_of"] = prev.get("index")
            docobj["tables"].pop()
            # 重写块元信息
            for page in docobj["pages"]:
                for b in page.get("blocks", []):
                    m = b.get("meta") or {}
                    if m.get("_table_part_of") == cur.get("index"):
                        m["_table_part_of"] = prev.get("index")

    def _build_sections(self, docobj):
        sections = []
        for pi, page in enumerate(docobj["pages"]):
            for b in page["blocks"]:
                if b["kind"] == "heading":
                    level = b.get("meta", {}).get("level", 1)
                    num = None
                    m = HEADING_PREFIX_RE.match(b["text"])
                    if m:
                        num = m.group(1).strip()
                    sections.append({
                        "title": b["text"], "level": level, "number": num,
                        "page": b["page"], "block_id": b["id"],
                        "bbox": b["bbox"]})
        docobj["sections"] = sections

    def _build_references(self, docobj):
        refs = []
        in_refs = False
        for pi, page in enumerate(docobj["pages"]):
            for b in page["blocks"]:
                if b["kind"] == "heading" and re.match(
                        r"^\s*(References?|Bibliography|参考文献)\b", b["text"], re.IGNORECASE):
                    in_refs = True
                    continue
                if in_refs and b["kind"] == "heading":
                    in_refs = False
                    continue
                if in_refs and REF_ITEM_RE.match(b["text"]):
                    m = REF_ITEM_RE.match(b["text"])
                    refs.append({"text": b["text"], "page": b["page"],
                                 "block_id": b["id"], "bbox": b["bbox"]})
        docobj["references"] = refs

    def _finalize_ids(self, docobj):
        # 1) 给块赋正式 id，并建立 旧id->新id 映射
        idmap = {}
        for page in docobj["pages"]:
            for i, b in enumerate(page.get("blocks", []), 1):
                old = b.get("id")
                new = "p%db%d" % (b["page"], i)
                if old and old != new:
                    idmap[old] = new
                b["id"] = new
                m = b.get("meta") or {}
                if m.get("merged_with"):
                    m["merged_with"] = [idmap.get(x, x) for x in m["merged_with"]]
        # 2) 重写各结构引用
        for t in docobj.get("tables", []):
            t["caption_block_id"] = idmap.get(t.get("caption_block_id"),
                                              t.get("caption_block_id"))
            for part in t.get("parts", []):
                part["block_id"] = idmap.get(part.get("block_id"), part.get("block_id"))
        for f in docobj.get("figures", []):
            f["block_id"] = idmap.get(f.get("block_id"), f.get("block_id"))
        for e in docobj.get("equations", []):
            e["block_id"] = idmap.get(e.get("block_id"), e.get("block_id"))
            e["number_block_id"] = idmap.get(e.get("number_block_id"),
                                             e.get("number_block_id"))
        for s in docobj.get("sections", []):
            s["block_id"] = idmap.get(s.get("block_id"), s.get("block_id"))
        for r in docobj.get("references", []):
            r["block_id"] = idmap.get(r.get("block_id"), r.get("block_id"))
        # 3) reading_order 重写
        for i, ids in enumerate(docobj.get("reading_order", [])):
            docobj["reading_order"][i] = [idmap.get(x, x) for x in ids]
        for page in docobj["pages"]:
            page["block_ids"] = [idmap.get(x, x) for x in page.get("block_ids", [])]

    def _sha256(self):
        h = hashlib.sha256()
        try:
            with open(self.pdf_path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        except OSError:
            pass
        return h.hexdigest()


def _dedup_warnings(warns):
    seen = set()
    out = []
    for w in warns:
        key = json.dumps(w, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(w)
    return out


# ---------------------------------------------------------------------------
# 渲染阅读顺序 Markdown
# ---------------------------------------------------------------------------

def render_markdown(document):
    """把文档模型渲染成带 [pNbM] 锚点的阅读顺序 Markdown（供 Agent 阅读）。"""
    md = []
    src = document.get("source", {})
    md.append("# 文档解析（阅读顺序）: %s" % src.get("file", "?"))
    md.append("")
    md.append("> backend=%s pages=%s encrypted=%s" % (
        src.get("backend"), src.get("pages"), src.get("encrypted")))
    md.append("")
    prev_page = None
    for page in document.get("pages", []):
        pno = page.get("page")
        md.append("\n<!-- ===== page %s (label %s) status %s ===== -->\n" % (
            pno, page.get("label"), page.get("status")))
        for hb in page.get("header", []):
            md.append("[页眉 p%d] %s\n" % (pno, hb.get("text", "")))
        for b in page.get("blocks", []):
            kind = b.get("kind", "paragraph")
            bid = b.get("id", "")
            zone = b.get("zone", "")
            text = b.get("text", "")
            bbox = b.get("bbox", [])
            tag = "[%s %s] " % (bid, zone)
            if kind == "heading":
                lvl = (b.get("meta") or {}).get("level", 1)
                md.append("\n%s %s\n" % ("#" * min(1 + lvl, 6), text))
                md.append("{anchor:%s}\n" % bid)
            elif kind == "figure_caption":
                md.append("\n> **%s** %s\n" % (tag, text))
            elif kind == "table_caption":
                md.append("\n> **%s** %s\n" % (tag, text))
            elif kind == "table":
                grid = (b.get("meta") or {}).get("grid") or []
                md.append("\n%s\n" % tag)
                if grid:
                    md.append("\n| " + " | ".join(str(c) for c in grid[0]) + " |")
                    md.append("\n|" + "---|" * max(len(grid[0]), 1))
                    for row in grid[1:]:
                        md.append("\n| " + " | ".join(str(c) for c in row) + " |")
                    md.append("\n")
                else:
                    md.append("\n```\n%s\n```\n" % text)
                md.append("{anchor:%s}\n" % bid)
            elif kind == "equation":
                num = (b.get("meta") or {}).get("number")
                md.append("\n$$\\text{(Eq %s)}\\quad %s$$\n%s\n" % (
                    num or "?", text, "{anchor:%s}" % bid))
            elif kind == "equation_number":
                md.append("{anchor:%s}\n" % bid)
            elif kind == "footnote":
                md.append("\n[脚注 %s] %s\n" % (bid, text))
            else:
                md.append("%s %s\n\n{anchor:%s}\n" % (tag, text, bid))
        for fb in page.get("footer", []):
            md.append("[页脚 p%d] %s\n" % (pno, fb.get("text", "")))
    md.append("\n## 结构索引\n")
    md.append("### 章节层级\n")
    for s in document.get("sections", []):
        md.append("- L%d %s | p%d %s | %s" % (s.get("level", 1), s.get("title", ""),
                                             s.get("page"), s.get("block_id", ""),
                                             s.get("bbox", [])))
        md.append("")
    md.append("### 图\n")
    for f in document.get("figures", []):
        md.append("- Fig %s | p%d %s | %s" % (f.get("index"), f.get("page"),
                                             f.get("block_id"), f.get("caption", "")[:120]))
        md.append("")
    md.append("### 表\n")
    for t in document.get("tables", []):
        md.append("- Table %s | 起始 p%d %s | parts=%d merged=%s | %s" % (
            t.get("index"), t.get("page"), t.get("caption_block_id"),
            len(t.get("parts", [])) + 1, t.get("merged"), t.get("caption", "")[:120]))
        md.append("")
    md.append("### 公式\n")
    for e in document.get("equations", []):
        md.append("- Eq %s | p%d %s | %s" % (e.get("number"), e.get("page"),
                                            e.get("block_id"), e.get("text", "")[:120]))
        md.append("")
    md.append("### 参考文献 (%d 条)\n" % len(document.get("references", [])))
    for r in document.get("references", [])[:200]:
        md.append("- p%d %s" % (r.get("page"), r.get("text", "")[:160]))
        md.append("")
    if document.get("warnings"):
        md.append("### 解析告警\n")
        for w in document.get("warnings", []):
            md.append("- [%s] p%s: %s" % (w.get("code"), w.get("page", "-"),
                                          w.get("detail", "")))
            md.append("")
    return "\n".join(md)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def _main():
    ap = argparse.ArgumentParser(description="科研 PDF 结构化解析")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default="document.json")
    ap.add_argument("--md", default=None, help="输出阅读顺序 Markdown 路径")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--backend", default=None, choices=["pymupdf", "pdfplumber", "pdftotext"])
    ap.add_argument("--ocr", action="store_true", help="无文字层页面启用 OCR")
    ap.add_argument("--ocr-langs", default="eng")
    ap.add_argument("--render", action="store_true", help="渲染每页 PNG 供人工复核")
    ap.add_argument("--render-dpi", type=int, default=150)
    ap.add_argument("--max-pages", type=int, default=None)
    a = ap.parse_args()
    workdir = a.workdir or os.path.dirname(os.path.abspath(a.out))
    os.makedirs(workdir, exist_ok=True)
    p = Parser(a.pdf, workdir=workdir, backend=a.backend, ocr=a.ocr,
               ocr_langs=a.ocr_langs, render=a.render, render_dpi=a.render_dpi,
               max_pages=a.max_pages)
    document = p.parse()
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=1)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(render_markdown(document))
    print(json.dumps({
        "ok": True, "backend": document["source"]["backend"],
        "pages": document["source"]["pages"],
        "sections": len(document["sections"]),
        "tables": len(document["tables"]),
        "equations": len(document["equations"]),
        "references": len(document["references"]),
        "warnings": len(document["warnings"]),
        "out": os.path.abspath(a.out),
    }, ensure_ascii=False))


if __name__ == "__main__":
    _main()
