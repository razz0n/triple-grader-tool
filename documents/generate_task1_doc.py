import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def create_task1_doc():
    doc = docx.Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Colors
    PRIMARY = RGBColor(0x1F, 0x29, 0x37)   # Slate 800
    ACCENT = RGBColor(0x25, 0x63, 0xEB)    # Royal Blue
    MUTED = RGBColor(0x4B, 0x55, 0x63)     # Slate 600
    CODE_COLOR = RGBColor(0x38, 0xBD, 0xF8) # Light Cyan / Sky Blue

    # Normal Style
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = PRIMARY
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    def add_header_block(title, subtitle):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(title)
        run.font.size = Pt(20)
        run.font.bold = True
        run.font.color.rgb = ACCENT

        p_sub = doc.add_paragraph()
        p_sub.paragraph_format.space_after = Pt(14)
        run_sub = p_sub.add_run(subtitle)
        run_sub.font.size = Pt(12)
        run_sub.font.italic = True
        run_sub.font.color.rgb = MUTED

    def add_section_heading(title):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(4)
        run = h.add_run(title)
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = PRIMARY

    def add_subsection_heading(title):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(3)
        run = h.add_run(title)
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = ACCENT

    def add_callout(text, title="Key Requirement Note"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F3F4F6"/>')
        tcPr.append(shd)
        
        borders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="none"/>
                <w:left w:val="single" w:sz="24" w:space="0" w:color="2563EB"/>
                <w:bottom w:val="none"/>
                <w:right w:val="none"/>
            </w:tcBorders>
        ''')
        tcPr.append(borders)
        
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        r_t = p.add_run(f"{title}: ")
        r_t.bold = True
        r_t.font.color.rgb = ACCENT
        r_body = p.add_run(text)
        r_body.font.color.rgb = PRIMARY

    def add_code_block(code_text):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="0F172A"/>')
        tcPr.append(shd)

        borders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="none"/>
                <w:left w:val="none"/>
                <w:bottom w:val="none"/>
                <w:right w:val="none"/>
            </w:tcBorders>
        ''')
        tcPr.append(borders)

        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(code_text)
        run.font.name = "Consolas"
        run.font.size = Pt(9.5)
        run.font.color.rgb = CODE_COLOR

    add_header_block(
        "Task 1 Summary: Application Updates, User Privacy, and Workflow API",
        "Triple Grader System Modernization and Pre-Evaluation Foundation"
    )

    add_callout(
        "This document describes the exact modifications implemented in Task 1. "
        "We removed whole-session average scores, protected reviewer anonymity through randomized user codes, "
        "repaired benchmark sentence identifiers, and introduced the RESTful HTTP curation workflow. "
        "Section 4 provides a step-by-step test guide for manual and automated verification.",
        "Executive Summary"
    )

    add_section_heading("1. Problem Context and Motivation")
    doc.add_paragraph(
        "In earlier versions of the application, several design elements conflicted with evaluation standards and user privacy. "
        "First, the system computed a single aggregate average grade across an entire session. In semantic triple grading, a session-wide average "
        "blurs high-quality triples with problematic triples, obscuring critical error details. Research standards require evaluations to occur "
        "at the individual triple level rather than averaging over the entire session."
    )
    doc.add_paragraph(
        "Second, user account records previously relied on email addresses as display names. In inter-rater agreement studies, "
        "displaying email addresses compromises participant privacy. Reviewers should only be identified through randomized codes (e.g. user_8f2a)."
    )
    doc.add_paragraph(
        "Third, the gold benchmark dataset (backend/gold_benchmark.csv) had 316 triple rows across 38 unique source sentences, "
        "but all rows used the same sentence_id (s0001). This defect prevented sentence-level grouping and cluster bootstrapping."
    )
    doc.add_paragraph(
        "Finally, the curation workflow needed a clean RESTful HTTP API to support reproducible testing across suggestions, voting, "
        "approvals, and exports."
    )

    add_section_heading("2. Implemented Modifications")

    add_subsection_heading("2.1 Removal of Session-Level Average Scores")
    doc.add_paragraph("We updated the backend services and frontend user interface:")
    doc.add_paragraph("• Backend Services: In backend/services/grading_service.py and backend/services/session_service.py, we updated the grading statistics functions so that session_average_grade is set to None. Individual triple grades, per-user score records, and sentence-level completeness and relation metrics remain fully preserved.")
    doc.add_paragraph("• Backend Main Routes: In backend/main.py, we updated session list responses and version snapshots to omit the session average.")
    doc.add_paragraph("• Frontend Session Cards: In frontend/src/components/FileUpload.jsx, we updated the session cards. The cards now display active reviewer counts without showing a composite session average.")
    doc.add_paragraph("• Workspace View: In frontend/src/components/GradingForm.jsx, we removed the session-wide average score banner from the header bar and removed personal average badges from the reviewer pills.")

    add_subsection_heading("2.2 Anonymization of User Identifiers")
    doc.add_paragraph("We protected participant privacy across backend utilities and frontend display logic:")
    doc.add_paragraph("• In backend/utils.py, we updated display_name(user). The function now strictly checks for clean username strings without @ symbols. If a name or email contains an @ symbol, the system generates an anonymous identifier derived from the user ID (e.g. user_a7f93214). Email addresses are never returned as display names.")
    doc.add_paragraph("• In frontend/src/components/GradingForm.jsx, the active username logic was updated to prioritize currentUser.username and safe non-email strings, ensuring participant anonymity during collaborative grading.")

    add_subsection_heading("2.3 Sentence Identifier Repair")
    doc.add_paragraph(
        "We ran documents/repair_sentence_ids.py against backend/gold_benchmark.csv. "
        "The 38 unique source sentences now carry sequential, stable identifiers from s0001 through s0038 across all 316 triple rows. "
        "This allows proper sentence-level grouping and cluster bootstrap evaluation."
    )

    add_subsection_heading("2.4 Authoritative Adjudicated Gold Set Policy")
    doc.add_paragraph(
        "We created backend/services/adjudicated_gold.py, implementing the canonical rule specified in Section 2.1 of the evaluation plan. "
        "Under this policy, suggested triples enter the gold set only when their status is explicitly approved. "
        "Original triples enter the gold set only if they are not marked for removal and have not been superseded by an approved correction."
    )

    add_subsection_heading("2.5 RESTful Curation Workflow API")
    doc.add_paragraph(
        "We added dedicated RESTful endpoints in backend/main.py to support the automated workflow:"
    )
    doc.add_paragraph("1. POST /api/sessions: Creates or registers a new grading session with initial sentences and versions.")
    doc.add_paragraph("2. GET /api/sessions/{session_id}: Retrieves the complete session state.")
    doc.add_paragraph("3. POST /api/sessions/{session_id}/suggestions: Allows reviewers to submit triple revisions with author metadata.")
    doc.add_paragraph("4. POST /api/sessions/{session_id}/vote: Records reviewer votes while strictly rejecting self-votes from the author.")
    doc.add_paragraph("5. POST /api/sessions/{session_id}/approve: Allows the session owner to approve a revision. The endpoint marks the suggestion as approved, supersedes the original triple, and creates an active corrected triple.")
    doc.add_paragraph("6. GET /api/sessions/{session_id}/export/json: Exports the canonical adjudicated gold triples as structured JSON.")
    doc.add_paragraph("7. GET /api/sessions/{session_id}/export/csv: Exports the canonical adjudicated gold triples as a CSV spreadsheet.")

    add_section_heading("3. Verification and Testing Summary")
    doc.add_paragraph(
        "We verified the entire implementation using an automated integration test with FastAPI TestClient. "
        "The test validated all seven workflow steps:"
    )

    table = doc.add_table(rows=8, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Operation", "Expected Outcome", "Observed Result"]
    hdr_cells = table.rows[0].cells
    for i, name in enumerate(headers):
        hdr_cells[i].text = name
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="E5E7EB"/>')
        hdr_cells[i]._tc.get_or_add_tcPr().append(shd)

    rows_data = [
        ("Session Creation", "Session registered with stable ID and owner", "Passed (Status 200)"),
        ("Add Suggestion", "Pending suggestion stored with triple linkage", "Passed (Status 200)"),
        ("Reviewer Vote", "Vote recorded under reviewer identity", "Passed (Status 200)"),
        ("Self-Vote Prevention", "Author voting on own suggestion rejected", "Passed (Status 400 Rejected)"),
        ("Owner Approval", "Suggestion approved, original superseded", "Passed (Status 200)"),
        ("State Verification", "Corrected triple active, original superseded", "Passed (100% verified)"),
        ("Adjudicated Export", "Export contains only active corrected triple", "Passed (JSON & CSV match)"),
    ]

    for row_idx, data in enumerate(rows_data, start=1):
        row_cells = table.rows[row_idx].cells
        for col_idx, text in enumerate(data):
            row_cells[col_idx].text = text

    # -------------------------------------------------------------------------
    # NEW SECTION: Test (Step-by-step User Guide)
    # -------------------------------------------------------------------------
    add_section_heading("4. Test: Verification Guide for the User")
    doc.add_paragraph(
        "To allow you to independently verify and validate all changes made in Task 1, we have provided four direct "
        "testing methods. You can execute these commands in PowerShell or your terminal from the project root directory."
    )

    add_subsection_heading("4.1 Method 1: Run the Automated Verification Script (Recommended)")
    doc.add_paragraph(
        "We created a dedicated verification script that runs all automated checks end-to-end and prints detailed pass/fail feedback. "
        "Run the following command in your terminal:"
    )
    add_code_block("python documents/test_task1_workflow.py")
    doc.add_paragraph("Expected Output from this script:")
    doc.add_paragraph("• Check 1: Confirms 316 triple rows and exactly 38 unique sentence IDs (s0001 through s0038).")
    doc.add_paragraph("• Check 2: Verifies that display_name never returns an email address or leaks personal email prefixes.")
    doc.add_paragraph("• Check 3: Verifies that session_average_grade is None while individual triple grades remain intact.")
    doc.add_paragraph("• Check 4: Verifies the full RESTful curation cycle: session creation -> suggestion -> vote -> self-vote rejection -> approval -> original superseded -> corrected active -> gold export JSON/CSV.")

    add_subsection_heading("4.2 Method 2: Inspect Sentence IDs in Gold Benchmark")
    doc.add_paragraph(
        "To directly check that the gold benchmark sentence identifiers have been repaired, run:"
    )
    add_code_block(
        "python -c \"import csv; rows = list(csv.DictReader(open('backend/gold_benchmark.csv', encoding='utf-8'))); "
        "ids = set(r['sentence_id'] for r in rows); print(f'Unique sentence IDs: {len(ids)}, range: {sorted(ids)[0]} to {sorted(ids)[-1]}')\""
    )
    doc.add_paragraph("Expected result: Unique sentence IDs: 38, range: s0001 to s0038.")

    add_subsection_heading("4.3 Method 3: Verify User Anonymization Function")
    doc.add_paragraph(
        "To verify that the display name function protects reviewer identity and never leaks email addresses, run:"
    )
    add_code_block(
        "python -c \"import sys; sys.path.insert(0, 'backend'); from utils import display_name; "
        "print('Email input:', display_name({'email': 'researcher.smith@cs.csu.edu'})); "
        "print('UUID input:', display_name({'id': '9e15250f-3731-4c98-9685-78122bd88d89'})); "
        "print('Username input:', display_name({'username': 'user_8f2a'}))\""
    )
    doc.add_paragraph("Expected result: All outputs produce anonymous handles (e.g. user_anon, user_9e15250f, user_8f2a) with zero email leakage.")

    add_subsection_heading("4.4 Method 4: Visual Check in Frontend UI")
    doc.add_paragraph(
        "You can visually confirm these changes in the web browser:"
    )
    doc.add_paragraph("1. Start backend: python backend/start_server.py (runs on http://127.0.0.1:8000)")
    doc.add_paragraph("2. Start frontend: cd frontend && npm run dev (runs on http://localhost:5173)")
    doc.add_paragraph("3. Check Dashboard Cards: Observe the recent session cards in FileUpload.jsx. They display the active reviewer count (e.g. '2 graders') without any composite session average ('Avg .../10').")
    doc.add_paragraph("4. Check Workspace Header: Enter any grading session. Observe that the top workspace header displays the active grader count without any overall session score.")
    doc.add_paragraph("5. Check Reviewer Pills: In the grader summary bar, verify that each grader appears with their anonymized code (e.g. 'user_rl', 'user_jw') and their graded count, without personal session average badges.")

    add_section_heading("5. Conclusion and Readiness for Task 2 (EQ1)")
    doc.add_paragraph(
        "Task 1 is complete, fully tested, and verified. The application foundations are clean, reproducible, and private. "
        "OpenIE has been excluded from the evaluation as instructed, and the codebase is ready for Evaluation Question 1 (EQ1)."
    )

    output_path = "documents/task1_application_updates_and_anonymization.docx"
    try:
        doc.save(output_path)
        print(f"Successfully generated {output_path}")
    except PermissionError:
        fallback_path = "documents/task1_application_updates_and_anonymization_updated.docx"
        doc.save(fallback_path)
        print(f"Original file is currently open in Microsoft Word. Saved updated report with Test section to: {fallback_path}")

if __name__ == "__main__":
    create_task1_doc()
