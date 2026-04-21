"""
main.py — FastAPI backend for the Ontology Triple Grading Tool.

Endpoints:
  POST /api/upload           → parse uploaded file → return session data
  POST /api/save             → persist graded session to storage/
  GET  /api/download/{id}/{fmt} → stream file in chosen format
  GET  /api/sessions         → list saved sessions
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from exporter import to_csv, to_excel, to_json, to_pdf, to_word
from parser import parse_file

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
    """Parse an uploaded CSV or Excel file and return structured sentence data."""
    allowed_extensions = {".csv", ".xlsx", ".xls"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(allowed_extensions)}",
        )

    file_bytes = await file.read()

    try:
        sentences = parse_file(file_bytes, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {str(exc)}")

    if not sentences:
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
        "total_sentences":  len(sentences),
        "sentences":        sentences,
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
