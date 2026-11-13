#!/usr/bin/env python3
"""render_manuscript_pdf.py — render the RDHEI manuscript markdown to PDF.

Usage: python3 render_manuscript_pdf.py <input.md> <output.pdf>

No LaTeX/pandoc/weasyprint is available in this environment, so this renderer
uses reportlab directly. Supported markdown: ATX headings, paragraphs, pipe
tables, fenced code blocks (incl. mermaid), bullet/numbered lists, images,
horizontal rules, inline bold/italic/code/links. Inline LaTeX ($...$ / $$...$$)
is rendered as monospace source text (no math engine is installed) — this is a
documented rendering limitation of the PDF, not of the markdown source.
"""
import re
import sys
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, Image,
                                KeepTogether, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
pdfmetrics.registerFont(TTFont("DJS", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DJS-B", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DJM", str(FONT_DIR / "DejaVuSansMono.ttf")))
pdfmetrics.registerFont(TTFont("DJM-B", str(FONT_DIR / "DejaVuSansMono-Bold.ttf")))
pdfmetrics.registerFontFamily("DJS", normal="DJS", bold="DJS-B",
                              italic="DJS", boldItalic="DJS-B")
pdfmetrics.registerFontFamily("DJM", normal="DJM", bold="DJM-B",
                              italic="DJM", boldItalic="DJM-B")

PAGE_W, PAGE_H = A4
MARGIN = 1.7 * cm
USABLE = PAGE_W - 2 * MARGIN

S = {
    "h1": ParagraphStyle("h1", fontName="DJS-B", fontSize=15.5, leading=19,
                         spaceBefore=14, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="DJS-B", fontSize=12.5, leading=16,
                         spaceBefore=13, spaceAfter=6, textColor=colors.HexColor("#102a43")),
    "h3": ParagraphStyle("h3", fontName="DJS-B", fontSize=10.8, leading=14,
                         spaceBefore=10, spaceAfter=5, textColor=colors.HexColor("#243b53")),
    "h4": ParagraphStyle("h4", fontName="DJS-B", fontSize=10, leading=13,
                         spaceBefore=8, spaceAfter=4),
    "p": ParagraphStyle("p", fontName="DJS", fontSize=8.9, leading=12.4,
                        alignment=TA_JUSTIFY, spaceAfter=5),
    "bullet": ParagraphStyle("bullet", fontName="DJS", fontSize=8.9, leading=12.4,
                             alignment=TA_JUSTIFY, spaceAfter=3,
                             leftIndent=12, bulletIndent=2),
    "code": ParagraphStyle("code", fontName="DJM", fontSize=6.6, leading=8.6,
                           backColor=colors.HexColor("#f2f4f7"),
                           borderPadding=4, spaceBefore=4, spaceAfter=6,
                           wordWrap="CJK"),
    "cap": ParagraphStyle("cap", fontName="DJS", fontSize=8.0, leading=11,
                          alignment=TA_JUSTIFY, spaceBefore=3, spaceAfter=8,
                          textColor=colors.HexColor("#334e68")),
    "cell": ParagraphStyle("cell", fontName="DJS", fontSize=7.0, leading=8.8),
    "cellb": ParagraphStyle("cellb", fontName="DJS-B", fontSize=7.0, leading=8.8),
    "cellr": ParagraphStyle("cellr", fontName="DJS", fontSize=7.0, leading=8.8,
                            alignment=TA_RIGHT),
    "cellrb": ParagraphStyle("cellrb", fontName="DJS-B", fontSize=7.0, leading=8.8,
                             alignment=TA_RIGHT),
}


def inline(text):
    """Convert inline markdown to reportlab mini-HTML."""
    out = escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r'<font face="DJM" size="7.6">\1</font>', out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    out = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", out)
    # inline LaTeX: keep the source in monospace (no math engine available)
    out = re.sub(r"\$\$(.+?)\$\$", r'<font face="DJM" size="7.8">[\1]</font>', out, flags=re.S)
    out = re.sub(r"(?<!\$)\$([^$\n]+)\$(?!\$)", r'<font face="DJM" size="7.8">[\1]</font>', out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", out)
    out = out.replace("$$", "")
    return out


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render_table(rows, story):
    header = rows[0]
    if len(rows) > 1 and set(rows[1][0]) <= set("-: "):
        sep, body = rows[1], rows[2:]
    else:
        sep, body = [], rows[1:]
    aligns = ["RIGHT" if (j < len(sep) and sep[j].endswith(":") and not sep[j].startswith(":"))
              else "LEFT" for j in range(len(header))]
    ncols = max(len(r) for r in rows)

    def cell_para(txt, col, bold=False):
        if bold:
            style = S["cellb"]
        elif col < len(aligns) and aligns[col] == "RIGHT":
            style = S["cellr"]
        else:
            style = S["cell"]
        return Paragraph(inline(txt) or "&nbsp;", style)

    data = [[cell_para(c, j, bold=True) for j, c in enumerate(header)]
            + [""] * (ncols - len(header))]
    for r in body:
        data.append([cell_para(c, j) for j, c in enumerate(r)] + [""] * (ncols - len(r)))
    # column widths: proportional to content, capped
    weights = []
    for j in range(ncols):
        w = max([len(header[j]) if j < len(header) else 0] +
                [len(r[j]) if j < len(r) else 0 for r in body]) + 2
        weights.append(min(max(w, 5), 34))
    total = sum(weights)
    widths = [USABLE * w / total for w in weights]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9fb3c8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eef5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
    ]))
    story.append(t)
    story.append(Spacer(1, 7))


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("DJS", 7)
    canvas.setFillColor(colors.HexColor("#627d98"))
    canvas.drawString(MARGIN, MARGIN * 0.55,
                      "CNN-Based RDHEI — revised manuscript 2026-10-20 (READY WITH DISCLOSED LIMITATIONS)")
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN * 0.55, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def build(md_path, pdf_path):
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    story = []
    i, n = 0, len(lines)
    para = []

    def flush():
        if para:
            story.append(Paragraph(inline(" ".join(x.strip() for x in para)), S["p"]))
            para.clear()

    while i < n:
        line = lines[i]
        if line.startswith("```"):
            flush()
            buf = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            story.append(Paragraph(escape("\n".join(buf)).replace(" ", "&nbsp;").replace("\n", "<br/>")
                                   or "&nbsp;", S["code"]))
            continue
        if re.match(r"^#{1,4}\s", line):
            flush()
            level = len(line) - len(line.lstrip("#"))
            text = line.lstrip("#").strip()
            story.append(Paragraph(inline(text), S[f"h{min(level, 4)}"]))
            i += 1
            continue
        if line.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            flush()
            rows = []
            while i < n and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            render_table(rows, story)
            continue
        if re.match(r"^!\[.*\]\(.+\)\s*$", line):
            flush()
            src = re.match(r"^!\[.*\]\((.+)\)\s*$", line).group(1)
            img_path = Path(md_path).resolve().parent / src
            if img_path.exists():
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(img_path) as im:
                        w, h = im.size
                    max_w, max_h = USABLE, 8.2 * cm
                    scale = min(max_w / w, max_h / h, 1.0)
                    story.append(Image(str(img_path), width=w * scale, height=h * scale,
                                       hAlign="CENTER"))
                    story.append(Spacer(1, 6))
                except Exception as exc:  # pragma: no cover
                    story.append(Paragraph(f"[figure missing: {src} — {exc}]", S["cap"]))
            i += 1
            continue
        if re.match(r"^---+\s*$", line):
            flush()
            story.append(HRFlowable(width="100%", thickness=0.6,
                                    color=colors.HexColor("#bcccdc"),
                                    spaceBefore=6, spaceAfter=6))
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush()
            bullet = re.sub(r"^\s*[-*]\s+", "", line)
            story.append(Paragraph(inline(bullet), S["bullet"], bulletText="•"))
            i += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            flush()
            m = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
            story.append(Paragraph(inline(m.group(3)), S["bullet"],
                                   bulletText=m.group(2) + "."))
            i += 1
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        para.append(line)
        i += 1
    flush()

    doc = BaseDocTemplate(pdf_path, pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=MARGIN,
                          title=Path(md_path).stem,
                          author="RDHEI project — revised manuscript 2026-10-20")
    frame = Frame(MARGIN, MARGIN, USABLE, PAGE_H - 2 * MARGIN, id="main")
    doc.addPageTemplates([PageTemplate(id="std", frames=[frame], onPage=on_page)])
    doc.build(story)
    print(f"WROTE {pdf_path} ({Path(pdf_path).stat().st_size} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    build(sys.argv[1], sys.argv[2])
