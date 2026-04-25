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
import hashlib
import secrets
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

from exporter import to_csv, to_excel, to_json, to_pdf, to_word
from parser import parse_file, parse_file_rich

DEFAULT_USERS = [
    {"username": "user_ysh", "name": "user_ysh", "email": "user_ysh@example.com", "password": "psd_ysh_psd"},
    {"username": "user_jw", "name": "user_jw", "email": "user_jw@example.com", "password": "psd_jw_psd"},
    {"username": "user_rl", "name": "user_rl", "email": "user_rl@example.com", "password": "psd_rl_psd"},
    {"username": "user_ab", "name": "user_ab", "email": "user_ab@example.com", "password": "psd_ab_psd"},
    {"username": "user_cd", "name": "user_cd", "email": "user_cd@example.com", "password": "psd_cd_psd"},
]

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,23}$")

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
SESSIONS_ROOT = STORAGE_DIR / "users"
SESSIONS_ROOT.mkdir(exist_ok=True)
USERS_FILE = STORAGE_DIR / "users.json"
TOKENS_FILE = STORAGE_DIR / "tokens.json"
_AUTH_SCHEME = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _save_json(path: Path, data: Any):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())  # Force write to disk immediately


def _norm_email(email: str) -> str:
    return email.strip().lower()


def _norm_username(username: str) -> str:
    return username.strip().lower()


def _is_valid_username(username: str) -> bool:
    return bool(USERNAME_PATTERN.fullmatch(_norm_username(username)))


def _display_name(user: Dict[str, Any]) -> str:
    name = (user.get("name") or "").strip()
    if name:
        return name
    email = user.get("email", "")
    local = email.split("@", 1)[0] if "@" in email else "User"
    return local or "User"


def _hash_password(password: str, salt_hex: Optional[str] = None) -> Dict[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260000)
    return {"salt": salt.hex(), "hash": dk.hex()}


def _verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    computed = _hash_password(password, salt_hex=salt_hex)["hash"]
    return secrets.compare_digest(computed, hash_hex)


def _load_users() -> Dict[str, Any]:
    users = _load_json(USERS_FILE, {"users": []})
    if "users" not in users:
        users = {"users": []}
    return users


def _save_users(users: Dict[str, Any]):
    _save_json(USERS_FILE, users)


def _load_tokens() -> Dict[str, Any]:
    tokens = _load_json(TOKENS_FILE, {"tokens": {}})
    if "tokens" not in tokens:
        tokens = {"tokens": {}}
    return tokens


def _save_tokens(tokens: Dict[str, Any]):
    _save_json(TOKENS_FILE, tokens)


def _make_unique_username(base_username: str, users: list) -> str:
    base = _norm_username(base_username) or "user"
    existing = {_norm_username(user.get("username", "")) for user in users}
    if base not in existing:
        return base
    suffix = 2
    while f"{base}_{suffix}" in existing:
        suffix += 1
    return f"{base}_{suffix}"


def _get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    users = _load_users()["users"]
    target = _norm_email(email)
    for user in users:
        if user.get("email") == target:
            return user
    return None


def _get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    users = _load_users()["users"]
    target = _norm_username(username)
    for user in users:
        if _norm_username(user.get("username", "")) == target:
            return user
    return None


def _find_user_for_login(login_value: str) -> Optional[Dict[str, Any]]:
    identifier = login_value.strip()
    if not identifier:
        return None
    if "@" in identifier:
        by_email = _get_user_by_email(identifier)
        if by_email:
            return by_email
    by_username = _get_user_by_username(identifier)
    if by_username:
        return by_username
    return _get_user_by_email(identifier)


def _get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    users = _load_users()["users"]
    for user in users:
        if user.get("id") == user_id:
            return user
    return None


def _issue_token(user_id: str) -> str:
    token = secrets.token_urlsafe(40)
    tokens = _load_tokens()
    tokens["tokens"][token] = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    _save_tokens(tokens)
    return token


def _user_from_token(token: str) -> Optional[Dict[str, Any]]:
    tokens = _load_tokens()["tokens"]
    token_data = tokens.get(token)
    if not token_data:
        return None
    return _get_user_by_id(token_data.get("user_id", ""))


def _revoke_token(token: str):
    tokens = _load_tokens()
    if token in tokens["tokens"]:
        del tokens["tokens"][token]
        _save_tokens(tokens)


async def _current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_AUTH_SCHEME),
) -> Dict[str, Any]:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = _user_from_token(creds.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


def _current_user_from_bearer_or_query(request: Request, token_qs: Optional[str]) -> Dict[str, Any]:
    token = token_qs
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = _user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


def _session_path_for_user(user_id: str, session_id: str) -> Path:
    if not session_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    user_dir = SESSIONS_ROOT / user_id
    user_dir.mkdir(exist_ok=True)
    return user_dir / f"{session_id}.json"


def _ensure_default_users():
    users_data = _load_users()
    users = users_data.get("users", [])
    changed = False

    for seed in DEFAULT_USERS:
        email = _norm_email(seed["email"])
        username = _norm_username(seed["username"])
        existing = next((u for u in users if _norm_email(u.get("email", "")) == email), None)

        if existing:
            if not existing.get("username"):
                existing["username"] = username
                changed = True
            continue

        if any(_norm_username(u.get("username", "")) == username for u in users):
            continue

        hashed = _hash_password(seed["password"])
        users.append(
            {
                "id": str(uuid.uuid4()),
                "username": username,
                "name": seed["name"],
                "email": email,
                "password_salt": hashed["salt"],
                "password_hash": hashed["hash"],
                "created_at": datetime.utcnow().isoformat(),
            }
        )
        changed = True

    if changed:
        users_data["users"] = users
        _save_users(users_data)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SaveRequest(BaseModel):
    session_id: str
    source_filename: str
    uploaded_at: str
    sentences: list


class AuthRequest(BaseModel):
    login: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    username: str = Field(min_length=3, max_length=24)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

_ensure_default_users()

@app.post("/api/auth/register")
async def register(body: RegisterRequest):
    email = _norm_email(str(body.email))
    username = _norm_username(body.username)

    if not _is_valid_username(username):
        raise HTTPException(
            status_code=422,
            detail="Username must be 3-24 chars, start with a letter, and use only lowercase letters, numbers, or underscore.",
        )

    if _get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if _get_user_by_username(username):
        raise HTTPException(status_code=409, detail="This username is already taken.")

    hashed = _hash_password(body.password)
    users_data = _load_users()

    user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "name": body.name.strip(),
        "email": email,
        "password_salt": hashed["salt"],
        "password_hash": hashed["hash"],
        "created_at": datetime.utcnow().isoformat(),
    }

    users_data["users"].append(user)
    _save_users(users_data)

    return {
        "ok": True,
        "message": "Account created successfully. Please log in.",
        "user": {"id": user["id"], "username": user["username"], "name": _display_name(user), "email": user["email"]},
    }


@app.post("/api/auth/login")
async def login(body: AuthRequest):
    user = _find_user_for_login(body.login)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")

    if not _verify_password(body.password, user["password_salt"], user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")

    token = _issue_token(user["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "name": _display_name(user), "email": user["email"]},
    }


@app.get("/api/auth/me")
async def me(user: Dict[str, Any] = Depends(_current_user)):
    return {"id": user["id"], "name": _display_name(user), "email": user["email"]}


@app.post("/api/auth/logout")
async def logout(creds: Optional[HTTPAuthorizationCredentials] = Depends(_AUTH_SCHEME)):
    if creds and creds.scheme.lower() == "bearer":
        _revoke_token(creds.credentials)
    return {"ok": True}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), _: Dict[str, Any] = Depends(_current_user)):
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
async def save_session(body: SaveRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Persist a graded session to the storage directory."""
    session_data = body.model_dump()

    # Capture user info and recompute sentence grades server-side for integrity
    user_name = _display_name(user)
    for s in session_data["sentences"]:
        grades = [t["grade"] for t in s.get("triples", []) if t.get("grade") is not None]
        s["sentence_grade"] = round(sum(grades) / len(grades), 2) if grades else None
        
        # Set author for triples that have been graded
        for t in s.get("triples", []):
            if t.get("grade") is not None and not t.get("author"):
                t["author"] = user_name

    session_data["owner_user_id"] = user["id"]
    out_path = _session_path_for_user(user["id"], body.session_id)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(session_data, fh, indent=2, ensure_ascii=False)

    return {"session_id": body.session_id, "saved_at": datetime.utcnow().isoformat()}


@app.get("/api/download/{session_id}/{fmt}")
async def download_session(session_id: str, fmt: str, user: Dict[str, Any] = Depends(_current_user)):
    """Download a saved session in the requested format."""
    json_path = _session_path_for_user(user["id"], session_id)
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
async def get_session(session_id: str, user: Dict[str, Any] = Depends(_current_user)):
    """Return the full saved session JSON (used by the frontend to resume a session)."""
    json_path = _session_path_for_user(user["id"], session_id)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    with open(json_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@app.get("/api/preview/{session_id}", response_class=HTMLResponse)
async def preview_session(
    session_id: str,
    request: Request,
    token: Optional[str] = Query(default=None),
):
    """Render an HTML preview of a saved graded session (opens in browser tab)."""
    user = _current_user_from_bearer_or_query(request, token)
    json_path = _session_path_for_user(user["id"], session_id)
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
async def list_sessions(user: Dict[str, Any] = Depends(_current_user)):
    """List all saved session files."""
    sessions = []
    user_dir = SESSIONS_ROOT / user["id"]
    user_dir.mkdir(exist_ok=True)
    for p in sorted(user_dir.glob("*.json")):
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
# Suggestion and voting endpoints
# ---------------------------------------------------------------------------

class TripleSuggestionRequest(BaseModel):
    session_id: str
    sentence_id: int
    triple_id: str
    subject: str
    predicate: str
    object: str
    reason: Optional[str] = None


class VoteRequest(BaseModel):
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    vote: Optional[str] = None  # "yes", "no", numeric grade, or null to clear


class EditSuggestionRequest(BaseModel):
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    subject: str
    predicate: str
    object: str
    reason: Optional[str] = None


@app.post("/api/suggestions/add")
async def add_suggestion(body: TripleSuggestionRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Add a suggested triple edit."""
    user_name = _display_name(user)
    json_path = _session_path_for_user(user["id"], body.session_id)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    
    with open(json_path, "r", encoding="utf-8") as fh:
        session = json.load(fh)
    
    # Find the sentence and triple
    sentence = None
    triple = None
    for s in session.get("sentences", []):
        if s.get("id") == body.sentence_id:
            sentence = s
            for t in s.get("triples", []):
                if t.get("id") == body.triple_id:
                    triple = t
                    break
            break
    
    if not sentence or not triple:
        raise HTTPException(status_code=404, detail="Sentence or triple not found.")
    
    # Create suggestion
    suggestion_id = str(uuid.uuid4())
    suggestion = {
        "id": suggestion_id,
        "author": user_name,
        "subject": body.subject,
        "predicate": body.predicate,
        "object": body.object,
        "reason": body.reason or "",
        "created_at": datetime.utcnow().isoformat(),
        "votes": {},
    }
    
    if "suggestions" not in triple:
        triple["suggestions"] = []
    triple["suggestions"].append(suggestion)
    
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(session, fh, indent=2, ensure_ascii=False)
    
    return {"suggestion_id": suggestion_id, "ok": True}


@app.post("/api/suggestions/vote")
async def vote_on_suggestion(body: VoteRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Vote on a suggested triple edit."""
    user_name = _display_name(user)
    json_path = _session_path_for_user(user["id"], body.session_id)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    
    with open(json_path, "r", encoding="utf-8") as fh:
        session = json.load(fh)
    
    # Find the sentence, triple, and suggestion
    sentence = None
    triple = None
    suggestion = None
    for s in session.get("sentences", []):
        if s.get("id") == body.sentence_id:
            sentence = s
            for t in s.get("triples", []):
                if t.get("id") == body.triple_id:
                    triple = t
                    for sug in t.get("suggestions", []):
                        if sug.get("id") == body.suggestion_id:
                            suggestion = sug
                            break
                    break
            break
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    
    # Record or clear vote (toggle support)
    if "votes" not in suggestion:
        suggestion["votes"] = {}
    existing_vote = suggestion["votes"].get(user_name)
    if body.vote is None or body.vote == "" or existing_vote == body.vote:
        suggestion["votes"].pop(user_name, None)
    else:
        suggestion["votes"][user_name] = body.vote
    
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(session, fh, indent=2, ensure_ascii=False)
    
    return {"ok": True}


@app.post("/api/suggestions/edit")
async def edit_suggestion(body: EditSuggestionRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Edit a suggestion (only the author can edit)."""
    user_name = _display_name(user)
    json_path = _session_path_for_user(user["id"], body.session_id)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    with open(json_path, "r", encoding="utf-8") as fh:
        session = json.load(fh)

    for s in session.get("sentences", []):
        if s.get("id") == body.sentence_id:
            for t in s.get("triples", []):
                if t.get("id") == body.triple_id:
                    for sug in t.get("suggestions", []):
                        if sug.get("id") == body.suggestion_id:
                            if sug.get("author") != user_name:
                                raise HTTPException(status_code=403, detail="Only the author can edit this suggestion.")
                            sug["subject"] = body.subject
                            sug["predicate"] = body.predicate
                            sug["object"] = body.object
                            sug["reason"] = body.reason or ""
                            sug["updated_at"] = datetime.utcnow().isoformat()
                            with open(json_path, "w", encoding="utf-8") as out:
                                json.dump(session, out, indent=2, ensure_ascii=False)
                            return {"ok": True}

    raise HTTPException(status_code=404, detail="Suggestion not found.")


@app.delete("/api/suggestions/{session_id}/{sentence_id}/{triple_id}/{suggestion_id}")
async def delete_suggestion(
    session_id: str,
    sentence_id: int,
    triple_id: str,
    suggestion_id: str,
    user: Dict[str, Any] = Depends(_current_user)
):
    """Delete a suggestion (only the author can delete)."""
    user_name = _display_name(user)
    json_path = _session_path_for_user(user["id"], session_id)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    
    with open(json_path, "r", encoding="utf-8") as fh:
        session = json.load(fh)
    
    # Find and delete the suggestion
    for s in session.get("sentences", []):
        if s.get("id") == sentence_id:
            for t in s.get("triples", []):
                if t.get("id") == triple_id:
                    suggestions = t.get("suggestions", [])
                    for i, sug in enumerate(suggestions):
                        if sug.get("id") == suggestion_id:
                            if sug.get("author") != user_name:
                                raise HTTPException(status_code=403, detail="Only the author can delete this suggestion.")
                            suggestions.pop(i)
                            with open(json_path, "w", encoding="utf-8") as fh:
                                json.dump(session, fh, indent=2, ensure_ascii=False)
                            return {"ok": True}
    
    raise HTTPException(status_code=404, detail="Suggestion not found.")


# ---------------------------------------------------------------------------
# Serve the React build in production
# Mount AFTER all API routes so /api/* is never intercepted.
# ---------------------------------------------------------------------------
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="static")
