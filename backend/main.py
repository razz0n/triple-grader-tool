"""  
main.py — FastAPI backend for the Ontology Triple Grading Tool.

Endpoints:
  POST /api/upload              → parse uploaded file → return session data
  POST /api/save                → persist graded session to storage/
  GET  /api/download/{id}/{fmt} → stream file in chosen format
  GET  /api/preview/{id}        → render HTML preview of graded session
  GET  /api/sessions            → list saved sessions
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from exporter import to_csv, to_excel, to_json, to_pdf, to_word
from parser import parse_file, parse_file_rich

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Ontology Grading Tool", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve the built frontend directory (present after `npm run build`)
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SaveRequest(BaseModel):
    session_id: str
    source_filename: str
    uploaded_at: str
    sentences: list


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Parse an uploaded CSV or Excel file and return structured sentence-group data for review."""
    allowed_extensions = {".csv", ".xlsx", ".xls"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(allowed_extensions)}",
        )

    file_bytes = await file.read()

    try:
        sentence_groups = parse_file_rich(file_bytes, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {str(exc)}")

    if not sentence_groups:
        raise HTTPException(
            status_code=422,
            detail="No sentence-triple groups found in the file. "
                   "Ensure sentences appear in column 8 (index 7) and "
                   "triples in columns 1–3 (index 0–2).",
        )

    session_id = str(uuid.uuid4())
    return {
        "session_id":       session_id,
        "source_filename":  file.filename,
        "uploaded_at":      datetime.utcnow().isoformat(),
        "total_groups":     len(sentence_groups),
        "sentence_groups":  sentence_groups,
    }


@app.post("/api/save")
async def save_session(body: SaveRequest):
    """Persist a graded session to the storage directory."""
    session_data = body.model_dump()

    # Recompute sentence grades server-side for integrity
    for s in session_data["sentences"]:
        grades = [t["grade"] for t in s.get("triples", []) if t.get("grade") is not None]
        s["sentence_grade"] = round(sum(grades) / len(grades), 2) if grades else None

    out_path = STORAGE_DIR / f"{body.session_id}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(session_data, fh, indent=2, ensure_ascii=False)

    return {"session_id": body.session_id, "saved_at": datetime.utcnow().isoformat()}


@app.get("/api/download/{session_id}/{fmt}")
async def download_session(session_id: str, fmt: str):
    """Download a saved session in the requested format."""
    # Validate session_id to prevent path traversal
    if not session_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID.")

    json_path = STORAGE_DIR / f"{session_id}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found. Save the session first.")

    with open(json_path, "r", encoding="utf-8") as fh:
        session = json.load(fh)

    fmt = fmt.lower()
    filename_base = session.get("source_filename", "graded").rsplit(".", 1)[0]

    if fmt == "json":
        data         = to_json(session)
        media_type   = "application/json"
        disposition  = f'attachment; filename="{filename_base}_graded.json"'
    elif fmt == "csv":
        data         = to_csv(session)
        media_type   = "text/csv"
        disposition  = f'attachment; filename="{filename_base}_graded.csv"'
    elif fmt in ("excel", "xlsx"):
        data         = to_excel(session)
        media_type   = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        disposition  = f'attachment; filename="{filename_base}_graded.xlsx"'
    elif fmt in ("pdf",):
        data         = to_pdf(session)
        media_type   = "application/pdf"
        disposition  = f'attachment; filename="{filename_base}_graded.pdf"'
    elif fmt in ("word", "docx"):
        data         = to_word(session)
        media_type   = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        disposition  = f'attachment; filename="{filename_base}_graded.docx"'
    else:
        raise HTTPException(status_code=400, detail=f"Unknown format '{fmt}'. Use: json, csv, excel, pdf, word.")

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Return the full saved session JSON (used by the frontend to resume a session)."""
    if not session_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    json_path = STORAGE_DIR / f"{session_id}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    with open(json_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@app.get("/api/preview/{session_id}", response_class=HTMLResponse)
async def preview_session(session_id: str):
    """Render an HTML preview of a saved graded session (opens in browser tab)."""
    if not session_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID.")

    json_path = STORAGE_DIR / f"{session_id}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found. Save the session first.")

    with open(json_path, "r", encoding="utf-8") as fh:
        session = json.load(fh)

    sentences   = session.get("sentences", [])
    filename    = session.get("source_filename", "")
    uploaded_at = session.get("uploaded_at", "")[:16].replace("T", " ")

    def grade_color(g):
        if g is None: return "#94a3b8"
        if g >= 7:    return "#16a34a"
        if g >= 4:    return "#d97706"
        return "#dc2626"

    def avg_grade(s):
        gs = [t["grade"] for t in s.get("triples", []) if t.get("grade") is not None]
        if not gs: return None
        return round(sum(gs) / len(gs), 1)

    rows_html = []
    for s in sentences:
        avg  = avg_grade(s)
        gc   = grade_color(avg)
        avg_label = f"{avg}" if avg is not None else "—"
        triple_rows = "".join(
            f"""<tr style="background:{'#f8fafc' if i%2==0 else '#fff'}">
              <td style="padding:5px 10px;color:#64748b;font-size:12px;">{i+1}</td>
              <td style="padding:5px 10px;font-size:12px;">{t.get('subject','')}</td>
              <td style="padding:5px 10px;font-size:12px;">{t.get('predicate','')}</td>
              <td style="padding:5px 10px;font-size:12px;">{t.get('object','')}</td>
              <td style="padding:5px 10px;text-align:center;font-weight:600;font-size:13px;color:{grade_color(t.get('grade'))}">{t.get('grade') if t.get('grade') is not None else '—'}</td>
            </tr>"""
            for i, t in enumerate(s.get("triples", []))
        )
        suggestion = s.get("suggestion", "").strip()
        sug_html = f'<p style="margin:8px 0 0;font-size:12px;color:#64748b;"><em>💬 {suggestion}</em></p>' if suggestion else ""
        rows_html.append(f"""
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;margin-bottom:18px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.06);">
            <div style="background:#1e3a5f;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:13px;font-weight:600;">Sentence {s['id']}</span>
              <span style="font-size:18px;font-weight:700;color:{gc};background:rgba(255,255,255,.15);border-radius:8px;padding:2px 10px;">{avg_label}<span style="font-size:11px;font-weight:400;"> / 10</span></span>
            </div>
            <div style="padding:12px 16px 4px;">
              <p style="margin:0 0 10px;font-size:14px;color:#1e293b;line-height:1.6;border-left:3px solid #93c5fd;padding-left:10px;">{s.get('text','')}</p>
              {sug_html}
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%;border-collapse:collapse;">
                <thead><tr style="background:#dbeafe;">
                  <th style="padding:6px 10px;font-size:11px;text-align:left;color:#1e3a5f;">#</th>
                  <th style="padding:6px 10px;font-size:11px;text-align:left;color:#1e3a5f;">Subject</th>
                  <th style="padding:6px 10px;font-size:11px;text-align:left;color:#1e3a5f;">Predicate</th>
                  <th style="padding:6px 10px;font-size:11px;text-align:left;color:#1e3a5f;">Object</th>
                  <th style="padding:6px 10px;font-size:11px;text-align:center;color:#1e3a5f;">Grade</th>
                </tr></thead>
                <tbody>{triple_rows}</tbody>
              </table>
            </div>
          </div>
        """)

    body = "\n".join(rows_html)
    total_triples = sum(len(s.get("triples", [])) for s in sentences)
    graded_triples = sum(
        sum(1 for t in s.get("triples", []) if t.get("grade") is not None)
        for s in sentences
    )
    overall_grades = [t["grade"] for s in sentences for t in s.get("triples", []) if t.get("grade") is not None]
    overall_avg = round(sum(overall_grades) / len(overall_grades), 1) if overall_grades else None
    overall_label = str(overall_avg) if overall_avg is not None else "—"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Preview — {filename}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background:#f1f5f9; color:#1e293b; }}
    .topbar {{ background:#1e3a5f; color:#fff; padding:14px 24px;
               display:flex; justify-content:space-between; align-items:center;
               position:sticky; top:0; z-index:10; box-shadow:0 2px 8px rgba(0,0,0,.2); }}
    .topbar h1 {{ margin:0; font-size:16px; font-weight:700; }}
    .topbar p  {{ margin:0; font-size:11px; opacity:.7; }}
    .stats {{ display:flex; gap:18px; text-align:right; }}
    .stat-val {{ font-size:20px; font-weight:700; line-height:1; }}
    .stat-lbl {{ font-size:10px; opacity:.7; }}
    .container {{ max-width:900px; margin:24px auto; padding:0 16px 40px; }}
    @media print {{ .topbar {{ position:static; }} }}
  </style>
</head>
<body>
  <div class="topbar">
    <div>
      <h1>📊 Ontology Triple Grading — Preview</h1>
      <p>{filename} &nbsp;&bull;&nbsp; Saved {uploaded_at}</p>
    </div>
    <div class="stats">
      <div><div class="stat-val">{len(sentences)}</div><div class="stat-lbl">Sentences</div></div>
      <div><div class="stat-val">{graded_triples}/{total_triples}</div><div class="stat-lbl">Triples graded</div></div>
      <div><div class="stat-val" style="color:#86efac;">{overall_label}</div><div class="stat-lbl">Overall avg</div></div>
    </div>
  </div>
  <div class="container">
    {body}
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/api/sessions")
async def list_sessions():
    """List all saved session files."""
    sessions = []
    for p in sorted(STORAGE_DIR.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            sessions.append({
                "session_id":      p.stem,
                "source_filename": data.get("source_filename", "unknown"),
                "uploaded_at":     data.get("uploaded_at", ""),
                "total_sentences": len(data.get("sentences", [])),
            })
        except Exception:
            pass
    return sessions


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Serve the React build in production
# Mount AFTER all API routes so /api/* is never intercepted.
# ---------------------------------------------------------------------------
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="static")
