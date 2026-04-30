"""
exporter.py — Convert a graded session JSON into PDF, CSV, Excel, Word, or JSON.
"""

import io
import json
import os
from typing import Any, Dict

import pandas as pd
from fpdf import FPDF
from docx import Document
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# PDF font setup — prefer Unicode-capable Arial when available (Windows)
# ---------------------------------------------------------------------------

_WIN_FONTS = "C:/Windows/Fonts"
_ARIAL_MAP = {
    "":   os.path.join(_WIN_FONTS, "arial.ttf"),
    "B":  os.path.join(_WIN_FONTS, "arialbd.ttf"),
    "I":  os.path.join(_WIN_FONTS, "ariali.ttf"),
    "BI": os.path.join(_WIN_FONTS, "arialbi.ttf"),
}
_USE_ARIAL = all(os.path.exists(p) for p in _ARIAL_MAP.values())
_PDF_FONT  = "Arial" if _USE_ARIAL else "Helvetica"

# Replacement table for non-Latin-1 characters (fallback when core font is used)
_LATIN1_MAP = [
    ("\u2014", "--"), ("\u2013", "-"),
    ("\u2018", "'"),  ("\u2019", "'"),
    ("\u201c", '"'),  ("\u201d", '"'),
    ("\u2026", "..."), ("\u00a0", " "),
]

def _pdf_safe(v) -> str:
    """Return a Latin-1-safe string (used when Arial is unavailable)."""
    s = "" if v is None else str(v)
    for a, b in _LATIN1_MAP:
        s = s.replace(a, b)
    return s.encode("latin-1", errors="replace").decode("latin-1")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade_str(grade) -> str:
    return str(grade) if grade is not None else "—"


def _avg_str(sentence) -> str:
    grades = [t["grade"] for t in sentence["triples"] if t.get("grade") is not None]
    if not grades:
        return "Not graded"
    avg = sum(grades) / len(grades)
    return f"{avg:.1f}"


def _sentence_metric(sentence, key: str, legacy_triple_key: str):
    value = sentence.get(key)
    if value is None and key == "external_relation":
        value = sentence.get("relation")
    if value is None:
        for triple in sentence.get("triples", []):
            triple_value = triple.get(legacy_triple_key)
            if triple_value is not None:
                return triple_value
    return value


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def to_json(session: Dict[str, Any]) -> bytes:
    return json.dumps(session, indent=2, ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# CSV  (flat, one row per triple)
# ---------------------------------------------------------------------------

def to_csv(session: Dict[str, Any]) -> bytes:
    rows = []
    for s in session.get("sentences", []):
        sent_grade = _avg_str(s)
        sent_completeness = _sentence_metric(s, "completeness", "completeness")
        sent_external_relation = _sentence_metric(s, "external_relation", "relation")
        for t in s.get("triples", []):
            rows.append({
                "Sentence ID":       s["id"],
                "Sentence":          s["text"],
                "Suggestion":        s.get("suggestion", ""),
                "Sentence Grade":    sent_grade,
                "Completeness":      _grade_str(sent_completeness),
                "External Relation":  _grade_str(sent_external_relation),
                "Triple ID":         t["id"],
                "Subject":           t["subject"],
                "Predicate":         t["predicate"],
                "Object":            t["object"],
                "Triple Grade":      _grade_str(t.get("grade")),
            })
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# Excel  (two sheets: Summary + Details)
# ---------------------------------------------------------------------------

_HEADER_FILL   = PatternFill("solid", fgColor="1E3A5F")
_ALT_FILL      = PatternFill("solid", fgColor="EBF2FA")
_ACCENT_FILL   = PatternFill("solid", fgColor="D6E4F0")
_HEADER_FONT   = Font(bold=True, color="FFFFFF", size=11)
_TITLE_FONT    = Font(bold=True, size=14, color="1E3A5F")
_THIN_BORDER_SIDE = Side(style="thin", color="CCCCCC")
_THIN_BORDER   = Border(
    left=_THIN_BORDER_SIDE, right=_THIN_BORDER_SIDE,
    top=_THIN_BORDER_SIDE, bottom=_THIN_BORDER_SIDE
)


def _style_header_row(ws, row_num: int, num_cols: int):
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.fill   = _HEADER_FILL
        cell.font   = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _THIN_BORDER


def _style_data_cell(cell, alt: bool = False):
    cell.fill      = _ALT_FILL if alt else PatternFill()
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    cell.border    = _THIN_BORDER


def to_excel(session: Dict[str, Any]) -> bytes:
    wb = Workbook()

    # ── Sheet 1: Summary (one row per sentence) ──────────────────────────
    ws_sum = wb.active
    ws_sum.title = "Summary"
    ws_sum["A1"] = "Ontology Triple Grading — Summary"
    ws_sum["A1"].font = _TITLE_FONT
    ws_sum.merge_cells("A1:G1")
    ws_sum.row_dimensions[1].height = 26

    headers_sum = ["Sentence ID", "Sentence", "# Triples", "Sentence Grade", "Completeness", "External Relation", "Suggestion"]
    ws_sum.append([])          # blank row 2
    ws_sum.append(headers_sum) # row 3
    _style_header_row(ws_sum, 3, len(headers_sum))
    ws_sum.row_dimensions[3].height = 22

    for i, s in enumerate(session.get("sentences", []), start=1):
        sent_completeness = _sentence_metric(s, "completeness", "completeness")
        sent_external_relation = _sentence_metric(s, "external_relation", "relation")
        row = [
            s["id"],
            s["text"],
            len(s.get("triples", [])),
            _avg_str(s),
            _grade_str(sent_completeness),
            _grade_str(sent_external_relation),
            s.get("suggestion", ""),
        ]
        ws_sum.append(row)
        row_num = i + 3
        alt = i % 2 == 0
        for col in range(1, len(headers_sum) + 1):
            _style_data_cell(ws_sum.cell(row=row_num, column=col), alt=alt)

    ws_sum.column_dimensions["A"].width = 12
    ws_sum.column_dimensions["B"].width = 60
    ws_sum.column_dimensions["C"].width = 10
    ws_sum.column_dimensions["D"].width = 14
    ws_sum.column_dimensions["E"].width = 14
    ws_sum.column_dimensions["F"].width = 16
    ws_sum.column_dimensions["G"].width = 50

    # ── Sheet 2: Details (one row per triple) ───────────────────────────
    ws_det = wb.create_sheet("Details")
    ws_det["A1"] = "Ontology Triple Grading — Details"
    ws_det["A1"].font = _TITLE_FONT
    ws_det.merge_cells("A1:K1")
    ws_det.row_dimensions[1].height = 26

    headers_det = [
        "Sentence ID", "Sentence", "Sentence Grade", "Completeness", "External Relation", "Suggestion",
        "Triple ID", "Subject", "Predicate", "Object", "Triple Grade"
    ]
    ws_det.append([])
    ws_det.append(headers_det)
    _style_header_row(ws_det, 3, len(headers_det))
    ws_det.row_dimensions[3].height = 22

    row_idx = 4
    for s in session.get("sentences", []):
        sent_grade = _avg_str(s)
        sent_completeness = _sentence_metric(s, "completeness", "completeness")
        sent_external_relation = _sentence_metric(s, "external_relation", "relation")
        for t in s.get("triples", []):
            row = [
                s["id"], s["text"], sent_grade, _grade_str(sent_completeness), _grade_str(sent_external_relation), s.get("suggestion", ""),
                t["id"], t["subject"], t["predicate"], t["object"],
                _grade_str(t.get("grade")),
            ]
            ws_det.append(row)
            alt = (row_idx % 2 == 0)
            for col in range(1, len(headers_det) + 1):
                _style_data_cell(ws_det.cell(row=row_idx, column=col), alt=alt)
            row_idx += 1

    col_widths_det = [12, 45, 14, 14, 16, 34, 10, 20, 20, 20, 12]
    for i, w in enumerate(col_widths_det, start=1):
        ws_det.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

class _GradingPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load Arial TrueType fonts when available for full Unicode support
        if _USE_ARIAL:
            for style, fpath in _ARIAL_MAP.items():
                self.add_font("Arial", style=style, fname=fpath)

    def header(self):
        self.set_font(_PDF_FONT, "B", 14)
        self.set_fill_color(30, 58, 95)
        self.set_text_color(255, 255, 255)
        self.cell(0, 12, "Ontology Triple Grading Report", ln=True, align="C", fill=True)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font(_PDF_FONT, "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def to_pdf(session: Dict[str, Any]) -> bytes:
    # Text helper: passthrough when using Unicode font; sanitize for core fonts
    _t = (lambda v: "" if v is None else str(v)) if _USE_ARIAL else _pdf_safe

    pdf = _GradingPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    sentences = session.get("sentences", [])
    total     = len(sentences)

    for s in sentences:
        sent_grade = _avg_str(s)
        sent_completeness = _grade_str(_sentence_metric(s, "completeness", "completeness"))
        sent_external_relation = _grade_str(_sentence_metric(s, "external_relation", "relation"))

        # ── Sentence heading ─────────────────────────────────────────────
        pdf.set_fill_color(30, 58, 95)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(_PDF_FONT, "B", 10)
        label = f"  Sentence {s['id']} of {total}    Grade: {sent_grade}"
        pdf.cell(0, 8, _t(label), ln=True, fill=True)
        pdf.ln(1)

        # ── Sentence text ─────────────────────────────────────────────────
        pdf.set_text_color(20, 20, 20)
        pdf.set_font(_PDF_FONT, "", 9)
        pdf.set_x(8)
        pdf.multi_cell(0, 5, _t(s["text"]))
        pdf.ln(2)

        pdf.set_font(_PDF_FONT, "", 8)
        pdf.set_text_color(70, 70, 70)
        pdf.set_x(8)
        pdf.multi_cell(0, 4, _t(f"Completeness: {sent_completeness}/10    External relation: {sent_external_relation}/10"))
        pdf.ln(1)

        # ── Suggestion ───────────────────────────────────────────────────
        suggestion = s.get("suggestion", "").strip()
        if suggestion:
            pdf.set_font(_PDF_FONT, "I", 8)
            pdf.set_text_color(90, 90, 90)
            pdf.set_x(8)
            pdf.multi_cell(0, 4, _t(f"Suggestion: {suggestion}"))
            pdf.ln(1)

        # ── Triples table ─────────────────────────────────────────────────
        pdf.set_font(_PDF_FONT, "B", 8)
        pdf.set_fill_color(214, 228, 240)
        pdf.set_text_color(20, 20, 20)
        col_w = [8, 48, 40, 48, 20]  # #, Subject, Predicate, Object, Grade
        headers = ["#", "Subject", "Predicate", "Object", "Grade"]
        for h, w in zip(headers, col_w):
            pdf.cell(w, 6, h, border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font(_PDF_FONT, "", 8)
        for i, t in enumerate(s.get("triples", []), start=1):
            fill = (i % 2 == 0)
            if fill:
                pdf.set_fill_color(235, 242, 250)
            else:
                pdf.set_fill_color(255, 255, 255)
            pdf.cell(col_w[0], 5, str(i),                         border=1, fill=fill, align="C")
            pdf.cell(col_w[1], 5, _t(t["subject"][:35]),          border=1, fill=fill)
            pdf.cell(col_w[2], 5, _t(t["predicate"][:30]),        border=1, fill=fill)
            pdf.cell(col_w[3], 5, _t(t["object"][:35]),           border=1, fill=fill)
            pdf.cell(col_w[4], 5, _t(_grade_str(t.get("grade"))), border=1, fill=fill, align="C")
            pdf.ln()

        pdf.ln(5)

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------------

def to_word(session: Dict[str, Any]) -> bytes:
    doc = Document()

    # Title
    title = doc.add_heading("Ontology Triple Grading Report", level=0)
    title.runs[0].font.color.rgb = RGBColor(30, 58, 95)

    sentences = session.get("sentences", [])
    total     = len(sentences)

    for s in sentences:
        sent_grade = _avg_str(s)
        sent_completeness = _grade_str(_sentence_metric(s, "completeness", "completeness"))
        sent_external_relation = _grade_str(_sentence_metric(s, "external_relation", "relation"))

        # Sentence heading
        heading_text = f"Sentence {s['id']} of {total}  —  Grade: {sent_grade}"
        h = doc.add_heading(heading_text, level=2)
        for run in h.runs:
            run.font.color.rgb = RGBColor(30, 58, 95)

        # Sentence text
        p = doc.add_paragraph(s["text"])
        p.runs[0].font.size = Pt(10)

        metric_line = doc.add_paragraph(f"Completeness: {sent_completeness}/10   External relation: {sent_external_relation}/10")
        metric_line.runs[0].font.size = Pt(9)

        # Suggestion
        suggestion = s.get("suggestion", "").strip()
        if suggestion:
            sp = doc.add_paragraph()
            sp.add_run("Suggestion: ").bold = True
            run = sp.add_run(suggestion)
            run.italic = True
            run.font.size = Pt(9)

        # Triples table
        triples = s.get("triples", [])
        if triples:
            table = doc.add_table(rows=1, cols=5)
            table.style = "Table Grid"
            hdr = table.rows[0].cells
            for cell, txt in zip(hdr, ["#", "Subject", "Predicate", "Object", "Grade"]):
                cell.text = txt
                cell.paragraphs[0].runs[0].font.bold = True
                cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
                cell._tc.get_or_add_tcPr()  # ensure cell properties exist

            for i, t in enumerate(triples, start=1):
                row_cells = table.add_row().cells
                row_cells[0].text = str(i)
                row_cells[1].text = t["subject"]
                row_cells[2].text = t["predicate"]
                row_cells[3].text = t["object"]
                row_cells[4].text = _grade_str(t.get("grade"))

        doc.add_paragraph()  # spacing

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
