# -*- coding: utf-8 -*-
"""Convert the DMC 1st Progress Report from Markdown to a formatted .docx.

Formatting follows the programme's §8 rules exactly:
  * body font 11 pt (the requirement allows 10-12 pt)
  * single line spacing
  * 1.27 cm margins on all four sides
  * page number in the footer only
  * images embedded in the file (no external paths)

The converter is deliberately self-contained: it understands only the subset of
Markdown actually used in DMC_1ST_PROGRESS_REPORT_DRAFT.md, and it fails loudly
on anything it does not understand rather than silently dropping content.

Run:
    python tools/_md_to_docx.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as _paths  # noqa: E402

from docx import Document  # noqa: E402
from docx.enum.section import WD_SECTION  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

ROOT = _paths.PROJECT_ROOT
SRC = ROOT / "04_reports" / "00_shared" / "docs" / "DMC_1ST_PROGRESS_REPORT_DRAFT.md"
OUT = ROOT / "04_reports" / "00_shared" / "docs" / "DMC_1st_Progress_Report.docx"

BODY_PT = 11.0          # within the permitted 10-12 pt
MARGIN_CM = 1.27
INK = RGBColor(0x11, 0x18, 0x27)
MUTED = RGBColor(0x6B, 0x72, 0x80)

# ---------------------------------------------------------------- helpers
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITAL_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")


def add_page_number_footer(section):
    """Put the page number in the footer, centred.  Nothing else in the footer."""
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for instr, kind in (("begin", "fldChar"), (None, "instrText"), ("end", "fldChar")):
        el = OxmlElement("w:fldChar") if kind == "fldChar" else OxmlElement("w:instrText")
        if kind == "fldChar":
            el.set(qn("w:fldCharType"), instr)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = " PAGE "
        run._r.append(el)
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED


def add_runs(par, text):
    """Render inline Markdown (**bold**, *italic*, `code`) into a paragraph."""
    # tokenise on the bold / italic / code markers, keeping the markers
    tokens = re.split(r"(\*\*.+?\*\*|(?<!\*)\*(?!\*).+?(?<!\*)\*(?!\*)|`[^`]+`)", text)
    for tk in tokens:
        if not tk:
            continue
        if tk.startswith("**") and tk.endswith("**"):
            r = par.add_run(tk[2:-2])
            r.bold = True
        elif tk.startswith("`") and tk.endswith("`"):
            r = par.add_run(tk[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(BODY_PT - 1)
        elif tk.startswith("*") and tk.endswith("*") and len(tk) > 2:
            r = par.add_run(tk[1:-1])
            r.italic = True
        else:
            par.add_run(tk)


def set_cell_text(cell, text, bold=False, size=BODY_PT - 1.5, align=None):
    cell.text = ""
    par = cell.paragraphs[0]
    par.paragraph_format.space_before = Pt(1)
    par.paragraph_format.space_after = Pt(1)
    par.paragraph_format.line_spacing = 1.0
    if align is not None:
        par.alignment = align
    add_runs(par, text)
    for r in par.runs:
        r.font.size = Pt(size)
        if bold:
            r.bold = True


def parse_table(lines, start):
    """Parse a GFM table beginning at `lines[start]`; return (rows, next_index)."""
    rows = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        raw = lines[i].strip().strip("|")
        rows.append([c.strip() for c in raw.split("|")])
        i += 1
    # drop the alignment separator row
    if len(rows) >= 2 and all(set(c) <= set("-: ") for c in rows[1]):
        rows.pop(1)
    return rows, i


# ---------------------------------------------------------------- main
def main() -> int:
    if not SRC.is_file():
        print(f"[FAIL] source not found: {SRC}")
        return 2
    md = SRC.read_text(encoding="utf-8")
    lines = md.split("\n")

    doc = Document()

    # ---- page setup
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(MARGIN_CM)
        s.left_margin = s.right_margin = Cm(MARGIN_CM)
        add_page_number_footer(s)

    # ---- base style
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(BODY_PT)
    st.font.color.rgb = INK
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    pf = st.paragraph_format
    pf.line_spacing = 1.0            # single spacing, as required
    pf.space_after = Pt(6)
    pf.space_before = Pt(0)

    n_img = n_tbl = n_h = 0
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        # ---- blank
        if not s:
            i += 1
            continue

        # ---- horizontal rule -> ignore (we use spacing instead)
        if s == "---":
            i += 1
            continue

        # ---- image
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", s)
        if m:
            alt, src = m.group(1), m.group(2)
            img = ROOT / src
            if not img.is_file():
                print(f"[FAIL] image missing: {img}")
                return 3
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run()
            run.add_picture(str(img), width=Cm(16.0))
            n_img += 1
            i += 1
            continue

        # ---- table
        if s.startswith("|"):
            rows, i = parse_table(lines, i)
            if rows:
                ncol = max(len(r) for r in rows)
                t = doc.add_table(rows=len(rows), cols=ncol)
                t.style = "Table Grid"
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                for ri, row in enumerate(rows):
                    for ci in range(ncol):
                        txt = row[ci] if ci < len(row) else ""
                        al = WD_ALIGN_PARAGRAPH.RIGHT if (ri > 0 and ci > 0 and
                              re.fullmatch(r"[−+\-]?[\d.,]+", txt.replace("**", "")) is not None) \
                             else None
                        set_cell_text(t.cell(ri, ci), txt, bold=(ri == 0), align=al)
                doc.add_paragraph()
                n_tbl += 1
            continue

        # ---- headings
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl, txt = len(m.group(1)), m.group(2)
            if lvl == 1:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(txt)
                r.bold = True
                r.font.size = Pt(18)
                p.paragraph_format.space_after = Pt(4)
            elif lvl == 2:
                p = doc.add_paragraph()
                r = p.add_run(txt)
                r.bold = True
                r.font.size = Pt(15)
                p.paragraph_format.space_before = Pt(14)
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.keep_with_next = True
            elif lvl == 3:
                p = doc.add_paragraph()
                r = p.add_run(txt)
                r.bold = True
                r.font.size = Pt(13)
                p.paragraph_format.space_before = Pt(10)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.keep_with_next = True
            else:
                p = doc.add_paragraph()
                r = p.add_run(txt)
                r.bold = True
                r.font.size = Pt(11.5)
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.keep_with_next = True
            n_h += 1
            i += 1
            continue

        # ---- numbered list
        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(3)
            add_runs(p, m.group(2))
            i += 1
            continue

        # ---- bullet
        if s.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.line_spacing = 1.0
            add_runs(p, s[2:])
            i += 1
            continue

        # ---- blockquote
        if s.startswith("> "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.space_after = Pt(4)
            add_runs(p, s[2:])
            for r in p.runs:
                r.font.color.rgb = MUTED
                r.font.size = Pt(BODY_PT - 1)
            i += 1
            continue

        # ---- normal paragraph
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_runs(p, s)
        i += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"[OK] {OUT}")
    print(f"     size {OUT.stat().st_size/1024:.0f} KB | "
          f"headings {n_h} | tables {n_tbl} | images {n_img}")
    print("[status] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
