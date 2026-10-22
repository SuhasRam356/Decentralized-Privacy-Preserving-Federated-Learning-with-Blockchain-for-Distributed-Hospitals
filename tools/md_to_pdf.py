#!/usr/bin/env python3
"""Build the MedXChAIn audit packet PDF from the Markdown sources.

Usage:
    python tools/md_to_pdf.py --repo . --out MEDXCHAIN_AUDIT_AND_ROADMAP.pdf

Requires: reportlab (pip install reportlab)
Inputs:  AGENT_BRIEF.md, TECHNICAL_AUDIT.md, ENHANCEMENT_ROADMAP.md
"""
from __future__ import annotations
import html
import re
import sys
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, HRFlowable, KeepTogether,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle, XPreformatted)
from reportlab.platypus.tableofcontents import TableOfContents

# ----------------------------------------------------------------------------- palette
NAVY = colors.HexColor("#0f2f57")
BLUE = colors.HexColor("#1a56db")
MUTED = colors.HexColor("#5a6b7d")
RULE = colors.HexColor("#dbe2ea")
CODEBG = colors.HexColor("#f5f6f8")
CODEBR = colors.HexColor("#e2e7ee")
ZEBRA = colors.HexColor("#f8fafc")
CODEINK = colors.HexColor("#8a1c4a")
GREEN = colors.HexColor("#12694a")
AMBER = colors.HexColor("#8a5a00")

PAGE_W, PAGE_H = A4
LM = RM = 17 * mm
TM = 22 * mm
BM = 18 * mm
USABLE = PAGE_W - LM - RM

# ----------------------------------------------------------------------------- fonts
FDIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("DJ", FDIR / "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DJ-B", FDIR / "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DJM", FDIR / "DejaVuSansMono.ttf"))
pdfmetrics.registerFont(TTFont("DJM-B", FDIR / "DejaVuSansMono-Bold.ttf"))
pdfmetrics.registerFontFamily("DJ", normal="DJ", bold="DJ-B", italic="DJ", boldItalic="DJ-B")
pdfmetrics.registerFontFamily("DJM", normal="DJM", bold="DJM-B", italic="DJM", boldItalic="DJM-B")
MONO_ADV = 0.602  # DejaVuSansMono advance width in em

# ----------------------------------------------------------------------------- char hygiene
REPLACE = {
    "\ufe0f": "", "\u274c": "\u2718", "\u2705": "\u2714", "\u26a0": "\u26a0",
    "\U0001f3e5": "H", "\U0001f512": "[lock]", "\U0001f4cb": "[list]",
    "\u200b": "", "\u00a0": " ",
}
KEEP_SYMBOLS = set("\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534\u253c"
                   "\u2192\u2190\u2194\u2248\u2264\u2265\u2260\u2212\u00b1\u00d7\u00b7"
                   "\u2026\u2013\u2014\u00a7\u2018\u2019\u201c\u201d\u25ba\u25bc\u25c4"
                   "\u2714\u2718\u2713\u2717\u03b1\u03b2\u03b3\u03b4\u03b5\u03bb\u03bc"
                   "\u03c0\u03c3\u03a3\u0394\u03b8\u2261\u2265\u00b0")


def clean(text: str) -> str:
    out = []
    for ch in text:
        if ch in REPLACE:
            out.append(REPLACE[ch])
        elif ord(ch) < 128 or ch in KEEP_SYMBOLS or ch in "\u00e9\u00e8\u00fc\u00f6\u00e7":
            out.append(ch)
        elif 0x2500 <= ord(ch) <= 0x257F:  # box drawing
            out.append(ch)
        else:
            out.append("?")
    return "".join(out)


# ----------------------------------------------------------------------------- styles
def st(name, **kw):
    base = dict(fontName="DJ", fontSize=9.3, leading=13.3, alignment=TA_LEFT,
                textColor=colors.HexColor("#1d2733"), spaceAfter=4)
    base.update(kw)
    return ParagraphStyle(name, **base)


S_BODY = st("Body")
S_H1 = st("H1", fontName="DJ-B", fontSize=19, leading=23, textColor=NAVY,
          spaceBefore=6, spaceAfter=8)
S_H2 = st("H2", fontName="DJ-B", fontSize=12.8, leading=16.5, textColor=NAVY,
          spaceBefore=13, spaceAfter=5, keepWithNext=1)
S_H3 = st("H3", fontName="DJ-B", fontSize=10.4, leading=13.6, textColor=colors.HexColor("#16324f"),
          spaceBefore=10, spaceAfter=3.5, keepWithNext=1)
S_H4 = st("H4", fontName="DJ-B", fontSize=9.4, leading=12.4, textColor=colors.HexColor("#2a3a4d"),
          spaceBefore=7, spaceAfter=2.5, keepWithNext=1)
S_BUL = st("Bul", leftIndent=12, bulletIndent=2.5, spaceAfter=2.6)
S_BUL2 = st("Bul2", leftIndent=24, bulletIndent=14.5, spaceAfter=2.2, fontSize=9.0)
S_NUM = st("Num", leftIndent=21, bulletIndent=4, spaceAfter=2.6)
S_QUOTE = st("Quote", fontName="DJ", fontSize=8.9, leading=12.6, textColor=colors.HexColor("#33475c"),
             leftIndent=8, rightIndent=6, spaceBefore=2, spaceAfter=2)
S_CELL = st("Cell", fontSize=7.5, leading=10.0, spaceAfter=0)
S_CELLH = st("CellH", fontName="DJ-B", fontSize=7.5, leading=10.0, textColor=colors.white, spaceAfter=0)
S_CELL_S = st("CellS", fontSize=6.9, leading=9.2, spaceAfter=0)
S_CELLH_S = st("CellHS", fontName="DJ-B", fontSize=6.9, leading=9.2, textColor=colors.white, spaceAfter=0)
S_TOC1 = st("TOC1", fontName="DJ-B", fontSize=9.2, leading=13.4, textColor=NAVY, spaceBefore=5)
S_TOC2 = st("TOC2", fontSize=8.3, leading=11.6, leftIndent=13, textColor=colors.HexColor("#2a3a4d"))


# ----------------------------------------------------------------------------- inline markdown
CODE_RE = re.compile(r"`([^`]+)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*([^*<>]+?)\*\*")
ITAL_RE = re.compile(r"(?<![*\w])\*(?!\s)([^*<>]+?)(?<!\s)\*(?![*\w])")
BOLDIT_RE = re.compile(r"\*\*\*([^*<>]+?)\*\*\*")


def inline(text: str, size: float = 9.3, color_hex: str | None = None) -> str:
    text = text.replace("\x02", "\x03")
    store: list[str] = []

    def stash(frag: str) -> str:
        store.append(frag)
        return f"\x00{len(store) - 1}\x00"

    def code_sub(m):
        c = html.escape(clean(m.group(1)), quote=False)
        return stash(f'<font name="DJM" size="{size - 1.1:.1f}" color="#8a1c4a">{c}</font>')

    text = CODE_RE.sub(code_sub, text)

    def link_sub(m):
        label = html.escape(clean(m.group(1)), quote=False)
        url = html.escape(m.group(2), quote=True)
        return stash(f'<a href="{url}" color="#1a56db">{label}</a>')

    text = LINK_RE.sub(link_sub, text)
    text = html.escape(clean(text), quote=False)
    text = BOLDIT_RE.sub(r"<b><i>\1</i></b>", text)
    text = BOLD_RE.sub(r"<b>\1</b>", text)
    text = ITAL_RE.sub(r"<i>\1</i>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: store[int(m.group(1))], text)
    text = text.replace("\x03", "<br/>")
    if color_hex:
        text = f'<font color="{color_hex}">{text}</font>'
    return text


def para(text: str, style=S_BODY) -> Paragraph:
    return Paragraph(inline(text, style.fontSize), style)


# ----------------------------------------------------------------------------- code blocks
def code_flowable(lines: list[str], width: float):
    longest = max((len(l) for l in lines), default=1)
    size = 7.7
    max_chars = (width - 14) / (MONO_ADV * size)
    if longest > max_chars:
        size = max(5.0, size * max_chars / longest)
    wrap_at = int((width - 14) / (MONO_ADV * size))
    wrapped: list[str] = []
    for line in lines:
        line = clean(line).rstrip()
        if len(line) <= wrap_at:
            wrapped.append(line or " ")
        else:
            chunks = textwrap.wrap(line, wrap_at, drop_whitespace=False,
                                   subsequent_indent="    ") or [""]
            wrapped.extend(c or " " for c in chunks)
    body = html.escape("\n".join(wrapped), quote=False)
    style = ParagraphStyle(
        "Code", fontName="DJM", fontSize=size, leading=size * 1.34,
        textColor=colors.HexColor("#1f2933"), backColor=CODEBG,
        borderColor=CODEBR, borderWidth=0.6, borderPadding=(4.5, 5, 4.5, 5),
        leftIndent=0, rightIndent=0, spaceBefore=3, spaceAfter=7)
    return XPreformatted(body, style)


# ----------------------------------------------------------------------------- tables
def _bare_len(cell: str) -> int:
    return len(re.sub(r"[`*]", "", cell))


def _longest_token(cell: str) -> int:
    toks = re.split(r"[\s]+", re.sub(r"[`*]", "", cell))
    return max((len(t) for t in toks), default=0)


def build_table(rows: list[list[str]], width: float):
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]

    # font size falls back if the table simply cannot fit
    for size, small in ((7.5, False), (7.0, True), (6.4, True), (5.9, True)):
        cell = ParagraphStyle("c", parent=S_CELL, fontSize=size, leading=size * 1.34, spaceAfter=0)
        cellh = ParagraphStyle("ch", parent=S_CELLH, fontSize=size, leading=size * 1.34, spaceAfter=0)
        if ncols >= 5 and size == 7.5:
            continue
        if ncols <= 4 and size != 7.5:
            continue
        data = [[Paragraph(inline(c, size), cellh if i == 0 else cell) for c in r]
                for i, r in enumerate(rows)]
        widths = _column_widths(rows, ncols, width, size)
        if widths is not None:
            break
    else:  # pragma: no cover - last resort
        widths = [width / ncols] * ncols

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, RULE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE),
        ("BOX", (0, 0), (-1, 0), 0.6, NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
    ]))
    return t


def _column_widths(rows, ncols, width, size):
    """Allocate widths: a floor from the longest unbreakable token, remainder by content mass."""
    pad = 9.0
    floor, mass = [], []
    for c in range(ncols):
        cells = [r[c] for r in rows if c < len(r)]
        body = cells[1:] if len(cells) > 1 else cells
        longest = max((_longest_token(x) for x in body), default=6)
        lens = sorted(_bare_len(x) for x in body) or [10]
        median = lens[len(lens) // 2]
        header_len = _bare_len(cells[0]) if cells else 0
        floor.append(min(longest * 0.52 * size + pad, 0.42 * width))
        mass.append(min(max(0.65 * median + 0.35 * header_len, 6), 70) ** 0.85)

    total_floor = sum(floor)
    if total_floor > width:
        scale = width / total_floor
        return [f * scale for f in floor]
    free = width - total_floor
    mass_total = sum(mass)
    widths = [floor[i] + free * mass[i] / mass_total for i in range(ncols)]
    minw = 16 * mm if ncols <= 4 else 12 * mm
    return [max(w, min(minw, width / ncols)) for w in widths]


def split_code(lines: list[str], chunk: int) -> list[list[str]]:
    """Split a long listing into chunks, preferring blank-line boundaries."""
    out, start, n = [], 0, len(lines)
    while start < n:
        end = min(start + chunk, n)
        if end < n:
            for probe in range(end, max(start + chunk // 2, start + 1), -1):
                if not lines[probe - 1].strip():
                    end = probe
                    break
        out.append(lines[start:end])
        start = end
    return out


MINIHEAD_RE = re.compile(r"^\*\*([^*<>]{3,140})\*\*\s*(.*)$")


def miniheading(text: str):
    """'**F6. Name** · *P2 · 2 pd*' -> a bold heading with a muted suffix on the same line."""
    if len(text) > 190:
        return None
    m = MINIHEAD_RE.match(text.strip())
    if not m:
        return None
    head, rest = m.group(1), m.group(2).strip()
    if not re.match(r"^([A-Z]\d+|\d+\.|Track|[A-Z][a-z]+ )", head) and "·" not in rest:
        return None
    suffix = f'  <font size="8.2" color="#5a6b7d">{inline(rest, 8.2)}</font>' if rest else ""
    return Paragraph(f'<font name="DJ-B" size="9.8" color="#16324f">{inline(head, 9.8)}</font>{suffix}',
                     ParagraphStyle("mini", fontName="DJ", fontSize=9.4, leading=12.6,
                                    spaceBefore=7, spaceAfter=2.5, keepWithNext=1))


def quote_block(text: str, width: float):
    inner = Paragraph(inline(text, 8.9), S_QUOTE)
    t = Table([[inner]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f7fb")),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ----------------------------------------------------------------------------- markdown parser
def parse(md: str):
    lines = md.split("\n")
    i, n = 0, len(lines)
    out = []
    while i < n:
        line = lines[i]

        if line.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(("code", buf))
            continue

        if not line.strip():
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            out.append((f"h{len(m.group(1))}", m.group(2).strip()))
            i += 1
            continue

        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            out.append(("hr", ""))
            i += 1
            continue

        if line.lstrip().startswith("|") and "|" in line:
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                raw = lines[i].strip().strip("|")
                raw = raw.replace("\\|", "\x01")          # protect escaped pipes
                if not re.match(r"^[\s:|\-]+$", raw):
                    cells = [c.strip().replace("\x01", "|") for c in raw.split("|")]
                    rows.append(cells)
                i += 1
            out.append(("table", rows))
            continue

        if line.lstrip().startswith(">"):
            buf = []
            while i < n and lines[i].lstrip().startswith(">"):
                buf.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append(("quote", " ".join(buf)))
            continue

        m = re.match(r"^(\s*)([-*+])\s+(.*)$", line)
        if m:
            indent = len(m.group(1))
            out.append(("bul", (2 if indent >= 2 else 1, m.group(3).strip())))
            i += 1
            continue

        m = re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", line)
        if m:
            out.append(("num", (m.group(2), m.group(3).strip())))
            i += 1
            continue

        # paragraph: gather until blank / block start
        buf = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|```|\||>|\s*[-*+]\s|\s*\d+[.)]\s*)", lines[i]):
            nxt = lines[i].strip()
            # hard break before "**Key:**" metadata lines
            sep = "\x02" if re.match(r"^\*\*[^*]+\*\*\s*[:.]", nxt) else " "
            buf.append(sep + nxt)
            i += 1
        out.append(("p", "".join(buf)))
    return out


# ----------------------------------------------------------------------------- doc template
class Doc(BaseDocTemplate):
    def __init__(self, path, **kw):
        super().__init__(path, pagesize=A4, leftMargin=LM, rightMargin=RM,
                         topMargin=TM, bottomMargin=BM, title=kw.pop("doctitle", ""),
                         author="Arena.ai Agent", subject="MedXChAIn audit & roadmap",
                         creator="md2pdf (reportlab)", **kw)
        self.part = ""
        cover = PageTemplate(id="Cover", frames=[Frame(LM, BM, USABLE, PAGE_H - TM - BM, id="c")])
        body = PageTemplate(id="Body", frames=[Frame(LM, BM, USABLE, PAGE_H - TM - BM, id="b")],
                            onPage=self.decorate)
        self.addPageTemplates([cover, body])

    def decorate(self, canv, doc):
        canv.saveState()
        canv.setFont("DJ", 7.2)
        canv.setFillColor(MUTED)
        canv.drawString(LM, PAGE_H - 13 * mm, "MedXChAIn — Technical Audit & Enhancement Roadmap")
        canv.drawRightString(PAGE_W - RM, PAGE_H - 13 * mm, self.part)
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.5)
        canv.line(LM, PAGE_H - 15.2 * mm, PAGE_W - RM, PAGE_H - 15.2 * mm)
        canv.line(LM, 12.5 * mm, PAGE_W - RM, 12.5 * mm)
        canv.setFont("DJ", 7.0)
        canv.drawString(LM, 8.6 * mm, "Repo SuhasRam356/…-Distributed-Hospitals  ·  baseline b0b8941  ·  audit 2026-10-22")
        canv.drawRightString(PAGE_W - RM, 8.6 * mm, f"page {doc.page}")
        canv.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        name = flowable.style.name
        if name in ("H1", "H2"):
            label = flowable.getPlainText()
            if label.strip().lower() != "contents":
                self._seq = getattr(self, "_seq", 0) + 1
                key = f"sec{self._seq}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(label, key,
                                          level=0 if name == "H1" else 1, closed=False)
        if name == "H1":
            label = flowable.getPlainText()
            if label.strip().lower() == "contents":
                return
            self.part = label[:60]
            self.notify("TOCEntry", (0, label, self.page))
        elif name == "H2":
            self.notify("TOCEntry", (1, flowable.getPlainText(), self.page))


# ----------------------------------------------------------------------------- emission
def emit_blocks(blocks, story, width):
    for kind, val in blocks:
        if kind == "h1":
            story.append(Spacer(1, 8))
            story.append(Paragraph(inline(val, 19), S_H1))
            story.append(HRFlowable(width="100%", thickness=1.4, color=NAVY,
                                    spaceBefore=1, spaceAfter=10))
        elif kind == "h2":
            story.append(Paragraph(inline(val, 12.8), S_H2))
        elif kind == "h3":
            story.append(Paragraph(inline(val, 10.4), S_H3))
        elif kind == "h4":
            story.append(Paragraph(inline(val, 9.4), S_H4))
        elif kind == "p":
            story.append(miniheading(val) or para(val))
        elif kind == "bul":
            lvl, text = val
            style = S_BUL2 if lvl == 2 else S_BUL
            story.append(Paragraph(inline(text, style.fontSize), style, bulletText="•"))
        elif kind == "num":
            num, text = val
            story.append(Paragraph(inline(text, 9.3), S_NUM, bulletText=f"{num}."))
        elif kind == "quote":
            story.append(Spacer(1, 2))
            story.append(quote_block(val, width))
            story.append(Spacer(1, 5))
        elif kind == "code":
            if val:
                if len(val) <= 58:
                    story.append(KeepTogether(code_flowable(val, width)))
                else:
                    # long listings flow across pages, split on blank lines when possible
                    for idx, piece in enumerate(split_code(val, 46)):
                        if idx:
                            piece = ["  …"] + piece
                        story.append(code_flowable(piece, width))
        elif kind == "table":
            if len(val) > 1:
                tbl = build_table(val, width)
                if len(val) <= 3:                       # tiny: keep with its caption
                    story.append(KeepTogether([Spacer(1, 2), tbl, Spacer(1, 8)]))
                else:
                    story.append(Spacer(1, 2))
                    story.append(CondPageBreak(45 * mm))
                    story.append(tbl)
                    story.append(Spacer(1, 8))
        elif kind == "hr":
            story.append(HRFlowable(width="100%", thickness=0.7, color=RULE,
                                    spaceBefore=6, spaceAfter=6))


# ----------------------------------------------------------------------------- cover
def cover(width: float):
    s = []
    s.append(Spacer(1, 26 * mm))
    s.append(Paragraph('<font color="#1a56db" size="10"><b>MEDICAL AI · FEDERATED LEARNING · BLOCKCHAIN</b></font>',
                       ParagraphStyle("kicker", fontName="DJ-B", fontSize=10, leading=14)))
    s.append(Spacer(1, 5 * mm))
    s.append(Paragraph('<font color="#0f2f57" size="34"><b>MedXChAIn</b></font>',
                       ParagraphStyle("t1", fontName="DJ-B", fontSize=34, leading=40)))
    s.append(Paragraph('<font color="#16324f" size="19">Technical Audit &amp; Enhancement Roadmap</font>',
                       ParagraphStyle("t2", fontName="DJ-B", fontSize=19, leading=26)))
    s.append(Spacer(1, 4 * mm))
    s.append(HRFlowable(width="100%", thickness=2.4, color=BLUE, spaceAfter=6))
    s.append(Paragraph('<font color="#5a6b7d" size="9.6">A complete engineering review of a decentralized, '
                       'privacy-preserving federated learning system for distributed hospitals — '
                       'followed by a build-ready plan to make it real.</font>',
                       ParagraphStyle("sub", fontName="DJ", fontSize=9.6, leading=14)))
    s.append(Spacer(1, 12 * mm))

    meta = [
        ["Repository", "SuhasRam356/Decentralized-Privacy-Preserving-Federated-Learning-…-Hospitals"],
        ["Baseline commit", "b0b8941044e807ff0ee628ad66ab9468d94ea1bd  (single commit, 2026-10-22)"],
        ["Branch audited", "arena/144b2365-decentralized-privacy-preservi"],
        ["Method", "Full source read · static analysis · live execution of contracts (solc 0.8.28 + Hardhat), "
                   "the IPFS emulator (4 ports), and every dashboard API endpoint"],
        ["Scope", "66 tracked files · 137 MB working tree · 573 LOC Python · 510 LOC Solidity · "
                  "3 638 LOC frontend · 14 contract tests"],
        ["Prepared for", "An implementing agent (human or AI) — see Part 0 for the working contract"],
        ["Companion files", "TECHNICAL_AUDIT.md · ENHANCEMENT_ROADMAP.md · agent_backlog.yaml"],
    ]
    rows = [[Paragraph(f'<b>{k}</b>', ParagraphStyle("mk", fontName="DJ-B", fontSize=8.4, leading=11.6,
                                                     textColor=NAVY)),
             Paragraph(html.escape(v), ParagraphStyle("mv", fontName="DJ", fontSize=8.4, leading=11.6))]
            for k, v in meta]
    t = Table(rows, colWidths=[30 * mm, width - 30 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    s.append(t)
    s.append(Spacer(1, 10 * mm))

    contents = [
        ["Part", "Contents", "Use it for"],
        ["0", "Agent briefing — mission, 8 non-negotiable rules, gates, verification commands, "
              "8 landmines found by execution, definition of done, reporting format",
         "Hand this to the implementing agent first"],
        ["I", "Technical audit — verdict, 19-row documentation-drift matrix, 27 findings (C/H/M/L) "
              "with reproducible evidence, live-execution transcripts, privacy & legal review",
         "Understand what is wrong and why it matters"],
        ["II", "Enhancement roadmap — 12 quick wins, 11 tracks, target architecture, 18 new features, "
               "SLOs, security, compliance, first 10 PRs, what not to build",
         "Plan and execute the rebuild"],
        ["A", "Backlog summary — 18 tasks with priority, findings closed, effort and dependencies "
              "(full machine-readable version in agent_backlog.yaml)",
         "Track progress task by task"],
    ]
    rows2 = [[Paragraph(inline(c, 7.2), S_CELLH_S if i == 0 else S_CELL_S) for c in r]
             for i, r in enumerate(contents)]
    t2 = Table(rows2, colWidths=[11 * mm, (width - 11 * mm) * 0.66, (width - 11 * mm) * 0.34],
               repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("GRID", (0, 0), (-1, -1), 0.3, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    s.append(t2)
    s.append(Spacer(1, 8 * mm))
    verdict = Paragraph(
        '<font color="#8a1c4a" size="8.8"><b>Headline verdict:</b> an impressive demonstration shell around a '
        'non-functional scientific core. The UI, contract layout, CID math and documentation are real work; '
        'the federated learning, on-chain coordination, IPFS integration and clinical inference are simulated, '
        'stubbed or disconnected — and 19 documented claims contradict the code.</font>',
        ParagraphStyle("v", fontName="DJ", fontSize=8.8, leading=12.6, backColor=colors.HexColor("#fdf3f6"),
                       borderColor=colors.HexColor("#e7c3d0"), borderWidth=0.6, borderPadding=7,
                       leftIndent=0, rightIndent=0))
    s.append(verdict)
    return s


# ----------------------------------------------------------------------------- main
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="MEDXCHAIN_AUDIT_AND_ROADMAP.pdf")
    args = ap.parse_args()
    root = Path(args.repo)
    out = Path(args.out)
    width = USABLE

    story = cover(width)
    story.append(PageBreak())

    # TOC
    toc = TableOfContents()
    toc.levelStyles = [S_TOC1, S_TOC2]
    toc.dotsMinLevel = 0
    story.append(Paragraph("Contents", S_H1))
    story.append(HRFlowable(width="100%", thickness=1.4, color=NAVY, spaceBefore=1, spaceAfter=10))
    story.append(toc)
    story.append(PageBreak())

    part0 = (root / "AGENT_BRIEF.md").read_text(encoding="utf-8")
    audit = (root / "TECHNICAL_AUDIT.md").read_text(encoding="utf-8")
    road = (root / "ENHANCEMENT_ROADMAP.md").read_text(encoding="utf-8")

    part0 = re.sub(r"^#\s+Agent Briefing — MedXChAIn remediation\s*$",
                   "# Part 0 — Agent Briefing (read before touching code)",
                   part0, count=1, flags=re.M)
    audit = re.sub(r"^#\s+MedXChAIn — Complete Technical Audit\s*$",
                   "# Part I — Technical Audit", audit, count=1, flags=re.M)
    road = re.sub(r"^#\s+MedXChAIn 2\.0 — Complete Enhancement & New-Feature Plan\s*$",
                  "# Part II — Enhancement & New-Feature Plan\n\n*What to build, in what order, and exactly how — "
                  "every item sized, sequenced and tied to a finding from Part I.*", road, count=1, flags=re.M)

    for index, md in enumerate((part0, audit, road)):
        if index:                       # start a new part only if the page is nearly full
            story.append(CondPageBreak(150 * mm))
        emit_blocks(parse(md), story, width)

    # Appendix — backlog summary (kept on one page with its heading)
    appendix = [
        Spacer(1, 8),
        Paragraph("Appendix A — Task backlog summary", S_H1),
        HRFlowable(width="100%", thickness=1.4, color=NAVY, spaceBefore=1, spaceAfter=10),
    ]
    appendix_body: list = []
    emit_blocks(parse(
        "The full machine-readable version — acceptance criteria, verify commands, file targets, stop "
        "conditions and regression guards — is `agent_backlog.yaml` in the repository root. This is the "
        "human-readable summary; the YAML is the contract.\n\n"
        "| ID | P | Task | Closes | pd | Depends |\n"
        "| :--- | :-- | :--- | :--- | --: | :--- |\n"
        "| T-01 | P0 | Remove fabricated metrics from the status API | C-02 | 0.5 | — |\n"
        "| T-02 | P0 | Harden ModelUpdateTracker (empty CID, quorum 0, zero aggregator) | C-05, H-03, H-04 | 1 | — |\n"
        "| T-03 | P0 | Stop serving substring-matching diagnosis | C-04 | 0.5 | — |\n"
        "| T-04 | P0 | Strip PII columns from committed datasets | C-03, M-04 | 1 | — |\n"
        "| T-05 | P0 | Deduplicate repo assets, fix ignore rules | M-04 | 0.5 | — |\n"
        "| T-06 | P0 | Correct IPFS client: multipart, verify, no invented CIDs | H-02 | 1 | — |\n"
        "| T-07 | P0 | Packaging, linting, CI skeleton | M-03 | 2 | — |\n"
        "| T-08 | P1 | Real local training, seeded, metric-producing | C-01, M-05, M-09 | 3 | T-07 |\n"
        "| T-09 | P1 | Single checkpoint format + LoRA adapters | H-06, H-08 | 2 | T-08 |\n"
        "| T-10 | P1 | Weighted FedAvg + robust aggregators + property tests | M-01, H-08 | 2 | T-09 |\n"
        "| T-11 | P1 | FederatedRound.sol v2: roles, Merkle root, challenge window | C-05, H-04, H-07, M-10 | 4 | T-02 |\n"
        "| T-12 | P1 | Python chain client + event indexer; pipeline really submits | H-01 | 3 | T-11 |\n"
        "| T-13 | P1 | FastAPI service, Postgres schema, round state machine | H-05, M-07 | 4 | T-07 |\n"
        "| T-14 | P1 | Bind the dashboard to real data; zero literals | M-01 | 3 | T-13 |\n"
        "| T-15 | P1 | Real diagnosis with calibration, conformal sets, abstention | C-04, M-06 | 3 | T-09, T-13 |\n"
        "| T-16 | P2 | DP-SGD over adapters + ε ledger | M-06 | 3 | T-09, T-13 |\n"
        "| T-17 | P2 | Encrypted artefacts before IPFS + crypto-shredding | M-06 | 2 | T-06, T-12 |\n"
        "| T-18 | P2 | Round manifest, replay, signed audit export | M-05, M-09 | 3 | T-12, T-13 |\n"
        "\n**Total: 37 person-days.** P0 (T-01…T-07, 6.5 pd) makes the project honest; P1 (T-08…T-15, "
        "24 pd) closes the loop; P2 (T-16…T-18, 8 pd) makes it credible. Start at T-01 and do not skip a gate.\n"
    ), appendix_body, width)
    story.append(KeepTogether(appendix + appendix_body))

    doc = Doc(str(out), doctitle="MedXChAIn — Technical Audit & Enhancement Roadmap")
    doc.multiBuild(story)
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
