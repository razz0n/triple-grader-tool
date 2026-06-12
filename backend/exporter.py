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
    explicit_sentence_grade = sentence.get("sentence_grade")
    if explicit_sentence_grade is not None:
        try:
            return f"{float(explicit_sentence_grade):.1f}"
        except (TypeError, ValueError):
            pass

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


def _calculate_paper_metrics(session: Dict[str, Any]) -> Dict[str, Any]:
    from datetime import datetime
    sentences = session.get("sentences", [])
    num_sentences = len(sentences)
    
    triples = [t for s in sentences for t in s.get("triples", [])]
    num_gold_triples = sum(1 for t in triples if not t.get("marked_for_removal"))
    avg_triples = (num_gold_triples / num_sentences) if num_sentences > 0 else 0.0
    
    # Unique annotators & reviewers
    users = set()
    owner_id = str(session.get("owner_user_id") or "").strip()
    if owner_id:
        users.add(owner_id)
    owner_name = str(session.get("owner_name") or "").strip()
    if owner_name:
        users.add(owner_name)
        
    for s in sentences:
        for c in s.get("sentence_comments", []):
            if c.get("user_id"):
                users.add(c.get("user_id"))
            if c.get("author"):
                users.add(c.get("author"))
            for r in c.get("replies", []):
                if r.get("user_id"):
                    users.add(r.get("user_id"))
                if r.get("author"):
                    users.add(r.get("author"))
        
        # completeness/relation by user
        for val in s.get("completeness_by_user", {}).values():
            if isinstance(val, dict):
                if val.get("user_id"):
                    users.add(val.get("user_id"))
                if val.get("user_name"):
                    users.add(val.get("user_name"))
        for val in s.get("external_relation_by_user", {}).values():
            if isinstance(val, dict):
                if val.get("user_id"):
                    users.add(val.get("user_id"))
                if val.get("user_name"):
                    users.add(val.get("user_name"))

        for t in s.get("triples", []):
            for val in t.get("grades_by_user", {}).values():
                if isinstance(val, dict):
                    if val.get("user_id"):
                        users.add(val.get("user_id"))
                    if val.get("user_name"):
                        users.add(val.get("user_name"))
            for c in t.get("triple_comments", []):
                if c.get("user_id"):
                    users.add(c.get("user_id"))
                if c.get("author"):
                    users.add(c.get("author"))
                for r in c.get("replies", []):
                    if r.get("user_id"):
                        users.add(r.get("user_id"))
                    if r.get("author"):
                        users.add(r.get("author"))
            for sug in t.get("suggestions", []):
                if sug.get("user_id"):
                    users.add(sug.get("user_id"))
                if sug.get("author"):
                    users.add(sug.get("author"))
                for r in sug.get("replies", []):
                    if r.get("user_id"):
                        users.add(r.get("user_id"))
                    if r.get("author"):
                        users.add(r.get("author"))

    # Cleanup empty strings or None from set
    users = {u for u in users if u}
    num_users = len(users) if users else 1
    
    # Calibration phase
    calibration_sentences = sum(1 for s in sentences if s.get("is_calibration"))
    calibration_pct = (calibration_sentences / num_sentences * 100) if num_sentences > 0 else 0.0
    
    # Pilot-stage triple overlap (OpenIE F1 if evaluated)
    eval_f1 = "N/A"
    if session.get("evaluation") and isinstance(session["evaluation"], dict):
        f1_val = session["evaluation"].get("f1")
        if f1_val is not None:
            try:
                eval_f1 = f"{float(f1_val)*100:.1f}%" if float(f1_val) <= 1.0 else f"{float(f1_val):.1f}%"
            except ValueError:
                eval_f1 = str(f1_val)
                
    # Reviewer agreement
    agreed_count = 0
    total_multi_vote = 0
    for s in sentences:
        for t in s.get("triples", []):
            grades = []
            for entry in t.get("grades_by_user", {}).values():
                if isinstance(entry, dict) and entry.get("grade") is not None:
                    grades.append(float(entry["grade"]))
            if len(grades) >= 2:
                total_multi_vote += 1
                if len(set(grades)) == 1:
                    agreed_count += 1
    agreement_str = f"{agreed_count / total_multi_vote * 100:.1f}%" if total_multi_vote > 0 else "N/A"
    
    # Accepted without change
    accepted_without_change = 0
    modified_after_review = 0
    for s in sentences:
        for t in s.get("triples", []):
            if not t.get("marked_for_removal"):
                has_approved_sug = any(sug.get("status") == "approved" for sug in t.get("suggestions", []))
                if has_approved_sug:
                    modified_after_review += 1
                else:
                    accepted_without_change += 1
                    
    accepted_without_change_pct = (accepted_without_change / num_gold_triples * 100) if num_gold_triples > 0 else 0.0
    modified_after_review_pct = (modified_after_review / num_gold_triples * 100) if num_gold_triples > 0 else 0.0
    
    # Rejected triples
    num_rejected_triples = sum(1 for t in triples if t.get("marked_for_removal"))
    
    # Missing triples suggested and added
    num_suggested_added = sum(1 for t in triples if t.get("is_new_suggestion") and t.get("status") == "approved")
    
    # Adjudication cases
    num_method_adjudications = sum(1 for s in sentences if len(s.get("sentence_comments", [])) > 0)
    
    num_triple_adjudications = 0
    for s in sentences:
        for t in s.get("triples", []):
            has_comments = len(t.get("triple_comments", [])) > 0
            has_sug_replies = any(len(sug.get("replies", [])) > 0 for sug in t.get("suggestions", []))
            if has_comments or has_sug_replies:
                num_triple_adjudications += 1
                
    # Guideline updates
    guideline_updates = session.get("guideline_updates", [])
    if not isinstance(guideline_updates, list):
        guideline_updates = []
    guideline_keywords = ["guideline", "rule", "instruction", "method decision"]
    auto_updates = 0
    for s in sentences:
        for c in s.get("sentence_comments", []):
            txt = c.get("text", "").lower()
            if any(k in txt for k in guideline_keywords):
                auto_updates += 1
            for r in c.get("replies", []):
                r_txt = r.get("text", "").lower()
                if any(k in r_txt for k in guideline_keywords):
                    auto_updates += 1
    num_guideline_updates = max(len(guideline_updates), auto_updates)
    
    return {
        "num_sentences": num_sentences,
        "num_gold_triples": num_gold_triples,
        "avg_triples": avg_triples,
        "num_users": num_users,
        "calibration_pct": calibration_pct,
        "eval_f1": eval_f1,
        "agreement_str": agreement_str,
        "accepted_without_change": accepted_without_change,
        "accepted_without_change_pct": accepted_without_change_pct,
        "modified_after_review": modified_after_review,
        "modified_after_review_pct": modified_after_review_pct,
        "num_rejected_triples": num_rejected_triples,
        "num_suggested_added": num_suggested_added,
        "num_method_adjudications": num_method_adjudications,
        "num_triple_adjudications": num_triple_adjudications,
        "num_guideline_updates": num_guideline_updates,
    }


def to_pdf(session: Dict[str, Any]) -> bytes:
    # Text helper: passthrough when using Unicode font; sanitize for core fonts
    _t = (lambda v: "" if v is None else str(v)) if _USE_ARIAL else _pdf_safe

    pdf = _GradingPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Paper Quality & Process Indicators Summary Table ────────────────────
    pdf.set_fill_color(30, 58, 95)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(_PDF_FONT, "B", 11)
    pdf.cell(0, 10, "  Paper Quality & Process Indicators Summary", ln=True, fill=True, align="L")
    pdf.ln(3)

    metrics = _calculate_paper_metrics(session)

    pdf.set_font(_PDF_FONT, "", 9)
    pdf.set_text_color(20, 20, 20)

    table_data = [
        ("Number of source sentences", str(metrics["num_sentences"])),
        ("Number of final gold triples", str(metrics["num_gold_triples"])),
        ("Average number of triples per sentence", f"{metrics['avg_triples']:.2f}"),
        ("Number of annotators and reviewers", str(metrics["num_users"])),
        ("Percentage of sentences in calibration phase", f"{metrics['calibration_pct']:.1f}%"),
        ("Pilot-stage triple overlap / match results", metrics["eval_f1"]),
        ("Reviewer agreement on candidate-triple decisions", metrics["agreement_str"]),
        ("Triples accepted without change (Count / %)", f"{metrics['accepted_without_change']} / {metrics['accepted_without_change_pct']:.1f}%"),
        ("Triples modified after review (Count / %)", f"{metrics['modified_after_review']} / {metrics['modified_after_review_pct']:.1f}%"),
        ("Number of rejected triples", str(metrics["num_rejected_triples"])),
        ("Missing triples suggested & added", str(metrics["num_suggested_added"])),
        ("Number of method-level adjudication cases", str(metrics["num_method_adjudications"])),
        ("Number of triple-level adjudication cases", str(metrics["num_triple_adjudications"])),
        ("Number of guideline updates / method decisions", str(metrics["num_guideline_updates"])),
    ]

    col_w1 = 130
    col_w2 = 50

    pdf.set_font(_PDF_FONT, "B", 9)
    pdf.set_fill_color(214, 228, 240)
    pdf.cell(col_w1, 7, "  Quality & Process Indicator", border=1, fill=True)
    pdf.cell(col_w2, 7, "Value", border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font(_PDF_FONT, "", 9)
    for i, (indicator, val) in enumerate(table_data):
        fill = (i % 2 == 0)
        if fill:
            pdf.set_fill_color(245, 248, 252)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.cell(col_w1, 6, "  " + _t(indicator), border=1, fill=fill)
        pdf.cell(col_w2, 6, _t(val), border=1, fill=fill, align="C")
        pdf.ln()

    pdf.ln(8)
    # ── Page break to start the regular report ─────────────────────────────
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
