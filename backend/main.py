"""  
main.py — FastAPI backend for the Ontology Triple Grading Tool. 

Endpoints:
  POST /api/upload              → parse uploaded file → return session data
  POST /api/save                → persist graded session to storage/
  GET  /api/download/{id}/{fmt} → stream file in chosen format
  GET  /api/preview/{id}        → render HTML preview of graded session
  GET  /api/sessions            → list saved sessions
"""

import copy
import hashlib
import html
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth import (
    current_user,
    current_user_from_bearer_or_query,
    ensure_default_users,
    find_user_for_login,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    hash_password,
    issue_token,
    load_tokens,
    load_users,
    revoke_token,
    save_tokens,
    save_users,
    upsert_user_db,
    user_from_token,
    verify_password,
)
from config import APP_TITLE, APP_VERSION, CORS_ORIGINS, FRONTEND_DIST, SESSIONS_ROOT, STORAGE_DIR, TOKENS_FILE, USERS_FILE
from database import (
    delete_sessions_db,
    init_database,
    list_sessions_db,
    load_session_db,
    save_single_session_db,
    use_database_storage,
)
from exporter import to_csv, to_excel, to_json, to_pdf, to_word
from models import (
    ApproveSuggestionRequest,
    AuthRequest,
    EditSuggestionRequest,
    EvaluationRequest,
    RegisterRequest,
    SaveRequest,
    TripleSuggestionRequest,
    VoteRequest,
    TripleCommentRequest,
    CommentReplyRequest,
    SuggestionReplyRequest,
    NotificationReadRequest,
    NotificationReadAllRequest,
    UpdateProfileRequest,
    GetSecurityQuestionRequest,
    ResetPasswordWithQuestionRequest,
    DeleteAccountRequest,
    CreateSessionRequest,
    WorkflowSuggestionRequest,
    WorkflowVoteRequest,
    WorkflowApproveRequest,
)
from parser import parse_file_rich
from services import (
    apply_collaborative_grades,
    build_adjudicated_gold_set,
    include_in_adjudicated_gold,
    calculate_average,
    calculate_session_activity_for_user,
    calculate_session_grading_stats,
    can_approve_session,
    can_edit_session_directly,
    can_suggest_session,
    is_session_owner,
    merge_existing_sentence_comments,
    merge_existing_suggestions,
    normalize_grade_value,
    normalize_sentence_comments,
    normalize_sentence_metric_by_user,
    normalize_sentence_metric_value,
    project_session_for_view,
    root_session_id,
    sentence_groups_to_draft_sentences,
    session_for_user_view,
    with_session_access_flags,
)
from sessions import (
    find_existing_session_path,
    load_existing_session,
    load_session_for_access,
    save_loaded_session,
)
from utils import display_name, is_valid_username, norm_email, norm_username

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
# WebSocket Real-Time Broadcasting
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def broadcast(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            for connection in list(self.active_connections[session_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(session_id, connection)

manager = ConnectionManager()

@app.websocket("/api/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
    except Exception:
        manager.disconnect(session_id, websocket)


# -------------------------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def _session_path_for_user(user_id: str, session_id: str) -> Path:
    if not session_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    user_dir = SESSIONS_ROOT / user_id
    user_dir.mkdir(exist_ok=True)
    return user_dir / f"{session_id}.json"


def _find_existing_session_path(session_id: str) -> Optional[Path]:
    if not session_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    if use_database_storage():
        return None
    for p in SESSIONS_ROOT.glob(f"*/{session_id}.json"):
        return p
    return None


def _get_session_path_for_access(session_id: str, owner_user_id: Optional[str] = None) -> Path:
    existing = _find_existing_session_path(session_id)
    if existing:
        return existing
    if owner_user_id:
        return _session_path_for_user(owner_user_id, session_id)
    raise HTTPException(status_code=404, detail="Session not found.")


def _load_session_for_access(session_id: str) -> tuple[Optional[Path], Dict[str, Any]]:
    if use_database_storage():
        session = load_session_db(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        return None, session

    json_path = _get_session_path_for_access(session_id)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    with open(json_path, "r", encoding="utf-8") as fh:
        session = json.load(fh)
    return json_path, session


def _save_loaded_session(session_path: Optional[Path], session: Dict[str, Any], owner_user_id: Optional[str] = None) -> None:
    if use_database_storage():
        if owner_user_id and not session.get("owner_user_id"):
            session["owner_user_id"] = owner_user_id
        save_single_session_db(session)
        return

    target_path = session_path
    if not target_path:
        target_user_id = str(owner_user_id or session.get("owner_user_id") or "").strip()
        session_id = str(session.get("session_id", "")).strip()
        existing = _find_existing_session_path(session_id) if session_id else None
        if existing:
            target_path = existing
        elif target_user_id and session_id:
            target_path = _session_path_for_user(target_user_id, session_id)
        else:
            raise HTTPException(status_code=400, detail="Cannot save session without session ID and owner ID.")
    with open(target_path, "w", encoding="utf-8") as fh:
        json.dump(session, fh, indent=2, ensure_ascii=False)


def _load_existing_session(session_id: str) -> tuple[Optional[Path], Optional[Dict[str, Any]]]:
    if use_database_storage():
        return None, load_session_db(session_id)

    existing_path = _find_existing_session_path(session_id)
    if not existing_path or not existing_path.exists():
        return None, None
    try:
        with open(existing_path, "r", encoding="utf-8") as fh:
            return existing_path, json.load(fh)
    except Exception:
        return existing_path, None


def _is_session_owner(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    user_id = user.get("id", "")
    user_username = norm_username(user.get("username", ""))
    user_email = norm_email(user.get("email", ""))

    owner_user_id = str(session.get("owner_user_id") or "").strip()
    if owner_user_id and (
        owner_user_id == user_id
        or norm_username(owner_user_id) == user_username
        or norm_email(owner_user_id) == user_email
    ):
        return True

    owner_email = session.get("owner_email")
    if owner_email and norm_email(owner_email) == user_email:
        return True

    owner_username = session.get("owner_username")
    if owner_username and norm_username(owner_username) == user_username:
        return True

    owner_name = (session.get("owner_name") or "").strip()
    if owner_name and owner_name in {
        (user.get("name") or "").strip(),
        user_username,
    }:
        return True

    # Legacy fallback for sessions saved before owner metadata was persisted,
    # where folders/IDs may have used username or email identifiers.
    parent_owner = str(session_path.parent.name or "").strip() if session_path else ""
    return bool(
        parent_owner
        and (
            parent_owner == user_id
            or norm_username(parent_owner) == user_username
            or norm_email(parent_owner) == user_email
        )
    )


def _root_session_id(session: Dict[str, Any]) -> str:
    return str(session.get("root_session_id") or session.get("session_id") or "").strip()


def _can_approve_session(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    # In v2 collaboration mode, only the owner can approve/unapprove suggestions.
    return _is_session_owner(session, session_path, user)


def _can_suggest_session(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    # In v2 collaboration mode, only collaborators (non-owners) can add triple suggestions.
    return not _is_session_owner(session, session_path, user)


def _can_edit_session_directly(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    # Shared v2 rule: owner can vote/approve, but does not grade.
    return not _is_session_owner(session, session_path, user)


def _normalize_grade_value(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0 or numeric > 10:
        return None
    if numeric.is_integer():
        return float(int(numeric))
    return round(numeric, 2)


def _normalize_grades_by_user(
    raw_grades: Any,
    *,
    fallback_grade: Any = None,
    fallback_author: str = "",
    fallback_user_id: str = "",
    fallback_graded_at: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}

    if isinstance(raw_grades, dict):
        for key, payload in raw_grades.items():
            if isinstance(payload, (int, float)):
                grade = _normalize_grade_value(payload)
                if grade is not None:
                    u_id = str(key).strip()
                    if u_id:
                        normalized[u_id] = {
                            "user_id": u_id,
                            "user_name": u_id,
                            "grade": grade,
                            "graded_at": None,
                        }
                continue
            if not isinstance(payload, dict):
                continue
            grade = _normalize_grade_value(payload.get("grade"))
            if grade is None:
                continue
            user_id = str(payload.get("user_id") or key or "").strip()
            if not user_id:
                continue
            user_name = str(payload.get("user_name") or user_id).strip() or user_id
            normalized[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "grade": grade,
                "graded_at": payload.get("graded_at"),
            }

    if normalized:
        return normalized

    legacy_grade = _normalize_grade_value(fallback_grade)
    if legacy_grade is None:
        return normalized

    legacy_name = str(fallback_author or "Legacy grader").strip() or "Legacy grader"
    legacy_id = str(fallback_user_id or "").strip()
    if not legacy_id:
        slug = re.sub(r"[^a-z0-9_]+", "_", legacy_name.lower()).strip("_") or "grader"
        legacy_id = f"legacy_{slug}"

    normalized[legacy_id] = {
        "user_id": legacy_id,
        "user_name": legacy_name,
        "grade": legacy_grade,
        "graded_at": fallback_graded_at,
    }
    return normalized


def _normalize_sentence_metric_value(value: Any) -> Optional[float]:
    return _normalize_grade_value(value)


def _normalize_sentence_metric_by_user(
    raw_metrics: Any,
    *,
    fallback_value: Any = None,
    fallback_user_id: str = "",
    fallback_user_name: str = "",
    fallback_updated_at: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}

    if isinstance(raw_metrics, dict):
        for key, payload in raw_metrics.items():
            if not isinstance(payload, dict):
                continue

            value = _normalize_sentence_metric_value(payload.get("value"))
            if value is None:
                continue

            user_id = str(payload.get("user_id") or key or "").strip()
            if not user_id:
                continue

            user_name = str(payload.get("user_name") or user_id).strip() or user_id
            normalized[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "value": value,
                "updated_at": payload.get("updated_at"),
            }

    if normalized:
        return normalized

    fallback_metric = _normalize_sentence_metric_value(fallback_value)
    if fallback_metric is None:
        return normalized

    metric_user_name = str(fallback_user_name or "Legacy grader").strip() or "Legacy grader"
    metric_user_id = str(fallback_user_id or "").strip()
    if not metric_user_id:
        slug = re.sub(r"[^a-z0-9_]+", "_", metric_user_name.lower()).strip("_") or "grader"
        metric_user_id = f"legacy_{slug}"

    normalized[metric_user_id] = {
        "user_id": metric_user_id,
        "user_name": metric_user_name,
        "value": fallback_metric,
        "updated_at": fallback_updated_at,
    }
    return normalized


def _normalize_sentence_comments(
    raw_comments: Any,
    *,
    fallback_text: str = "",
    fallback_author: str = "",
    fallback_user_id: str = "",
    fallback_created_at: Optional[str] = None,
) -> list[Dict[str, Any]]:
    normalized: list[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    if isinstance(raw_comments, list):
        for idx, payload in enumerate(raw_comments):
            if not isinstance(payload, dict):
                continue

            text = str(payload.get("text") or payload.get("comment") or "").strip()
            if not text:
                continue

            comment_id = str(payload.get("id") or "").strip()
            if not comment_id:
                comment_id = f"comment_{idx}_{uuid.uuid4().hex[:8]}"
            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)

            user_id = str(payload.get("user_id") or payload.get("author_user_id") or "").strip()
            author = str(payload.get("author") or payload.get("user_name") or "").strip()
            if not author:
                author = user_id or "User"

            if author == "System Migration" or author == "System" or "Legacy Suggestion Migration" in text:
                continue

            created_at = payload.get("created_at")
            if created_at is None:
                created_at = payload.get("posted_at")
            if created_at is None:
                created_at = fallback_created_at or datetime.utcnow().isoformat()

            read_by_raw = payload.get("read_by") or []
            if not isinstance(read_by_raw, list):
                read_by_raw = [read_by_raw] if read_by_raw else []
            read_by = list(set([str(uid).strip() for uid in read_by_raw if uid]))
            if user_id and user_id not in read_by:
                read_by.append(user_id)

            replies = payload.get("replies") or []
            normalized_replies = []
            if isinstance(replies, list):
                for r_idx, r_payload in enumerate(replies):
                    if not isinstance(r_payload, dict):
                        continue
                    r_text = str(r_payload.get("text") or r_payload.get("comment") or "").strip()
                    if not r_text:
                        continue
                    r_id = str(r_payload.get("id") or "").strip()
                    if not r_id:
                        r_id = f"reply_{r_idx}_{uuid.uuid4().hex[:8]}"
                    r_user_id = str(r_payload.get("user_id") or r_payload.get("author_user_id") or "").strip()
                    r_author = str(r_payload.get("author") or r_payload.get("user_name") or "").strip()
                    if not r_author:
                        r_author = r_user_id or "User"
                    r_created_at = r_payload.get("created_at") or r_payload.get("posted_at") or datetime.utcnow().isoformat()
                    
                    r_read_by_raw = r_payload.get("read_by") or []
                    if not isinstance(r_read_by_raw, list):
                        r_read_by_raw = [r_read_by_raw] if r_read_by_raw else []
                    r_read_by = list(set([str(uid).strip() for uid in r_read_by_raw if uid]))
                    if r_user_id and r_user_id not in r_read_by:
                        r_read_by.append(r_user_id)

                    normalized_replies.append({
                        "id": r_id,
                        "user_id": r_user_id,
                        "author": r_author,
                        "text": r_text,
                        "created_at": r_created_at,
                        "read_by": r_read_by,
                        "parent_reply_id": r_payload.get("parent_reply_id"),
                    })
            normalized_replies.sort(key=lambda row: str(row.get("created_at") or ""))

            normalized.append({
                "id": comment_id,
                "user_id": user_id,
                "author": author,
                "text": text,
                "created_at": created_at,
                "read_by": read_by,
                "replies": normalized_replies,
            })

    if not normalized:
        legacy_text = str(fallback_text or "").strip()
        if legacy_text:
            legacy_author = str(fallback_author or "Legacy comment").strip() or "Legacy comment"
            legacy_user_id = str(fallback_user_id or "").strip()
            legacy_hash = hashlib.sha1(legacy_text.encode("utf-8")).hexdigest()[:10]
            
            legacy_read_by: list[str] = []
            if legacy_user_id:
                legacy_read_by.append(legacy_user_id)

            normalized.append({
                "id": f"legacy_comment_{legacy_hash}",
                "user_id": legacy_user_id,
                "author": legacy_author,
                "text": legacy_text,
                "created_at": fallback_created_at or datetime.utcnow().isoformat(),
                "read_by": legacy_read_by,
            })

    normalized.sort(key=lambda row: str(row.get("created_at") or ""))
    return normalized


def _normalize_suggestions(raw_suggestions: Any) -> list[Dict[str, Any]]:
    normalized = []
    if not isinstance(raw_suggestions, list):
        return normalized
    for idx, payload in enumerate(raw_suggestions):
        if not isinstance(payload, dict):
            continue
        sug_id = str(payload.get("id") or "").strip()
        if not sug_id:
            sug_id = f"suggestion_{idx}_{uuid.uuid4().hex[:8]}"
        
        author = str(payload.get("author") or "").strip()
        user_id = str(payload.get("user_id") or "").strip()
        if not author:
            author = user_id or "User"
        
        read_by_raw = payload.get("read_by") or []
        if not isinstance(read_by_raw, list):
            read_by_raw = [read_by_raw] if read_by_raw else []
        read_by = list(set([str(uid).strip() for uid in read_by_raw if uid]))
        if user_id and user_id not in read_by:
            read_by.append(user_id)
            
        replies = payload.get("replies") or []
        normalized_replies = []
        if isinstance(replies, list):
            for r_idx, r_payload in enumerate(replies):
                if not isinstance(r_payload, dict):
                    continue
                r_text = str(r_payload.get("text") or r_payload.get("comment") or "").strip()
                if not r_text:
                    continue
                r_id = str(r_payload.get("id") or "").strip()
                if not r_id:
                    r_id = f"reply_{r_idx}_{uuid.uuid4().hex[:8]}"
                r_user_id = str(r_payload.get("user_id") or r_payload.get("author_user_id") or "").strip()
                r_author = str(r_payload.get("author") or r_payload.get("user_name") or "").strip()
                if not r_author:
                    r_author = r_user_id or "User"
                r_created_at = r_payload.get("created_at") or r_payload.get("posted_at") or datetime.utcnow().isoformat()
                
                r_read_by_raw = r_payload.get("read_by") or []
                if not isinstance(r_read_by_raw, list):
                    r_read_by_raw = [r_read_by_raw] if r_read_by_raw else []
                r_read_by = list(set([str(uid).strip() for uid in r_read_by_raw if uid]))
                if r_user_id and r_user_id not in r_read_by:
                    r_read_by.append(r_user_id)
                
                normalized_replies.append({
                    "id": r_id,
                    "user_id": r_user_id,
                    "author": r_author,
                    "text": r_text,
                    "created_at": r_created_at,
                    "read_by": r_read_by,
                    "parent_reply_id": r_payload.get("parent_reply_id"),
                })
        normalized_replies.sort(key=lambda row: str(row.get("created_at") or ""))
        
        normalized.append({
            "id": sug_id,
            "author": author,
            "user_id": user_id,
            "subject": str(payload.get("subject") or "").strip(),
            "predicate": str(payload.get("predicate") or "").strip(),
            "object": str(payload.get("object") or "").strip(),
            "reason": str(payload.get("reason") or "").strip(),
            "created_at": payload.get("created_at") or datetime.utcnow().isoformat(),
            "votes": payload.get("votes") or {},
            "status": payload.get("status") or "pending",
            "approved_by": payload.get("approved_by"),
            "read_by": read_by,
            "replies": normalized_replies,
        })
    return normalized


def _merge_triple_comments(
    incoming_comments: Any,
    existing_comments: Any,
) -> list[Dict[str, Any]]:
    norm_incoming = _normalize_sentence_comments(incoming_comments)
    norm_existing = _normalize_sentence_comments(existing_comments)

    merged_by_id = {str(c.get("id")): c for c in norm_existing if c.get("id")}
    for c in norm_incoming:
        cid = str(c.get("id"))
        if cid:
            if cid in merged_by_id:
                existing_r = merged_by_id[cid].get("replies") or []
                incoming_r = c.get("replies") or []
                merged_replies_dict = {str(r.get("id")): r for r in existing_r}
                for r in incoming_r:
                    merged_replies_dict[str(r.get("id"))] = r
                c["replies"] = sorted(merged_replies_dict.values(), key=lambda row: str(row.get("created_at") or ""))
            merged_by_id[cid] = c

    return sorted(merged_by_id.values(), key=lambda row: str(row.get("created_at") or ""))


def _apply_collaborative_grades(
    incoming_session: Dict[str, Any],
    existing_session: Optional[Dict[str, Any]],
    user: Dict[str, Any],
) -> None:
    user_id = str(user.get("id") or "").strip()
    user_name = display_name(user)
    now_iso = datetime.utcnow().isoformat()
    user_can_grade = not _is_session_owner(existing_session or incoming_session, None, user)

    existing_sentences = {
        s.get("id"): s
        for s in (existing_session or {}).get("sentences", [])
        if s.get("id") is not None
    }
    owner_fallback_user_id = str((existing_session or {}).get("owner_user_id") or "").strip()
    owner_fallback_user_name = str((existing_session or {}).get("owner_name") or "").strip()

    for sentence in incoming_session.get("sentences", []):
        existing_sentence = existing_sentences.get(sentence.get("id"))

        existing_completeness = _normalize_sentence_metric_by_user(
            (existing_sentence or {}).get("completeness_by_user"),
            fallback_value=(existing_sentence or {}).get("completeness"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=(existing_sentence or {}).get("completeness_updated_at"),
        )
        incoming_completeness = _normalize_sentence_metric_by_user(
            sentence.get("completeness_by_user"),
            fallback_value=sentence.get("completeness"),
            fallback_user_id=user_id,
            fallback_user_name=user_name,
            fallback_updated_at=sentence.get("completeness_updated_at"),
        )
        merged_completeness = dict(existing_completeness)
        for metric_user_id, payload in incoming_completeness.items():
            if metric_user_id not in merged_completeness:
                merged_completeness[metric_user_id] = payload

        my_completeness = _normalize_sentence_metric_value(sentence.get("completeness"))
        if not user_can_grade:
            merged_completeness.pop(user_id, None)
            sentence["completeness"] = None
            sentence.pop("completeness_updated_at", None)
        elif my_completeness is None:
            merged_completeness.pop(user_id, None)
            sentence["completeness"] = None
            sentence.pop("completeness_updated_at", None)
        else:
            merged_completeness[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "value": my_completeness,
                "updated_at": now_iso,
            }
            sentence["completeness"] = my_completeness
            sentence["completeness_updated_at"] = now_iso
        sentence["completeness_by_user"] = merged_completeness

        existing_external = _normalize_sentence_metric_by_user(
            (existing_sentence or {}).get("external_relation_by_user"),
            fallback_value=(existing_sentence or {}).get("external_relation"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=(existing_sentence or {}).get("external_relation_updated_at"),
        )
        incoming_external = _normalize_sentence_metric_by_user(
            sentence.get("external_relation_by_user"),
            fallback_value=sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation"),
            fallback_user_id=user_id,
            fallback_user_name=user_name,
            fallback_updated_at=sentence.get("external_relation_updated_at"),
        )
        merged_external = dict(existing_external)
        for metric_user_id, payload in incoming_external.items():
            if metric_user_id not in merged_external:
                merged_external[metric_user_id] = payload

        raw_ext = sentence.get("external_relation")
        raw_rel = sentence.get("relation")
        if raw_rel is not None and (raw_ext is None or raw_rel != (existing_sentence or {}).get("external_relation")):
            my_external = _normalize_sentence_metric_value(raw_rel)
        else:
            my_external = _normalize_sentence_metric_value(raw_ext if raw_ext is not None else raw_rel)

        if not user_can_grade:
            merged_external.pop(user_id, None)
            sentence["external_relation"] = None
            sentence["relation"] = None
            sentence.pop("external_relation_updated_at", None)
        elif my_external is None:
            merged_external.pop(user_id, None)
            sentence["external_relation"] = None
            sentence["relation"] = None
            sentence.pop("external_relation_updated_at", None)
        else:
            merged_external[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "value": my_external,
                "updated_at": now_iso,
            }
            sentence["external_relation"] = my_external
            sentence["relation"] = my_external
            sentence["external_relation_updated_at"] = now_iso
        sentence["external_relation_by_user"] = merged_external

        existing_triples = {
            t.get("id"): t
            for t in (existing_sentence or {}).get("triples", [])
            if t.get("id") is not None
        }

        is_owner_user = _is_session_owner(existing_session or incoming_session, None, user)

        for triple in sentence.get("triples", []):
            triple_id = triple.get("id")
            existing_triple = existing_triples.get(triple_id, {})

            if existing_triple:
                if is_owner_user:
                    triple["subject"] = triple.get("subject") if triple.get("subject") is not None else existing_triple.get("subject", "")
                    triple["predicate"] = triple.get("predicate") if triple.get("predicate") is not None else existing_triple.get("predicate", "")
                    triple["object"] = triple.get("object") if triple.get("object") is not None else existing_triple.get("object", "")
                else:
                    # Triple text and suggestion threads are collaborative shared state;
                    # preserve the latest server copy to avoid stale client overwrites for non-owners.
                    triple["subject"] = existing_triple.get("subject", triple.get("subject"))
                    triple["predicate"] = existing_triple.get("predicate", triple.get("predicate"))
                    triple["object"] = existing_triple.get("object", triple.get("object"))
                
                for key in ("is_new_suggestion", "status", "suggested_by", "suggested_by_id", "approved_by", "approved_at"):
                    if is_owner_user:
                        if key not in triple and key in existing_triple:
                            triple[key] = existing_triple[key]
                    else:
                        if key in existing_triple:
                            triple[key] = existing_triple[key]

                existing_marked = existing_triple.get("marked_for_removal", False)
                existing_by = existing_triple.get("marked_for_removal_by")
                existing_by_name = existing_triple.get("marked_for_removal_by_name")
                existing_reason = existing_triple.get("removal_reason", "")

                if existing_marked:
                    is_authorized_to_modify = (
                        _is_session_owner(incoming_session, None, user)
                        or str(user.get("id") or "").strip() == str(existing_by or "").strip()
                    )
                    if not is_authorized_to_modify:
                        triple["marked_for_removal"] = True
                        triple["marked_for_removal_by"] = existing_by
                        triple["marked_for_removal_by_name"] = existing_by_name
                        triple["removal_reason"] = existing_reason
                    else:
                        triple["marked_for_removal"] = triple.get("marked_for_removal", False)
                        triple["marked_for_removal_by"] = triple.get("marked_for_removal_by")
                        triple["marked_for_removal_by_name"] = triple.get("marked_for_removal_by_name")
                        triple["removal_reason"] = triple.get("removal_reason", "")
                else:
                    triple["marked_for_removal"] = triple.get("marked_for_removal", False)
                    triple["marked_for_removal_by"] = triple.get("marked_for_removal_by")
                    triple["marked_for_removal_by_name"] = triple.get("marked_for_removal_by_name")
                    triple["removal_reason"] = triple.get("removal_reason", "")

                triple["suggestions"] = _merge_suggestions_lists(
                    triple.get("suggestions") or [],
                    existing_triple.get("suggestions") or []
                )

                triple["triple_comments"] = _merge_triple_comments(
                    triple.get("triple_comments"),
                    existing_triple.get("triple_comments")
                )
            else:
                triple["triple_comments"] = _normalize_sentence_comments(triple.get("triple_comments"))

            existing_grades = _normalize_grades_by_user(
                existing_triple.get("grades_by_user"),
                fallback_grade=existing_triple.get("grade"),
                fallback_author=str(existing_triple.get("author") or ""),
                fallback_user_id=owner_fallback_user_id,
                fallback_graded_at=existing_triple.get("graded_at"),
            )
            incoming_grades = _normalize_grades_by_user(triple.get("grades_by_user"))

            merged_grades = dict(existing_grades)
            for grader_id, grade_payload in incoming_grades.items():
                if grader_id not in merged_grades:
                    merged_grades[grader_id] = grade_payload

            my_grade = _normalize_grade_value(triple.get("grade"))
            if not user_can_grade:
                merged_grades.pop(user_id, None)
                triple["grade"] = None
                triple["author"] = None
                triple.pop("graded_at", None)
            elif my_grade is None:
                merged_grades.pop(user_id, None)
                triple["grade"] = None
                triple["author"] = None
                triple.pop("graded_at", None)
            else:
                merged_grades[user_id] = {
                    "user_id": user_id,
                    "user_name": user_name,
                    "grade": my_grade,
                    "graded_at": now_iso,
                }
                triple["grade"] = my_grade
                triple["author"] = user_name
                triple["graded_at"] = now_iso

            triple["grades_by_user"] = merged_grades


def _sentence_list_stats(sentences: list, owner_fallback_user_id: str) -> Dict[str, Any]:
    total_triples = 0
    graded_triples = 0
    total_grade_entries = 0
    grade_sum = 0.0

    per_grader: Dict[str, Dict[str, Any]] = {}

    for sentence in sentences:
        for triple in sentence.get("triples", []):
            if triple.get("is_new_suggestion") and triple.get("status") != "approved":
                continue
            total_triples += 1
            grades_by_user = _normalize_grades_by_user(
                triple.get("grades_by_user"),
                fallback_grade=triple.get("grade"),
                fallback_author=str(triple.get("author") or ""),
                fallback_user_id=owner_fallback_user_id,
                fallback_graded_at=triple.get("graded_at"),
            )
            triple["grades_by_user"] = grades_by_user

            if grades_by_user:
                graded_triples += 1

            for grader_id, grade_payload in grades_by_user.items():
                grade = _normalize_grade_value(grade_payload.get("grade"))
                if grade is None:
                    continue

                total_grade_entries += 1
                grade_sum += float(grade)

                grader_summary = per_grader.setdefault(
                    grader_id,
                    {
                        "user_id": grader_id,
                        "user_name": str(grade_payload.get("user_name") or grader_id),
                        "graded_triples": 0,
                        "grade_count": 0,
                        "grade_sum": 0.0,
                        "average_grade": None,
                        "latest_graded_at": None,
                    },
                )
                grader_summary["graded_triples"] += 1
                grader_summary["grade_count"] += 1
                grader_summary["grade_sum"] += float(grade)

                graded_at = grade_payload.get("graded_at")
                latest = grader_summary.get("latest_graded_at")
                if graded_at and (not latest or str(graded_at) > str(latest)):
                    grader_summary["latest_graded_at"] = graded_at

    grader_summary_rows: list[Dict[str, Any]] = []
    for item in per_grader.values():
        grade_count = int(item.get("grade_count") or 0)
        grade_sum_local = float(item.get("grade_sum") or 0.0)
        item["average_grade"] = round(grade_sum_local / grade_count, 2) if grade_count > 0 else None
        item.pop("grade_sum", None)
        grader_summary_rows.append(item)

    grader_summary_rows.sort(
        key=lambda row: (
            -(int(row.get("graded_triples") or 0)),
            str(row.get("user_name") or "").lower(),
        )
    )

    overall_avg = round(grade_sum / total_grade_entries, 2) if total_grade_entries > 0 else None
    is_completed = total_triples > 0 and graded_triples == total_triples
    completed_grader_count = sum(
        1
        for row in grader_summary_rows
        if total_triples > 0 and int(row.get("graded_triples") or 0) >= total_triples
    )

    return {
        "total_triples": total_triples,
        "graded_triples": graded_triples,
        "session_average_grade": None,
        "is_completed_grading": is_completed,
        "total_grade_entries": total_grade_entries,
        "total_unique_graders": len(grader_summary_rows),
        "completed_grader_count": completed_grader_count,
        "grader_summary": grader_summary_rows,
    }


def _session_grading_stats(session_data: Dict[str, Any]) -> Dict[str, Any]:
    owner_fallback_user_id = str(session_data.get("owner_user_id") or "").strip()
    return _sentence_list_stats(session_data.get("sentences", []), owner_fallback_user_id)


def _find_target_triple_and_sentence(session: Dict[str, Any], version_name: Optional[str], sentence_id: Any, triple_id: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if "versions" not in session:
        session["versions"] = [
            {
                "name": "Initial",
                "created_at": session.get("uploaded_at") or datetime.utcnow().isoformat(),
                "created_by": session.get("owner_user_id") or "",
                "sentences": session.get("sentences") or []
            }
        ]
        session["last_version_name"] = "Initial"
        session["current_version_name"] = "Initial"
        
    versions = session.get("versions") or []
    selected_version = None
    if version_name:
        selected_version = next((v for v in versions if v.get("name") == version_name), None)
    if not selected_version and versions:
        selected_version = versions[-1]
        
    sentences = selected_version.get("sentences", []) if selected_version else session.get("sentences", [])
    
    for s in sentences:
        sid = str(s.get("id") or s.get("sentence_id") or "")
        target_sid = str(sentence_id)
        sid_clean = sid.lstrip("s").lstrip("0") or "0" if sid.startswith("s") else sid
        tgt_clean = target_sid.lstrip("s").lstrip("0") or "0" if target_sid.startswith("s") else target_sid
        if (
            sid == target_sid
            or sid_clean == tgt_clean
            or (target_sid.isdigit() and sid == f"s{int(target_sid):04d}")
            or (sid.isdigit() and target_sid == f"s{int(sid):04d}")
        ):
            for t in s.get("triples", []):
                tid = str(t.get("id") or t.get("triple_id") or "")
                if tid == str(triple_id):
                    return s, t
    return None, None


def _find_target_sentence(session: Dict[str, Any], version_name: Optional[str], sentence_id: Any) -> Optional[Dict[str, Any]]:
    if "versions" not in session:
        session["versions"] = [
            {
                "name": "Initial",
                "created_at": session.get("uploaded_at") or datetime.utcnow().isoformat(),
                "created_by": session.get("owner_user_id") or "",
                "sentences": session.get("sentences") or []
            }
        ]
        session["last_version_name"] = "Initial"
        session["current_version_name"] = "Initial"
        
    versions = session.get("versions") or []
    selected_version = None
    if version_name:
        selected_version = next((v for v in versions if v.get("name") == version_name), None)
    if not selected_version and versions:
        selected_version = versions[-1]
        
    sentences = selected_version.get("sentences", []) if selected_version else session.get("sentences", [])
    
    for s in sentences:
        sid = str(s.get("id") or s.get("sentence_id") or "")
        target_sid = str(sentence_id)
        if sid == target_sid or (target_sid.isdigit() and sid == f"s{int(target_sid):04d}"):
            return s
    return None


def _session_activity_for_user(session_data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        return {
            "my_has_activity": False,
            "my_graded_triples": 0,
            "my_sentence_metric_updates": 0,
            "my_sentence_comment_posts": 0,
            "my_total_actions": 0,
        }

    owner_fallback_user_id = str(session_data.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(session_data.get("owner_name") or "").strip()

    my_graded_triples = 0
    my_sentence_metric_updates = 0
    my_sentence_comment_posts = 0

    for sentence in session_data.get("sentences", []):
        completeness_by_user = _normalize_sentence_metric_by_user(
            sentence.get("completeness_by_user"),
            fallback_value=sentence.get("completeness"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("completeness_updated_at"),
        )
        my_completeness = completeness_by_user.get(user_id)
        if isinstance(my_completeness, dict) and _normalize_sentence_metric_value(my_completeness.get("value")) is not None:
            my_sentence_metric_updates += 1

        external_relation_by_user = _normalize_sentence_metric_by_user(
            sentence.get("external_relation_by_user"),
            fallback_value=sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("external_relation_updated_at"),
        )
        my_external_relation = external_relation_by_user.get(user_id)
        if isinstance(my_external_relation, dict) and _normalize_sentence_metric_value(my_external_relation.get("value")) is not None:
            my_sentence_metric_updates += 1

        sentence_comments = _normalize_sentence_comments(sentence.get("sentence_comments"))
        my_sentence_comment_posts += sum(
            1
            for comment in sentence_comments
            if str(comment.get("user_id") or "").strip() == user_id
        )

        for triple in sentence.get("triples", []):
            if triple.get("is_new_suggestion") and triple.get("status") != "approved":
                continue
            grades_by_user = _normalize_grades_by_user(
                triple.get("grades_by_user"),
                fallback_grade=triple.get("grade"),
                fallback_author=str(triple.get("author") or ""),
                fallback_user_id=owner_fallback_user_id,
                fallback_graded_at=triple.get("graded_at"),
            )
            my_grade = grades_by_user.get(user_id)
            if isinstance(my_grade, dict) and _normalize_grade_value(my_grade.get("grade")) is not None:
                my_graded_triples += 1

    my_total_actions = my_graded_triples + my_sentence_metric_updates + my_sentence_comment_posts
    return {
        "my_has_activity": my_total_actions > 0,
        "my_graded_triples": my_graded_triples,
        "my_sentence_metric_updates": my_sentence_metric_updates,
        "my_sentence_comment_posts": my_sentence_comment_posts,
        "my_total_actions": my_total_actions,
    }


def _session_for_user_view(session: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    # Deep copy so caller gets a user-scoped projection without mutating storage payload.
    data = json.loads(json.dumps(session, ensure_ascii=False))

    # Normalize versions structure
    if "versions" not in data:
        data["versions"] = [
            {
                "name": "Initial",
                "created_at": data.get("uploaded_at") or datetime.utcnow().isoformat(),
                "created_by": data.get("owner_user_id") or "",
                "sentences": data.get("sentences") or []
            }
        ]
        data["last_version_name"] = "Initial"
        data["current_version_name"] = "Initial"

    user_id = str(user.get("id") or "").strip()
    owner_fallback_user_id = str(data.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(data.get("owner_name") or "").strip()

    # Process each version
    for version in data.get("versions", []):
        sentences = version.get("sentences", [])
        version_stats = _sentence_list_stats(sentences, owner_fallback_user_id)

        for sentence in sentences:
            # Normalize sentence comments
            sentence_comments = _normalize_sentence_comments(
                sentence.get("sentence_comments"),
                fallback_text=str(sentence.get("suggestion") or ""),
                fallback_author=owner_fallback_user_name,
                fallback_user_id=owner_fallback_user_id,
                fallback_created_at=sentence.get("comment_created_at"),
            )
            sentence["sentence_comments"] = sentence_comments
            sentence["comment_count"] = len(sentence_comments)
            sentence["suggestion"] = sentence_comments[-1].get("text", "") if sentence_comments else ""

            # Normalize completeness by user
            completeness_by_user = _normalize_sentence_metric_by_user(
                sentence.get("completeness_by_user"),
                fallback_value=sentence.get("completeness"),
                fallback_user_id=owner_fallback_user_id,
                fallback_user_name=owner_fallback_user_name,
                fallback_updated_at=sentence.get("completeness_updated_at"),
            )
            completeness_values = [
                float(payload.get("value"))
                for payload in completeness_by_user.values()
                if _normalize_sentence_metric_value(payload.get("value")) is not None
            ]
            current_user_completeness = completeness_by_user.get(user_id) if user_id else None
            sentence["completeness"] = (
                current_user_completeness.get("value")
                if isinstance(current_user_completeness, dict)
                else None
            )
            sentence["completeness_by_user"] = completeness_by_user
            sentence["completeness_count"] = len(completeness_values)
            sentence["completeness_average"] = (
                round(sum(completeness_values) / len(completeness_values), 2)
                if completeness_values
                else None
            )

            # Normalize external_relation by user
            external_relation_by_user = _normalize_sentence_metric_by_user(
                sentence.get("external_relation_by_user"),
                fallback_value=sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation"),
                fallback_user_id=owner_fallback_user_id,
                fallback_user_name=owner_fallback_user_name,
                fallback_updated_at=sentence.get("external_relation_updated_at"),
            )
            external_relation_values = [
                float(payload.get("value"))
                for payload in external_relation_by_user.values()
                if _normalize_sentence_metric_value(payload.get("value")) is not None
            ]
            current_user_external = external_relation_by_user.get(user_id) if user_id else None
            sentence["external_relation"] = (
                current_user_external.get("value")
                if isinstance(current_user_external, dict)
                else None
            )
            sentence["external_relation_by_user"] = external_relation_by_user
            sentence["external_relation_count"] = len(external_relation_values)
            sentence["external_relation_average"] = (
                round(sum(external_relation_values) / len(external_relation_values), 2)
                if external_relation_values
                else None
            )

            for triple in sentence.get("triples", []):
                triple["triple_comments"] = _normalize_sentence_comments(triple.get("triple_comments"))
                triple["suggestions"] = _normalize_suggestions(triple.get("suggestions"))
                grades_by_user = _normalize_grades_by_user(
                    triple.get("grades_by_user"),
                    fallback_grade=triple.get("grade"),
                    fallback_author=str(triple.get("author") or ""),
                    fallback_user_id=owner_fallback_user_id,
                    fallback_graded_at=triple.get("graded_at"),
                )
                triple["grades_by_user"] = grades_by_user
                grade_values = [
                    float(payload.get("grade"))
                    for payload in grades_by_user.values()
                    if isinstance(payload, dict) and _normalize_grade_value(payload.get("grade")) is not None
                ]
                current_user_grade = grades_by_user.get(user_id) if user_id else None

                triple["grade"] = current_user_grade.get("grade") if isinstance(current_user_grade, dict) else None
                triple["author"] = current_user_grade.get("user_name") if isinstance(current_user_grade, dict) else None
                triple["grade_count"] = len(grade_values)
                triple["grade_average"] = (
                    round(sum(grade_values) / len(grade_values), 2)
                    if grade_values
                    else None
                )

        version["session_average_grade"] = version_stats["session_average_grade"]
        version["is_completed_grading"] = version_stats["is_completed_grading"]
        version["total_grade_entries"] = version_stats["total_grade_entries"]
        version["total_unique_graders"] = version_stats["total_unique_graders"]
        version["completed_grader_count"] = version_stats["completed_grader_count"]
        version["grader_summary"] = version_stats["grader_summary"]

    # By default, we select the active version name if specified in data, or the latest
    active_name = data.get("current_version_name")
    versions_list = data["versions"]
    selected_version = next((v for v in versions_list if v.get("name") == active_name), None)
    if not selected_version and versions_list:
        selected_version = versions_list[-1]
        data["current_version_name"] = selected_version.get("name")

    if selected_version:
        data["sentences"] = selected_version.get("sentences") or []
        data["session_average_grade"] = selected_version.get("session_average_grade")
        data["is_completed_grading"] = selected_version.get("is_completed_grading")
        data["total_grade_entries"] = selected_version.get("total_grade_entries")
        data["total_unique_graders"] = selected_version.get("total_unique_graders")
        data["completed_grader_count"] = selected_version.get("completed_grader_count")
        data["grader_summary"] = selected_version.get("grader_summary")
        if user_id:
            my_summary = next((row for row in selected_version.get("grader_summary", []) if row.get("user_id") == user_id), None)
            data["my_graded_triples"] = int(my_summary.get("graded_triples") or 0) if my_summary else 0

    is_owner = _is_session_owner(data, None, user)
    owner_draft = data.get("owner_draft")
    latest_version_name = versions_list[-1].get("name") if versions_list else "Initial"
    if is_owner and isinstance(owner_draft, dict) and owner_draft.get("sentences"):
        data["has_unpublished_draft"] = True
        if data.get("current_version_name") == latest_version_name:
            data["sentences"] = copy.deepcopy(owner_draft["sentences"])

    return data


def _with_session_access_flags(
    session: Dict[str, Any],
    session_path: Optional[Path],
    user: Dict[str, Any],
) -> Dict[str, Any]:
    data = _session_for_user_view(session, user)
    session_id = str(data.get("session_id") or "").strip()
    data["root_session_id"] = session_id
    data["is_copy"] = False
    data["can_edit"] = _can_edit_session_directly(session, session_path, user)
    data["can_suggest"] = _can_suggest_session(session, session_path, user)
    data["can_approve"] = _can_approve_session(session, session_path, user)
    data["is_owner"] = _is_session_owner(session, session_path, user)
    return data


def _delete_sessions(session_ids: list[str]) -> int:
    normalized_ids = sorted({str(session_id).strip() for session_id in session_ids if str(session_id).strip()})
    if not normalized_ids:
        return 0

    if use_database_storage():
        return delete_sessions_db(normalized_ids)

    deleted = 0
    for sid in normalized_ids:
        json_path = _find_existing_session_path(sid)
        if json_path and json_path.exists():
            json_path.unlink()
            deleted += 1
    return deleted


def _sentence_groups_to_draft_sentences(sentence_groups: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Convert parser sentence groups into a saved draft sentence list."""
    sentences: list[Dict[str, Any]] = []
    sentence_id = 1

    for group in sentence_groups:
        versions = group.get("versions") or []
        selected_version_id = str(group.get("selected_version_id") or "").strip()

        selected_version = next(
            (v for v in versions if str(v.get("version_id") or "").strip() == selected_version_id),
            None,
        )
        if not selected_version and versions:
            selected_version = versions[0]

        raw_triples = selected_version.get("triples", []) if isinstance(selected_version, dict) else []
        triples: list[Dict[str, Any]] = []

        for idx, triple in enumerate(raw_triples, start=1):
            subject = str(triple.get("subject") or "").strip()
            predicate = str(triple.get("predicate") or "").strip()
            obj = str(triple.get("object") or "").strip()
            if not (subject and predicate and obj):
                continue

            triple_id = str(triple.get("id") or f"{sentence_id}_{idx}")
            triples.append({
                "id": triple_id,
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "grade": None,
                "is_placeholder": bool(triple.get("is_placeholder", False)),
                "note": str(triple.get("note") or ""),
            })

        if not triples:
            triples.append({
                "id": f"{sentence_id}_1",
                "subject": "[No Triples]",
                "predicate": "[None]",
                "object": "[None]",
                "grade": None,
                "is_placeholder": True,
                "note": "No triples provided in source file. Please use 'Suggest New Triple' to add annotations.",
            })

        sentence_text = str(group.get("sentence_text") or "").strip()
        if not sentence_text and isinstance(selected_version, dict):
            sentence_text = str(selected_version.get("sentence_candidate") or "").strip()

        sentences.append({
            "id": sentence_id,
            "text": sentence_text or "(no sentence text)",
            "suggestion": "",
            "sentence_comments": [],
            "comment_count": 0,
            "sentence_grade": None,
            "completeness": None,
            "external_relation": None,
            "triples": triples,
        })
        sentence_id += 1

    return sentences


def _merge_suggestions_lists(incoming_sugs: list, existing_sugs: list) -> list:
    merged_sugs = {}
    
    # Pre-populate with existing suggestions
    for sug in existing_sugs or []:
        sug_id = str(sug.get("id") or "").strip()
        if sug_id:
            merged_sugs[sug_id] = json.loads(json.dumps(sug))
            
    # Merge incoming suggestions
    for sug in incoming_sugs or []:
        sug_id = str(sug.get("id") or "").strip()
        if not sug_id:
            continue
            
        if sug_id in merged_sugs:
            existing_sug = merged_sugs[sug_id]
            existing_sug["subject"] = sug.get("subject", existing_sug.get("subject"))
            existing_sug["predicate"] = sug.get("predicate", existing_sug.get("predicate"))
            existing_sug["object"] = sug.get("object", existing_sug.get("object"))
            existing_sug["reason"] = sug.get("reason", existing_sug.get("reason"))
            existing_sug["status"] = sug.get("status", existing_sug.get("status"))
            
            incoming_votes = sug.get("votes") or {}
            existing_votes = existing_sug.get("votes") or {}
            merged_votes = dict(existing_votes)
            for user_key, vote_val in incoming_votes.items():
                merged_votes[user_key] = vote_val
            existing_sug["votes"] = merged_votes
            
            incoming_replies = sug.get("replies") or []
            existing_replies = existing_sug.get("replies") or []
            merged_replies = {str(r.get("id")): r for r in existing_replies if r.get("id")}
            for r in incoming_replies:
                rid = str(r.get("id") or "").strip()
                if rid:
                    merged_replies[rid] = r
            existing_sug["replies"] = sorted(merged_replies.values(), key=lambda x: str(x.get("created_at") or ""))
        else:
            merged_sugs[sug_id] = json.loads(json.dumps(sug))
            
    return sorted(merged_sugs.values(), key=lambda x: str(x.get("created_at") or ""))


def _merge_existing_suggestions(incoming_session: Dict[str, Any], existing_session: Dict[str, Any]) -> None:
    """Keep suggestions persisted via suggestion endpoints when owner performs a full save."""
    if "versions" not in incoming_session:
        incoming_session["versions"] = [
            {
                "name": "Initial",
                "created_at": incoming_session.get("uploaded_at") or datetime.utcnow().isoformat(),
                "created_by": incoming_session.get("owner_user_id") or "",
                "sentences": incoming_session.get("sentences") or []
            }
        ]
        incoming_session["last_version_name"] = "Initial"
        incoming_session["current_version_name"] = "Initial"

    if "versions" not in existing_session:
        existing_session["versions"] = [
            {
                "name": "Initial",
                "created_at": existing_session.get("uploaded_at") or datetime.utcnow().isoformat(),
                "created_by": existing_session.get("owner_user_id") or "",
                "sentences": existing_session.get("sentences") or []
            }
        ]
        existing_session["last_version_name"] = "Initial"
        existing_session["current_version_name"] = "Initial"

    existing_versions = {
        v.get("name"): v
        for v in existing_session.get("versions", [])
        if v.get("name")
    }

    for version in incoming_session.get("versions", []):
        version_name = version.get("name")
        existing_version = existing_versions.get(version_name)
        if not existing_version:
            continue

        existing_sentences = {
            s.get("id"): s
            for s in existing_version.get("sentences", [])
            if s.get("id") is not None
        }

        for sentence in version.get("sentences", []):
            sentence_id = sentence.get("id")
            existing_sentence = existing_sentences.get(sentence_id)
            if not existing_sentence:
                continue

            existing_triples = {
                t.get("id"): t
                for t in existing_sentence.get("triples", [])
                if t.get("id") is not None
            }

            for triple in sentence.get("triples", []):
                triple_id = triple.get("id")
                existing_triple = existing_triples.get(triple_id)
                if not existing_triple:
                    continue

                triple["suggestions"] = _merge_suggestions_lists(
                    triple.get("suggestions") or [],
                    existing_triple.get("suggestions") or []
                )


def _merge_existing_sentence_comments(incoming_session: Dict[str, Any], existing_session: Dict[str, Any]) -> None:
    """Preserve and merge sentence comment threads across full-session saves."""
    if "versions" not in incoming_session:
        incoming_session["versions"] = [
            {
                "name": "Initial",
                "created_at": incoming_session.get("uploaded_at") or datetime.utcnow().isoformat(),
                "created_by": incoming_session.get("owner_user_id") or "",
                "sentences": incoming_session.get("sentences") or []
            }
        ]
        incoming_session["last_version_name"] = "Initial"
        incoming_session["current_version_name"] = "Initial"

    if "versions" not in existing_session:
        existing_session["versions"] = [
            {
                "name": "Initial",
                "created_at": existing_session.get("uploaded_at") or datetime.utcnow().isoformat(),
                "created_by": existing_session.get("owner_user_id") or "",
                "sentences": existing_session.get("sentences") or []
            }
        ]
        existing_session["last_version_name"] = "Initial"
        existing_session["current_version_name"] = "Initial"

    owner_fallback_user_id = str(existing_session.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(existing_session.get("owner_name") or "").strip()

    existing_versions = {
        v.get("name"): v
        for v in existing_session.get("versions", [])
        if v.get("name")
    }

    for version in incoming_session.get("versions", []):
        version_name = version.get("name")
        existing_version = existing_versions.get(version_name)

        existing_sentences = {
            s.get("id"): s
            for s in (existing_version or {}).get("sentences", [])
            if s.get("id") is not None
        }

        for sentence in version.get("sentences", []):
            sentence_id = sentence.get("id")
            existing_sentence = existing_sentences.get(sentence_id)

            incoming_comments = _normalize_sentence_comments(
                sentence.get("sentence_comments"),
                fallback_text=str(sentence.get("suggestion") or ""),
                fallback_author=owner_fallback_user_name,
                fallback_user_id=owner_fallback_user_id,
                fallback_created_at=sentence.get("comment_created_at"),
            )

            if not existing_sentence:
                sentence["sentence_comments"] = incoming_comments
                sentence["comment_count"] = len(incoming_comments)
                if incoming_comments:
                    sentence["suggestion"] = incoming_comments[-1].get("text", "")
                continue

            existing_comments = _normalize_sentence_comments(
                existing_sentence.get("sentence_comments"),
                fallback_text=str(existing_sentence.get("suggestion") or ""),
                fallback_author=owner_fallback_user_name,
                fallback_user_id=owner_fallback_user_id,
                fallback_created_at=existing_sentence.get("comment_created_at"),
            )

            merged_by_id: Dict[str, Dict[str, Any]] = {
                str(comment.get("id") or ""): comment
                for comment in existing_comments
                if str(comment.get("id") or "").strip()
            }

            for comment in incoming_comments:
                comment_id = str(comment.get("id") or "").strip()
                if not comment_id:
                    continue
                if comment_id in merged_by_id:
                    existing_r = merged_by_id[comment_id].get("replies") or []
                    incoming_r = comment.get("replies") or []
                    merged_replies_dict = {str(r.get("id")): r for r in existing_r}
                    for r in incoming_r:
                        merged_replies_dict[str(r.get("id"))] = r
                    comment["replies"] = sorted(merged_replies_dict.values(), key=lambda row: str(row.get("created_at") or ""))
                merged_by_id[comment_id] = comment

            merged_comments = sorted(
                merged_by_id.values(),
                key=lambda row: str(row.get("created_at") or ""),
            )
            sentence["sentence_comments"] = merged_comments
            sentence["comment_count"] = len(merged_comments)
            if merged_comments:
                sentence["suggestion"] = merged_comments[-1].get("text", "")




# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

init_database(users_json_path=USERS_FILE, tokens_json_path=TOKENS_FILE, sessions_root=SESSIONS_ROOT)
ensure_default_users()

@app.post("/api/auth/register")
async def register(body: RegisterRequest):
    email = norm_email(str(body.email))
    username = norm_username(body.username)

    if not is_valid_username(username):
        raise HTTPException(
            status_code=422,
            detail="Username must be 3-24 chars, start with a letter, and use only lowercase letters, numbers, or underscore.",
        )

    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="This username is already taken.")

    hashed = hash_password(body.password)
    users_data = load_users()

    user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "name": body.name.strip(),
        "email": email,
        "password_salt": hashed["salt"],
        "password_hash": hashed["hash"],
        "created_at": datetime.utcnow().isoformat(),
        "security_question": body.security_question.strip(),
        "security_answer": body.security_answer.strip().lower(),
    }

    users_data["users"].append(user)
    if use_database_storage():
        upsert_user_db(user)
    else:
        save_users(users_data)

    return {
        "ok": True,
        "message": "Account created successfully. Please log in.",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": display_name(user),
            "email": user["email"],
            "security_question": user["security_question"]
        },
    }


@app.post("/api/auth/login")
async def login(body: AuthRequest):
    user = find_user_for_login(body.login)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")

    if not verify_password(body.password, user["password_salt"], user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")

    token = issue_token(user["id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user.get("username") or "",
            "name": display_name(user),
            "email": user["email"],
            "security_question": user.get("security_question") or "",
        },
    }


@app.get("/api/auth/me")
async def me(user: Dict[str, Any] = Depends(current_user)):
    return {
        "id": user["id"],
        "username": user.get("username") or "",
        "name": display_name(user),
        "email": user["email"],
        "security_question": user.get("security_question") or "",
    }


@app.post("/api/auth/logout")
async def logout(creds: Optional[HTTPAuthorizationCredentials] = Depends(_AUTH_SCHEME)):
    if creds and creds.scheme.lower() == "bearer":
        revoke_token(creds.credentials)
    return {"ok": True}


@app.put("/api/auth/profile")
async def update_profile(body: UpdateProfileRequest, user: Dict[str, Any] = Depends(current_user)):
    users_data = load_users()
    users = users_data.get("users", [])
    
    target = None
    for u in users:
        if u.get("id") == user["id"]:
            target = u
            break
            
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if body.name is not None:
        name_val = body.name.strip()
        if len(name_val) < 2 or len(name_val) > 80:
            raise HTTPException(status_code=422, detail="Name must be between 2 and 80 characters.")
        target["name"] = name_val
        
    if body.username is not None:
        username_val = norm_username(body.username)
        if username_val != norm_username(target.get("username", "")):
            if not is_valid_username(username_val):
                raise HTTPException(
                    status_code=422,
                    detail="Username must be 3-24 chars, start with a letter, and use lowercase letters, numbers, or underscore.",
                )
            if get_user_by_username(username_val):
                raise HTTPException(status_code=409, detail="This username is already taken.")
            target["username"] = username_val
            
    if body.email is not None:
        email_val = norm_email(body.email)
        if email_val != norm_email(target.get("email", "")):
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email_val):
                raise HTTPException(status_code=422, detail="Invalid email format.")
            if get_user_by_email(email_val):
                raise HTTPException(status_code=409, detail="An account with this email already exists.")
            target["email"] = email_val
            
    if body.password is not None:
        pass_val = body.password
        if len(pass_val) < 8 or len(pass_val) > 128:
            raise HTTPException(status_code=422, detail="Password must be between 8 and 128 characters.")
        
        # Enforce security question validation to change password
        if not body.security_answer:
            raise HTTPException(status_code=400, detail="Security answer is required to change password.")
            
        stored_answer = str(target.get("security_answer") or "").strip().lower()
        if body.security_answer.strip().lower() != stored_answer:
            raise HTTPException(status_code=400, detail="Incorrect answer to security question.")
            
        hashed = hash_password(pass_val)
        target["password_salt"] = hashed["salt"]
        target["password_hash"] = hashed["hash"]
        
    if body.security_question is not None:
        q_val = body.security_question.strip()
        if q_val:
            if len(q_val) < 5 or len(q_val) > 255:
                raise HTTPException(status_code=422, detail="Security question must be between 5 and 255 characters.")
            target["security_question"] = q_val
            
    if body.security_answer is not None:
        a_val = body.security_answer.strip().lower()
        if a_val:
            target["security_answer"] = a_val
            
    # Save updated user record
    if use_database_storage():
        upsert_user_db(target)
    else:
        save_users(users_data)
        
    return {
        "ok": True,
        "message": "Profile updated successfully.",
        "user": {
            "id": target["id"],
            "username": target.get("username") or "",
            "name": display_name(target),
            "email": target["email"],
            "security_question": target.get("security_question") or "",
        }
    }


@app.post("/api/auth/forgot-password/question")
async def forgot_password_question(body: GetSecurityQuestionRequest):
    user = find_user_for_login(body.login)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")
        
    question = user.get("security_question")
    if not question:
        raise HTTPException(
            status_code=400,
            detail="This account does not have a security question set. Please contact an administrator."
        )
        
    return {
        "ok": True,
        "login": body.login,
        "security_question": question
    }


@app.post("/api/auth/forgot-password/reset")
async def forgot_password_reset(body: ResetPasswordWithQuestionRequest):
    user = find_user_for_login(body.login)
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")
        
    stored_answer = str(user.get("security_answer") or "").strip().lower()
    if not stored_answer:
        raise HTTPException(
            status_code=400,
            detail="This account does not have a security question set."
        )
        
    user_answer = body.answer.strip().lower()
    if user_answer != stored_answer:
        raise HTTPException(status_code=400, detail="Incorrect answer to security question.")
        
    new_password = body.password
    if len(new_password) < 8 or len(new_password) > 128:
        raise HTTPException(status_code=422, detail="Password must be between 8 and 128 characters.")
        
    hashed = hash_password(new_password)
    
    # Update user password in user data list
    users_data = load_users()
    users = users_data.get("users", [])
    
    target = None
    for u in users:
        if u.get("id") == user["id"]:
            target = u
            break
            
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
        
    target["password_salt"] = hashed["salt"]
    target["password_hash"] = hashed["hash"]
    
    if use_database_storage():
        upsert_user_db(target)
    else:
        save_users(users_data)
        
    return {
        "ok": True,
        "message": "Password reset successfully. You can now log in."
    }


@app.post("/api/auth/delete-account")
async def delete_account(body: DeleteAccountRequest, user: Dict[str, Any] = Depends(current_user)):
    user_id = user["id"]
    users_data = load_users()
    users = users_data.get("users", [])
    
    target = None
    for u in users:
        if u.get("id") == user_id:
            target = u
            break
            
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
        
    # Verify password
    if not verify_password(body.password, target["password_salt"], target["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect password.")
        
    # Verify security answer
    stored_answer = str(target.get("security_answer") or "").strip().lower()
    if body.security_answer.strip().lower() != stored_answer:
        raise HTTPException(status_code=400, detail="Incorrect answer to security question.")
        
    # Delete all user sessions, tokens, and records
    if use_database_storage():
        from database import SessionRecord, TokenRecord, UserRecord, SessionLocal
        with SessionLocal() as db:
            # Delete sessions owned by user
            db.query(SessionRecord).filter(SessionRecord.owner_user_id == user_id).delete(synchronize_session=False)
            # Delete tokens belonging to user
            db.query(TokenRecord).filter(TokenRecord.user_id == user_id).delete(synchronize_session=False)
            # Delete user record
            db.query(UserRecord).filter(UserRecord.id == user_id).delete(synchronize_session=False)
            db.commit()
    else:
        # Delete session files
        import shutil
        user_sessions_dir = SESSIONS_ROOT / user_id
        if user_sessions_dir.exists():
            shutil.rmtree(user_sessions_dir, ignore_errors=True)
            
        # Revoke user tokens
        tokens_data = load_tokens()
        tokens = tokens_data.get("tokens", {})
        tokens_to_keep = {
            t: data for t, data in tokens.items() if data.get("user_id") != user_id
        }
        tokens_data["tokens"] = tokens_to_keep
        save_tokens(tokens_data)
        
        # Delete user record from users list
        users_data["users"] = [u for u in users if u.get("id") != user_id]
        save_users(users_data)
        
    return {
        "ok": True,
        "message": "Account and all associated grading sessions have been deleted successfully."
    }

def _json_to_sentence_groups(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Convert a downloaded session JSON into sentence_groups for review."""
    if isinstance(payload.get("sentence_groups"), list):
        sentence_groups = payload["sentence_groups"]
        if not sentence_groups:
            raise ValueError("Uploaded JSON contains an empty 'sentence_groups' list.")
        return _validate_sentence_groups(sentence_groups)

    sentences = payload.get("sentences")
    if not isinstance(sentences, list):
        raise ValueError("JSON upload must contain either 'sentence_groups' or exported 'sentences'.")

    if not sentences:
        raise ValueError("Uploaded JSON contains no sentences.")

    groups: list[Dict[str, Any]] = []
    for idx, sentence in enumerate(sentences, start=1):
        if not isinstance(sentence, dict):
            raise ValueError(f"Sentence #{idx} must be an object.")

        sentence_text = str(
            sentence.get("text")
            or sentence.get("sentence_text")
            or sentence.get("sentence")
            or sentence.get("sentence_candidate")
            or ""
        ).strip()
        if not sentence_text:
            raise ValueError(f"Sentence #{idx} is missing required sentence text.")

        triples = sentence.get("triples")
        if not isinstance(triples, list):
            triples = []

        version_triples = []
        if not triples:
            version_triples.append({
                "id": f"{idx}_1_1",
                "subject": "[No Triples]",
                "predicate": "[None]",
                "object": "[None]",
                "is_placeholder": True,
                "note": "No triples provided in source file. Please use 'Suggest New Triple' to add annotations.",
            })
        else:
            for ti, triple in enumerate(triples, start=1):
                if not isinstance(triple, dict):
                    raise ValueError(f"Sentence #{idx}, triple #{ti} must be an object.")

                subject = str(triple.get("subject") or "").strip()
                predicate = str(triple.get("predicate") or "").strip()
                obj = str(triple.get("object") or "").strip()
                if not subject or not predicate or not obj:
                    raise ValueError(
                        f"Sentence #{idx}, triple #{ti} must include non-empty subject, predicate, and object."
                    )

                version_triples.append({
                    "id": str(triple.get("id") or f"{idx}_1_{ti}"),
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "is_placeholder": bool(triple.get("is_placeholder", False)),
                    "note": str(triple.get("note") or ""),
                })

        groups.append({
            "group_id": idx,
            "sentence_text": sentence_text,
            "selected_version_id": f"{idx}_1",
            "versions": [
                {
                    "version_id": f"{idx}_1",
                    "version_label": "Imported",
                    "sentence_candidate": sentence_text,
                    "triples": version_triples,
                }
            ],
        })

    return groups


def _validate_sentence_groups(sentence_groups: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    if not isinstance(sentence_groups, list):
        raise ValueError("'sentence_groups' must be a list.")

    for gi, group in enumerate(sentence_groups, start=1):
        if not isinstance(group, dict):
            raise ValueError(f"Sentence group #{gi} must be an object.")

        sentence_text = str(
            group.get("sentence_text")
            or group.get("text")
            or group.get("sentence")
            or ""
        ).strip()
        if not sentence_text:
            raise ValueError(f"Sentence group #{gi} is missing required sentence text.")

        versions = group.get("versions")
        if not isinstance(versions, list) or not versions:
            raise ValueError(f"Sentence group #{gi} must contain at least one version.")

        for vi, version in enumerate(versions, start=1):
            if not isinstance(version, dict):
                raise ValueError(f"Sentence group #{gi}, version #{vi} must be an object.")

            triples = version.get("triples")
            if not isinstance(triples, list):
                triples = []

            if not triples:
                version["triples"] = [{
                    "id": f"{gi}_{vi}_1",
                    "subject": "[No Triples]",
                    "predicate": "[None]",
                    "object": "[None]",
                    "is_placeholder": True,
                    "note": "No triples provided in source file. Please use 'Suggest New Triple' to add annotations.",
                }]
            else:
                for ti, triple in enumerate(triples, start=1):
                    if not isinstance(triple, dict):
                        raise ValueError(
                            f"Sentence group #{gi}, version #{vi}, triple #{ti} must be an object."
                        )
                    subject = str(triple.get("subject") or "").strip()
                    predicate = str(triple.get("predicate") or "").strip()
                    obj = str(triple.get("object") or "").strip()
                    if not subject or not predicate or not obj:
                        raise ValueError(
                            f"Sentence group #{gi}, version #{vi}, triple #{ti} must include non-empty subject, predicate, and object."
                        )

    return sentence_groups


def _parse_uploaded_json(file_bytes: bytes) -> list[Dict[str, Any]]:
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception:
        try:
            payload = json.loads(file_bytes.decode("latin-1"))
        except Exception as exc:
            raise ValueError(f"Invalid JSON upload: {str(exc)}")

    if isinstance(payload, list) and len(payload) > 0:
        first_item = payload[0]
        is_flat_triples = isinstance(first_item, dict) and "subject" in first_item and "predicate" in first_item and "object" in first_item
        
        if is_flat_triples:
            grouped_sentences = []
            sentence_index = {}
            for idx, item in enumerate(payload):
                if not isinstance(item, dict):
                    continue
                s_text = str(
                    item.get("sentence")
                    or item.get("text")
                    or item.get("sentence_text")
                    or item.get("sentence_candidate")
                    or ""
                ).strip()
                if not s_text:
                    s_text = f"Untitled Sentence {idx+1}"
                
                triple_obj = {
                    "id": str(item.get("id") or f"tpl-{idx}"),
                    "subject": str(item.get("subject") or "").strip(),
                    "predicate": str(item.get("predicate") or "").strip(),
                    "object": str(item.get("object") or "").strip(),
                }
                
                if s_text in sentence_index:
                    target_idx = sentence_index[s_text]
                    grouped_sentences[target_idx]["triples"].append(triple_obj)
                else:
                    new_sent = {
                        "text": s_text,
                        "triples": [triple_obj]
                    }
                    sentence_index[s_text] = len(grouped_sentences)
                    grouped_sentences.append(new_sent)
            payload = {"sentences": grouped_sentences}
        else:
            is_group = isinstance(first_item, dict) and "versions" in first_item
            if is_group:
                payload = {"sentence_groups": payload}
            else:
                payload = {"sentences": payload}

    if not isinstance(payload, dict):
        raise ValueError("Uploaded JSON must be an object at the top level.")

    return _json_to_sentence_groups(payload)


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user: Dict[str, Any] = Depends(current_user)):
    """Parse an uploaded file, save an owner draft, and return sentence-group data for review."""
    allowed_extensions = {".csv", ".xlsx", ".xls", ".json"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    file_bytes = await file.read()

    try:
        if suffix == ".json":
            sentence_groups = _parse_uploaded_json(file_bytes)
        else:
            sentence_groups = parse_file_rich(file_bytes, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
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
    uploaded_at = datetime.utcnow().isoformat()

    draft_session = {
        "session_id": session_id,
        "source_filename": file.filename,
        "uploaded_at": uploaded_at,
        "sentences": _sentence_groups_to_draft_sentences(sentence_groups),
        "manual_mode": False,
        "owner_user_id": user.get("id", ""),
        "owner_name": display_name(user),
        "owner_email": norm_email(user.get("email", "")),
        "owner_username": norm_username(user.get("username", "")),
        "root_session_id": session_id,
        "is_copy": False,
    }
    _save_loaded_session(None, draft_session, owner_user_id=user.get("id", ""))

    return {
        "session_id":       session_id,
        "source_filename":  file.filename,
        "uploaded_at":      uploaded_at,
        "total_groups":     len(sentence_groups),
        "sentence_groups":  sentence_groups,
        "draft_saved":      True,
    }


def _publish_new_version(
    session: Dict[str, Any],
    new_version_name: str,
    incoming_sentences: list,
    user: Dict[str, Any]
) -> Dict[str, Any]:
    user_id = str(user.get("id") or "").strip()
    user_display = display_name(user)
    now_iso = datetime.utcnow().isoformat()

    # Get the previous published version to compare against for diffs and grade resets
    versions = session.get("versions") or []
    prev_version = versions[-1] if versions else None
    prev_sentences = prev_version.get("sentences", []) if prev_version else []


    # Map previous triples by ID
    prev_triple_map: Dict[str, Dict[str, Any]] = {}
    for s in prev_sentences:
        for t in s.get("triples", []):
            tid = str(t.get("id") or "").strip()
            if tid:
                prev_triple_map[tid] = t

    published_sentences = []
    for s in incoming_sentences:
        sentence_copy = dict(s)
        sentence_copy["sentence_comments"] = []
        sentence_copy["comment_count"] = 0
        sentence_copy["suggestion"] = ""
        new_triples = []
        for t in s.get("triples", []):
            t_copy = dict(t)
            # Clear previous version's resolved comments, suggestions, and removal requests in new version
            t_copy["triple_comments"] = []
            t_copy["suggestions"] = []
            t_copy["marked_for_removal"] = False
            t_copy["removal_reason"] = ""
            t_copy["marked_for_removal_by"] = None
            t_copy["marked_for_removal_by_name"] = None

            tid = str(t.get("id") or "").strip()
            prev_t = prev_triple_map.get(tid)

            if not prev_t:
                # NEW TRIPLE in this published version: reset grades & mark new
                t_copy["is_new_in_version"] = True
                t_copy["is_modified_in_version"] = False
                t_copy["diff_hint"] = ["Newly added in this version"]
                t_copy["grade"] = None
                t_copy["author"] = None
                t_copy["grades_by_user"] = {}
                t_copy["graded_at"] = None
            else:
                prev_sub = str(prev_t.get("subject") or "").strip()
                prev_pred = str(prev_t.get("predicate") or "").strip()
                prev_obj = str(prev_t.get("object") or "").strip()

                curr_sub = str(t.get("subject") or "").strip()
                curr_pred = str(t.get("predicate") or "").strip()
                curr_obj = str(t.get("object") or "").strip()

                sub_changed = (curr_sub != prev_sub)
                pred_changed = (curr_pred != prev_pred)
                obj_changed = (curr_obj != prev_obj)

                if sub_changed or pred_changed or obj_changed:
                    hints = []
                    if sub_changed:
                        hints.append(f"Subject changed from '{prev_sub}' to '{curr_sub}'")
                    if pred_changed:
                        hints.append(f"Predicate changed from '{prev_pred}' to '{curr_pred}'")
                    if obj_changed:
                        hints.append(f"Object changed from '{prev_obj}' to '{curr_obj}'")

                    t_copy["is_modified_in_version"] = True
                    t_copy["is_new_in_version"] = False
                    t_copy["diff_hint"] = hints
                    # MODIFIED TRIPLE: reset grades so graders can grade the modified triple
                    t_copy["grade"] = None
                    t_copy["author"] = None
                    t_copy["grades_by_user"] = {}
                    t_copy["graded_at"] = None
                else:
                    # UNMODIFIED TRIPLE: preserve previous grades intact
                    t_copy["is_modified_in_version"] = False
                    t_copy["is_new_in_version"] = False
                    t_copy.pop("diff_hint", None)
                    t_copy["grade"] = prev_t.get("grade")
                    t_copy["author"] = prev_t.get("author")
                    t_copy["grades_by_user"] = prev_t.get("grades_by_user") or {}
                    t_copy["graded_at"] = prev_t.get("graded_at")

            new_triples.append(t_copy)
        sentence_copy["triples"] = new_triples
        published_sentences.append(sentence_copy)

    new_version_obj = {
        "name": new_version_name,
        "created_at": now_iso,
        "created_by": user_display,
        "sentences": copy.deepcopy(published_sentences),
        "is_published": True,
    }

    if "versions" not in session or not isinstance(session["versions"], list):
        session["versions"] = []

    existing_idx = next((i for i, v in enumerate(session["versions"]) if v.get("name") == new_version_name), None)
    if existing_idx is not None:
        session["versions"][existing_idx] = new_version_obj
    else:
        session["versions"].append(new_version_obj)

    session["current_version_name"] = new_version_name
    session["last_version_name"] = new_version_name
    session["sentences"] = published_sentences
    session["owner_draft"] = None  # Clear owner draft after successful publish

    # Push notification for all users
    if "notifications" not in session or not isinstance(session["notifications"], list):
        session["notifications"] = []

    session["notifications"].append({
        "id": f"notif-pub-{uuid.uuid4()}",
        "type": "version_published",
        "version_name": new_version_name,
        "published_by": user_display,
        "created_at": now_iso,
        "message": f"Owner {user_display} published a new version: '{new_version_name}'",
        "read_by": [user_id],
    })

    return session


def _sync_collaborative_elements(target_sentences: list, source_sentences: list) -> None:
    source_sentence_map = {s.get("id"): s for s in source_sentences if s.get("id") is not None}
    
    for target_sent in target_sentences:
        sid = target_sent.get("id")
        source_sent = source_sentence_map.get(sid)
        if not source_sent:
            continue
            
        for key in (
            "sentence_comments",
            "completeness_by_user",
            "external_relation_by_user",
            "completeness",
            "external_relation",
            "completeness_updated_at",
            "external_relation_updated_at",
            "comment_count",
            "completeness_count",
            "completeness_average",
            "external_relation_count",
            "external_relation_average",
        ):
            if key in source_sent:
                target_sent[key] = json.loads(json.dumps(source_sent[key]))
                
        source_triple_map = {t.get("id"): t for t in source_sent.get("triples", []) if t.get("id") is not None}
        
        for target_triple in target_sent.get("triples", []):
            tid = target_triple.get("id")
            source_triple = source_triple_map.get(tid)
            if not source_triple:
                continue
                
            for key in (
                "triple_comments",
                "grades_by_user",
                "grade",
                "author",
                "graded_at",
                "is_new_suggestion",
                "status",
                "suggested_by",
                "suggested_by_id",
                "approved_by",
                "approved_at",
                "marked_for_removal",
                "marked_for_removal_by",
                "marked_for_removal_by_name",
                "removal_reason",
                "suggestions",
            ):
                if key in source_triple:
                    target_triple[key] = json.loads(json.dumps(source_triple[key]))


def _has_owner_manual_modifications(incoming_sentences: list, existing_sentences: list) -> bool:
    existing_triples = {}
    for s in existing_sentences:
        for t in s.get("triples", []):
            tid = str(t.get("id") or "").strip()
            if tid:
                existing_triples[tid] = t

    incoming_triples = {}
    for s in incoming_sentences:
        for t in s.get("triples", []):
            tid = str(t.get("id") or "").strip()
            if tid:
                incoming_triples[tid] = t

    for tid, incoming_t in incoming_triples.items():
        existing_t = existing_triples.get(tid)
        if not existing_t:
            # Manual addition by owner
            if not incoming_t.get("is_new_suggestion", False):
                return True
        else:
            # Existing triple text change manually by owner
            text_changed = (
                incoming_t.get("subject") != existing_t.get("subject")
                or incoming_t.get("predicate") != existing_t.get("predicate")
                or incoming_t.get("object") != existing_t.get("object")
            )
            if text_changed:
                has_approved_sug = False
                for sug in existing_t.get("suggestions", []):
                    if (
                        sug.get("subject") == incoming_t.get("subject")
                        and sug.get("predicate") == incoming_t.get("predicate")
                        and sug.get("object") == incoming_t.get("object")
                    ):
                        has_approved_sug = True
                        break
                if not has_approved_sug:
                    return True

    for tid, existing_t in existing_triples.items():
        if tid not in incoming_triples:
            # Manual deletion by owner (ignore marked for removal, corrected triples, or suggestions)
            if not existing_t.get("marked_for_removal", False) and not existing_t.get("is_corrected", False) and not existing_t.get("is_new_suggestion", False):
                return True

    return False


@app.post("/api/save")
async def save_session(body: SaveRequest, user: Dict[str, Any] = Depends(current_user)):
    """Persist a graded session or publish a new version to storage."""
    session_data = body.model_dump()

    existing_path, existing_session = _load_existing_session(body.session_id)
    target_session = existing_session or session_data

    # Ensure versions list exists
    if "versions" not in target_session or not target_session["versions"]:
        target_session["versions"] = [{
            "name": "Initial",
            "created_at": target_session.get("uploaded_at") or datetime.utcnow().isoformat(),
            "created_by": target_session.get("owner_name") or display_name(user),
            "sentences": target_session.get("sentences") or [],
        }]
        target_session["current_version_name"] = "Initial"
        target_session["last_version_name"] = "Initial"

    # Ensure owner metadata exists on new or target session
    if not target_session.get("owner_user_id"):
        target_session["owner_user_id"] = str(user.get("id") or "").strip()
        target_session["owner_name"] = display_name(user)
        target_session["owner_email"] = user.get("email")
        target_session["owner_username"] = user.get("username")

    is_owner = _is_session_owner(target_session, existing_path, user)
    is_publish = bool(body.is_publish)

    if is_publish and is_owner:
        pub_version_name = getattr(body, "version_name", None) or getattr(body, "current_version_name", None) or f"Version {len(target_session.get('versions', [])) + 1}"
        target_session = _publish_new_version(
            session=target_session,
            new_version_name=pub_version_name,
            incoming_sentences=body.sentences or target_session.get("sentences") or [],
            user=user
        )
    elif is_owner:
        # Check if the owner has manual CRUD/modifications
        existing_sentences = existing_session.get("sentences", []) if existing_session else []
        if _has_owner_manual_modifications(body.sentences or [], existing_sentences):
            # Save to owner_draft as a working draft (requires publish)
            if body.sentences:
                # Sync latest collaborative elements from active version into the incoming draft
                _sync_collaborative_elements(body.sentences, existing_sentences)
                target_session["owner_draft"] = {
                    "updated_at": datetime.utcnow().isoformat(),
                    "sentences": body.sentences,
                }
                target_session["sentences"] = body.sentences
                curr_ver_name = target_session.get("current_version_name") or "Initial"
                for v in target_session.get("versions") or []:
                    if v.get("name") == curr_ver_name and not v.get("is_published"):
                        v["sentences"] = copy.deepcopy(body.sentences)
                        break
            if body.current_version_name:
                target_session["current_version_name"] = body.current_version_name
        else:
            # No manual modifications (only suggestion/deletion approvals, comments, or grades).
            # Save directly to the active version's sentences
            if body.sentences:
                target_session["sentences"] = body.sentences
                # Also update the active version inside versions list if it's not a published milestone
                curr_ver_name = target_session.get("current_version_name") or "Initial"
                for v in target_session.get("versions") or []:
                    if v.get("name") == curr_ver_name and not v.get("is_published"):
                        v["sentences"] = copy.deepcopy(body.sentences)
                        break
            
            # Clear owner draft since the decisions are now direct changes on the active version
            target_session["owner_draft"] = None
            if body.current_version_name:
                target_session["current_version_name"] = body.current_version_name
    else:
        # Non-owner grader save: merge grades into active version
        if existing_session:
            # Sync existing versions list to incoming session so they are preserved
            session_data["versions"] = json.loads(json.dumps(existing_session.get("versions") or []))
            curr_ver_name = existing_session.get("current_version_name") or "Initial"
            session_data["current_version_name"] = curr_ver_name

            # Place incoming client sentences into the active version of the versions list
            for v in session_data.get("versions") or []:
                if v.get("name") == curr_ver_name:
                    v["sentences"] = session_data.get("sentences") or []
                    break

            try:
                _merge_existing_suggestions(session_data, existing_session)
            except Exception:
                pass
            try:
                _merge_existing_sentence_comments(session_data, existing_session)
            except Exception:
                pass

        _apply_collaborative_grades(session_data, existing_session, user)

        # Sync the fully merged sentences into the active version in session_data["versions"]
        curr_ver_name = session_data.get("current_version_name") or "Initial"
        for v in session_data.get("versions") or []:
            if v.get("name") == curr_ver_name:
                v["sentences"] = session_data.get("sentences") or []
                break

        # Save fully merged version back to the target_session
        target_session["sentences"] = session_data.get("sentences") or []
        target_session["versions"] = session_data.get("versions") or []

        # Sync collaborative updates into owner_draft sentences to keep it aligned
        if target_session.get("owner_draft") and isinstance(target_session["owner_draft"], dict) and target_session["owner_draft"].get("sentences"):
            _sync_collaborative_elements(target_session["owner_draft"]["sentences"], target_session["sentences"])

    # Recalculate stats & normalize metadata for all versions
    owner_user_id = str(target_session.get("owner_user_id") or user.get("id", "")).strip()
    target_session["root_session_id"] = body.session_id
    target_session["is_copy"] = False

    _save_loaded_session(existing_path, target_session, owner_user_id=owner_user_id)

    # Broadcast real-time update
    await manager.broadcast(body.session_id, {
        "type": "version_published" if is_publish else "session_updated",
        "version_name": target_session.get("current_version_name"),
    })

    stats = _session_grading_stats(target_session)
    return {
        "session_id": body.session_id,
        "saved_at": datetime.utcnow().isoformat(),
        "total_unique_graders": stats["total_unique_graders"],
        "grader_summary": stats["grader_summary"],
        "is_publish": is_publish,
    }


def _avg_or_none(values: list[float]) -> Optional[float]:
    return round(sum(values) / len(values), 2) if values else None


def _preview_grader_options(session_data: Dict[str, Any]) -> list[Dict[str, Any]]:
    stats = _session_grading_stats(session_data)
    options: list[Dict[str, Any]] = []
    for row in stats.get("grader_summary", []):
        user_id = str(row.get("user_id") or "").strip()
        if not user_id:
            continue
        options.append({
            "user_id": user_id,
            "user_name": str(row.get("user_name") or user_id),
            "graded_triples": int(row.get("graded_triples") or 0),
        })
    return options


def _resolve_preview_selection(
    requested_mode: str,
    requested_user_id: Optional[str],
    current_user_id: str,
    grader_options: list[Dict[str, Any]],
) -> tuple[str, str, str]:
    mode = str(requested_mode or "combined").strip().lower()
    if mode == "mine":
        mode = "user"
        requested_user_id = current_user_id
    if mode not in {"combined", "user"}:
        mode = "combined"

    valid_ids = [str(item.get("user_id") or "").strip() for item in grader_options if str(item.get("user_id") or "").strip()]
    selected_user_id = str(requested_user_id or "").strip()

    if mode == "user":
        if selected_user_id not in valid_ids:
            if current_user_id in valid_ids:
                selected_user_id = current_user_id
            elif valid_ids:
                selected_user_id = valid_ids[0]
            else:
                mode = "combined"
                selected_user_id = ""

    if mode == "combined":
        return "combined", "", "Combined grading"

    selected_name = next(
        (str(item.get("user_name") or selected_user_id) for item in grader_options if str(item.get("user_id") or "").strip() == selected_user_id),
        selected_user_id,
    )
    return "user", selected_user_id, selected_name


def _project_session_for_view(
    session_data: Dict[str, Any],
    view_mode: str,
    view_user_id: str = "",
) -> Dict[str, Any]:
    data = json.loads(json.dumps(session_data, ensure_ascii=False))

    owner_fallback_user_id = str(data.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(data.get("owner_name") or "").strip()

    overall_triple_grades: list[float] = []
    total_triples = 0
    graded_triples = 0

    for sentence in data.get("sentences", []):
        sentence_user_grades: Dict[str, list[float]] = {}

        completeness_by_user = _normalize_sentence_metric_by_user(
            sentence.get("completeness_by_user"),
            fallback_value=sentence.get("completeness"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("completeness_updated_at"),
        )
        external_relation_by_user = _normalize_sentence_metric_by_user(
            sentence.get("external_relation_by_user"),
            fallback_value=sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("external_relation_updated_at"),
        )

        sentence["completeness_by_user"] = completeness_by_user
        sentence["external_relation_by_user"] = external_relation_by_user

        filtered_triples = []
        for triple in sentence.get("triples", []):
            if triple.get("is_new_suggestion") and triple.get("status") != "approved":
                continue
            filtered_triples.append(triple)
            total_triples += 1

            grades_by_user = _normalize_grades_by_user(
                triple.get("grades_by_user"),
                fallback_grade=triple.get("grade"),
                fallback_author=str(triple.get("author") or ""),
                fallback_user_id=owner_fallback_user_id,
                fallback_graded_at=triple.get("graded_at"),
            )
            triple["grades_by_user"] = grades_by_user

            for grader_id, payload in grades_by_user.items():
                grade_value = _normalize_grade_value(payload.get("grade"))
                if grade_value is None:
                    continue
                sentence_user_grades.setdefault(grader_id, []).append(float(grade_value))

            if view_mode == "user" and view_user_id:
                selected_payload = grades_by_user.get(view_user_id)
                selected_grade = (
                    _normalize_grade_value(selected_payload.get("grade"))
                    if isinstance(selected_payload, dict)
                    else None
                )
                triple["grade"] = selected_grade
                triple["author"] = (
                    str(selected_payload.get("user_name") or view_user_id)
                    if isinstance(selected_payload, dict) and selected_grade is not None
                    else None
                )
                triple["grade_count"] = 1 if selected_grade is not None else 0
                triple["grade_average"] = selected_grade
            else:
                grade_values = [
                    float(grade_value)
                    for payload in grades_by_user.values()
                    for grade_value in [_normalize_grade_value(payload.get("grade"))]
                    if grade_value is not None
                ]
                combined_grade = _avg_or_none(grade_values)
                triple["grade"] = combined_grade
                triple["author"] = "Combined" if combined_grade is not None else None
                triple["grade_count"] = len(grade_values)
                triple["grade_average"] = combined_grade

            if triple.get("grade") is not None:
                graded_triples += 1
                overall_triple_grades.append(float(triple["grade"]))

        sentence["triples"] = filtered_triples

        if view_mode == "user" and view_user_id:
            selected_comp = completeness_by_user.get(view_user_id)
            selected_ext = external_relation_by_user.get(view_user_id)

            comp_value = (
                _normalize_sentence_metric_value(selected_comp.get("value"))
                if isinstance(selected_comp, dict)
                else None
            )
            ext_value = (
                _normalize_sentence_metric_value(selected_ext.get("value"))
                if isinstance(selected_ext, dict)
                else None
            )

            sentence["completeness"] = comp_value
            sentence["completeness_count"] = 1 if comp_value is not None else 0
            sentence["completeness_average"] = comp_value

            sentence["external_relation"] = ext_value
            sentence["external_relation_count"] = 1 if ext_value is not None else 0
            sentence["external_relation_average"] = ext_value

            sentence_grade_values = [float(v) for v in sentence_user_grades.get(view_user_id, [])]
            sentence["sentence_grade"] = _avg_or_none(sentence_grade_values)
        else:
            comp_values = [
                float(metric_value)
                for payload in completeness_by_user.values()
                for metric_value in [_normalize_sentence_metric_value(payload.get("value"))]
                if metric_value is not None
            ]
            ext_values = [
                float(metric_value)
                for payload in external_relation_by_user.values()
                for metric_value in [_normalize_sentence_metric_value(payload.get("value"))]
                if metric_value is not None
            ]

            sentence["completeness"] = _avg_or_none(comp_values)
            sentence["completeness_count"] = len(comp_values)
            sentence["completeness_average"] = _avg_or_none(comp_values)

            sentence["external_relation"] = _avg_or_none(ext_values)
            sentence["external_relation_count"] = len(ext_values)
            sentence["external_relation_average"] = _avg_or_none(ext_values)

            per_user_sentence_grades = [
                _avg_or_none(values)
                for values in sentence_user_grades.values()
                if values
            ]
            sentence["sentence_grade"] = _avg_or_none([
                float(v)
                for v in per_user_sentence_grades
                if v is not None
            ])

    data["session_average_grade"] = None
    data["is_completed_grading"] = total_triples > 0 and graded_triples == total_triples
    data["graded_triples"] = graded_triples
    data["total_triples"] = total_triples
    data["preview_view_mode"] = view_mode
    data["preview_view_user_id"] = view_user_id if view_mode == "user" and view_user_id else None
    return data


@app.get("/api/download/{session_id}/{fmt}")
async def download_session(
    session_id: str,
    fmt: str,
    request: Request,
    token: Optional[str] = Query(default=None),
    view_mode: str = Query(default="mine"),
    view_user_id: Optional[str] = Query(default=None),
    version_name: Optional[str] = Query(default=None),
):
    """Download a saved session in the requested format."""
    user = current_user_from_bearer_or_query(request, token)
    _, raw_session = _load_session_for_access(session_id)
    if version_name:
        raw_session["current_version_name"] = version_name
    base_session = _session_for_user_view(raw_session, user)

    grader_options = _preview_grader_options(base_session)
    selected_mode, selected_user_id, selected_label = _resolve_preview_selection(
        requested_mode=view_mode,
        requested_user_id=view_user_id,
        current_user_id=str(user.get("id") or "").strip(),
        grader_options=grader_options,
    )
    session = _project_session_for_view(base_session, selected_mode, selected_user_id)

    fmt = fmt.lower()
    filename_base = session.get("source_filename", "graded").rsplit(".", 1)[0]
    filename_suffix = "combined"
    if selected_mode == "user":
        safe_label = re.sub(r"[^a-z0-9_]+", "_", str(selected_label).lower()).strip("_") or "user"
        filename_suffix = safe_label

    if fmt == "json":
        data         = to_json(session)
        media_type   = "application/json"
        disposition  = f'attachment; filename="{filename_base}_{filename_suffix}_graded.json"'
    elif fmt == "csv":
        data         = to_csv(session)
        media_type   = "text/csv"
        disposition  = f'attachment; filename="{filename_base}_{filename_suffix}_graded.csv"'
    elif fmt in ("excel", "xlsx"):
        data         = to_excel(session)
        media_type   = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        disposition  = f'attachment; filename="{filename_base}_{filename_suffix}_graded.xlsx"'
    elif fmt in ("pdf",):
        data         = to_pdf(session)
        media_type   = "application/pdf"
        disposition  = f'attachment; filename="{filename_base}_{filename_suffix}_graded.pdf"'
    elif fmt in ("word", "docx"):
        data         = to_word(session)
        media_type   = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        disposition  = f'attachment; filename="{filename_base}_{filename_suffix}_graded.docx"'
    else:
        raise HTTPException(status_code=400, detail=f"Unknown format '{fmt}'. Use: json, csv, excel, pdf, word.")

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


@app.get("/api/session/{session_id}")
async def get_session(
    session_id: str,
    version_name: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(current_user)
):
    """Return the full saved session JSON (used by the frontend to resume a session)."""
    session_path, session = _load_session_for_access(session_id)
    if version_name:
        session["current_version_name"] = version_name
    return _with_session_access_flags(session, session_path, user)


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, user: Dict[str, Any] = Depends(current_user)):
    """Delete a saved session (owner only)."""
    session_path, session = _load_session_for_access(session_id)

    if not _is_session_owner(session, session_path, user):
        raise HTTPException(status_code=403, detail="Only the session owner can delete this file.")

    resolved_session_id = str(session.get("session_id") or session_id).strip()
    deleted_session_ids = [resolved_session_id]
    deleted_count = _delete_sessions(deleted_session_ids)

    return {
        "ok": True,
        "deleted_session_id": resolved_session_id,
        "deleted_session_ids": deleted_session_ids,
        "deleted_count": deleted_count,
        "cascade_deleted": False,
    }


@app.delete("/api/session/{session_id}/version/{version_name}")
async def delete_session_version(
    session_id: str,
    version_name: str,
    user: Dict[str, Any] = Depends(current_user)
):
    """Delete a version from a session's history (owner only)."""
    json_path, session = _load_session_for_access(session_id)

    if not _is_session_owner(session, json_path, user):
        raise HTTPException(status_code=403, detail="Only the session owner can delete versions.")

    versions = session.get("versions") or []
    if len(versions) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only remaining version of a file.")

    target_idx = next((i for i, v in enumerate(versions) if v.get("name") == version_name), None)
    if target_idx is None:
        raise HTTPException(status_code=404, detail=f"Version '{version_name}' not found.")

    deleted_ver = versions.pop(target_idx)

    # If the active version was deleted, fallback to the latest remaining version
    if session.get("current_version_name") == version_name:
        session["current_version_name"] = versions[-1]["name"]
        session["last_version_name"] = versions[-1]["name"]

    _save_loaded_session(json_path, session)

    await manager.broadcast(session_id, {"type": "version_deleted", "version_name": version_name})

    return {
        "ok": True,
        "deleted_version": version_name,
        "remaining_versions": [v.get("name") for v in versions],
        "current_version_name": session["current_version_name"],
    }


@app.post("/api/session/{session_id}/copy")
async def get_or_create_session_copy(
    session_id: str,
    user: Dict[str, Any] = Depends(current_user),
):
    """Backward-compatible endpoint: return the same shared session (no per-user copies in v2)."""
    session_path, session = _load_session_for_access(session_id)
    result = _with_session_access_flags(session, session_path, user)
    result["copy_created"] = False
    result["copy_mode"] = "disabled"
    return result


@app.get("/api/preview/{session_id}", response_class=HTMLResponse)
async def preview_session(
    session_id: str,
    request: Request,
    token: Optional[str] = Query(default=None),
    view_mode: str = Query(default="combined"),
    view_user_id: Optional[str] = Query(default=None),
    version_name: Optional[str] = Query(default=None),
):
    """Render an HTML preview of a saved graded session (opens in browser tab)."""
    user = current_user_from_bearer_or_query(request, token)
    if True:
        _, raw_session = _load_session_for_access(session_id)
        if version_name:
            raw_session["current_version_name"] = version_name
        base_session = _session_for_user_view(raw_session, user)

        grader_options = _preview_grader_options(base_session)
        selected_mode, selected_user_id, selected_label = _resolve_preview_selection(
                requested_mode=view_mode,
                requested_user_id=view_user_id,
                current_user_id=str(user.get("id") or "").strip(),
                grader_options=grader_options,
        )
        session = _project_session_for_view(base_session, selected_mode, selected_user_id)

        sentences = session.get("sentences", [])
        filename = str(session.get("source_filename", ""))
        uploaded_at = str(session.get("uploaded_at", ""))[:16].replace("T", " ")

        def grade_color(grade: Optional[float]) -> str:
                if grade is None:
                        return "#94a3b8"
                if grade >= 7:
                        return "#16a34a"
                if grade >= 4:
                        return "#d97706"
                return "#dc2626"

        def grade_label(grade: Optional[float]) -> str:
                if grade is None:
                        return "—"
                return f"{float(grade):.2f}"

        rows_html: list[str] = []
        for sentence in sentences:
                sentence_grade = _normalize_grade_value(sentence.get("sentence_grade"))

                triple_rows = "".join(
                        f"""<tr style="background:{'#f8fafc' if idx % 2 == 0 else '#fff'}">
                            <td style="padding:5px 10px;color:#64748b;font-size:12px;">{idx + 1}</td>
                            <td style="padding:5px 10px;font-size:12px;">{html.escape(str(triple.get('subject', '')))}</td>
                            <td style="padding:5px 10px;font-size:12px;">{html.escape(str(triple.get('predicate', '')))}</td>
                            <td style="padding:5px 10px;font-size:12px;">{html.escape(str(triple.get('object', '')))}</td>
                            <td style="padding:5px 10px;text-align:center;font-weight:600;font-size:13px;color:{grade_color(_normalize_grade_value(triple.get('grade')))}">{grade_label(_normalize_grade_value(triple.get('grade')))}</td>
                        </tr>"""
                        for idx, triple in enumerate(sentence.get("triples", []))
                )

                suggestion = str(sentence.get("suggestion", "")).strip()
                suggestion_html = (
                        f'<p style="margin:8px 0 0;font-size:12px;color:#64748b;"><em>💬 {html.escape(suggestion)}</em></p>' if suggestion else ""
                )

                completeness = _normalize_sentence_metric_value(sentence.get("completeness"))
                external_relation = _normalize_sentence_metric_value(sentence.get("external_relation"))
                metrics_html = ""
                if completeness is not None or external_relation is not None:
                        comp_label = "—" if completeness is None else f"{float(completeness):.2f}"
                        rel_label = "—" if external_relation is None else f"{float(external_relation):.2f}"
                        metrics_html = (
                                '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">'
                                f'<span style="font-size:11px;padding:3px 8px;background:#ecfdf5;border:1px solid #bbf7d0;border-radius:999px;color:#166534;">Completeness: {comp_label}/10</span>'
                                f'<span style="font-size:11px;padding:3px 8px;background:#eef2ff;border:1px solid #c7d2fe;border-radius:999px;color:#3730a3;">External Relation: {rel_label}/10</span>'
                                '</div>'
                        )

                rows_html.append(
                        f"""
                    <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;margin-bottom:18px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.06);">
                        <div style="background:#1e3a5f;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;gap:8px;">
                            <span style="font-size:13px;font-weight:600;">Sentence {html.escape(str(sentence.get('id', '')))}</span>
                            <span style="font-size:18px;font-weight:700;color:{grade_color(sentence_grade)};background:rgba(255,255,255,.15);border-radius:8px;padding:2px 10px;">{grade_label(sentence_grade)}<span style="font-size:11px;font-weight:400;"> / 10</span></span>
                        </div>
                        <div style="padding:12px 16px 4px;">
                            <p style="margin:0 0 10px;font-size:14px;color:#1e293b;line-height:1.6;border-left:3px solid #93c5fd;padding-left:10px;">{html.escape(str(sentence.get('text', '')))}</p>
                            {metrics_html}
                            {suggestion_html}
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
                """
                )

        body = "\n".join(rows_html)
        total_sentences = len(sentences)
        total_triples = int(session.get("total_triples") or sum(len(s.get("triples", [])) for s in sentences))
        graded_triples = int(
                session.get("graded_triples")
                if session.get("graded_triples") is not None
                else sum(sum(1 for t in s.get("triples", []) if t.get("grade") is not None) for s in sentences)
        )
        overall_average = _normalize_grade_value(session.get("session_average_grade"))
        overall_label = grade_label(overall_average)

        selected_option_value = "combined" if selected_mode == "combined" else f"user:{selected_user_id}"
        mode_options = [
                {
                        "value": "combined",
                        "label": f"Combined grading ({len(grader_options)} user{'s' if len(grader_options) != 1 else ''})",
                }
        ] + [
                {
                        "value": f"user:{str(option.get('user_id') or '')}",
                        "label": f"{str(option.get('user_name') or 'User')} ({int(option.get('graded_triples') or 0)} triples)",
                }
                for option in grader_options
        ]
        mode_options_html = "".join(
                f'<option value="{html.escape(option["value"])}"{" selected" if option["value"] == selected_option_value else ""}>{html.escape(option["label"])}</option>'
                for option in mode_options
        )

        preview_token_js = json.dumps(token or "")
        selected_mode_js = json.dumps(selected_mode)
        selected_user_id_js = json.dumps(selected_user_id)

        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Preview — {html.escape(filename)}</title>
  <style>
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f1f5f9; color: #1e293b; }}
        .topbar {{ background: #1e3a5f; color: #fff; padding: 14px 24px; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,.2); display: grid; grid-template-columns: minmax(220px, 1fr) auto auto; gap: 16px; align-items: center; }}
        .topbar h1 {{ margin: 0; font-size: 16px; font-weight: 700; }}
        .topbar p {{ margin: 0; font-size: 11px; opacity: .8; }}
        .controls {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .controls label {{ font-size: 11px; opacity: .9; font-weight: 600; }}
        .controls select {{ border: 1px solid #93c5fd; background: #fff; color: #1e293b; border-radius: 8px; padding: 5px 8px; font-size: 12px; min-width: 170px; }}
        .controls button {{ border: 1px solid #86efac; background: #22c55e; color: #052e16; border-radius: 8px; padding: 6px 10px; font-size: 12px; font-weight: 700; cursor: pointer; }}
        .controls button:hover {{ background: #16a34a; color: #ecfdf5; }}
        .stats {{ display: flex; gap: 18px; text-align: right; }}
        .stat-val {{ font-size: 20px; font-weight: 700; line-height: 1; }}
        .stat-lbl {{ font-size: 10px; opacity: .75; }}
        .container {{ max-width: 900px; margin: 24px auto; padding: 0 16px 40px; }}
        @media (max-width: 960px) {{ .topbar {{ grid-template-columns: 1fr; }} .stats {{ text-align: left; }} }}
        @media print {{ .topbar {{ position: static; }} }}
  </style>
</head>
<body>
  <div class="topbar">
    <div>
      <h1>📊 Ontology Triple Grading — Preview</h1>
            <p>{html.escape(filename)} &nbsp;&bull;&nbsp; Saved {html.escape(uploaded_at)} &nbsp;&bull;&nbsp; View: {html.escape(selected_label)}</p>
        </div>
        <div class="controls">
            <label for="preview-view-mode">View</label>
            <select id="preview-view-mode" onchange="onPreviewModeChange()">
                {mode_options_html}
            </select>
            <label for="preview-download-format">Download</label>
            <select id="preview-download-format">
                <option value="pdf">PDF</option>
                <option value="word">Word</option>
                <option value="excel">Excel</option>
                <option value="csv">CSV</option>
                <option value="json">JSON</option>
            </select>
            <button type="button" onclick="downloadPreview()">Download</button>
    </div>
    <div class="stats">
            <div><div class="stat-val">{total_sentences}</div><div class="stat-lbl">Sentences</div></div>
      <div><div class="stat-val">{graded_triples}/{total_triples}</div><div class="stat-lbl">Triples graded</div></div>
            <div><div class="stat-val">{len(grader_options)}</div><div class="stat-lbl">Users graded</div></div>
            <div><div class="stat-val" style="color:#86efac;">{overall_label}</div><div class="stat-lbl">Overall avg</div></div>
    </div>
  </div>
  <div class="container">
    {body}
  </div>
    <script>
        const PREVIEW_TOKEN = {preview_token_js};
        const PREVIEW_MODE = {selected_mode_js};
        const PREVIEW_USER_ID = {selected_user_id_js};

        function onPreviewModeChange() {{
            const selector = document.getElementById("preview-view-mode");
            const rawValue = selector ? selector.value : "combined";
            const chunks = rawValue.split(":");
            const mode = chunks[0] || "combined";
            const userId = chunks.length > 1 ? chunks.slice(1).join(":") : "";

            const url = new URL(window.location.href);
            url.searchParams.set("view_mode", mode);
            if (userId) {{
                url.searchParams.set("view_user_id", userId);
            }} else {{
                url.searchParams.delete("view_user_id");
            }}
            if (PREVIEW_TOKEN) {{
                url.searchParams.set("token", PREVIEW_TOKEN);
            }}
            window.location.href = url.toString();
        }}

        function downloadPreview() {{
            const formatSelector = document.getElementById("preview-download-format");
            const format = formatSelector ? formatSelector.value : "pdf";
            const url = new URL(window.location.origin + "/api/download/{session_id}/" + encodeURIComponent(format));
            if (PREVIEW_TOKEN) {{
                url.searchParams.set("token", PREVIEW_TOKEN);
            }}
            url.searchParams.set("view_mode", PREVIEW_MODE || "combined");
            if (PREVIEW_MODE === "user" && PREVIEW_USER_ID) {{
                url.searchParams.set("view_user_id", PREVIEW_USER_ID);
            }}
            window.open(url.toString(), "_blank", "noopener");
        }}
    </script>
</body>
</html>"""
        return HTMLResponse(content=html_doc)


@app.get("/api/sessions")
async def list_sessions(user: Dict[str, Any] = Depends(current_user)):
    """List all saved session files across all users for collaboration."""
    sessions = []
    if use_database_storage():
        source_sessions = list_sessions_db()
        for data in source_sessions:
            session_id = str(data.get("session_id") or "").strip()
            if not session_id:
                continue

            # Hide legacy copy sessions in v2 shared-file mode.
            root_session_id = _root_session_id(data) or session_id
            if bool(data.get("is_copy")) or root_session_id != session_id:
                continue

            owner_user_id = str(data.get("owner_user_id") or "").strip()
            grading_stats = _session_grading_stats(data)
            user_activity = _session_activity_for_user(data, user)

            owner_user = get_user_by_id(owner_user_id)
            is_owner = _is_session_owner(data, None, user)
            owner_name = data.get("owner_name") or (display_name(owner_user) if owner_user else owner_user_id)

            sessions.append({
                "session_id":      session_id,
                "source_filename": data.get("source_filename", "unknown"),
                "uploaded_at":     data.get("uploaded_at", ""),
                "total_sentences": len(data.get("sentences", [])),
                "total_versions":  len(data.get("versions", [])),
                "current_version_name": data.get("current_version_name") or "Initial",
                "owner_user_id": owner_user_id,
                "owner_name": owner_name,
                "is_owner": is_owner,
                "can_edit": _can_edit_session_directly(data, None, user),
                "can_suggest": _can_suggest_session(data, None, user),
                "can_approve": _can_approve_session(data, None, user),
                "root_session_id": session_id,
                "is_copy": False,
                "source_owner_user_id": owner_user_id,
                "source_owner_name": owner_name,
                "copied_from_session_id": None,
                "session_average_grade": grading_stats["session_average_grade"],
                "is_completed_grading": grading_stats["is_completed_grading"],
                "root_average_grade": None,
                "completed_copy_count": 0,
                "total_unique_graders": grading_stats["total_unique_graders"],
                "completed_grader_count": grading_stats["completed_grader_count"],
                "total_grade_entries": grading_stats["total_grade_entries"],
                "grader_summary": grading_stats["grader_summary"],
                "my_has_activity": user_activity["my_has_activity"],
                "my_graded_triples": user_activity["my_graded_triples"],
                "my_sentence_metric_updates": user_activity["my_sentence_metric_updates"],
                "my_sentence_comment_posts": user_activity["my_sentence_comment_posts"],
                "my_total_actions": user_activity["my_total_actions"],
            })
        return sessions

    for p in sorted(SESSIONS_ROOT.glob("*/*.json")):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            session_id = str(data.get("session_id") or p.stem).strip() or p.stem
            root_session_id = _root_session_id(data) or session_id

            # Hide legacy copy sessions in v2 shared-file mode.
            if bool(data.get("is_copy")) or root_session_id != session_id:
                continue

            owner_user_id = str(data.get("owner_user_id") or p.parent.name).strip()
            grading_stats = _session_grading_stats(data)
            user_activity = _session_activity_for_user(data, user)

            owner_user = get_user_by_id(owner_user_id)
            is_owner = _is_session_owner(data, p, user)
            owner_name = data.get("owner_name") or (display_name(owner_user) if owner_user else owner_user_id)

            sessions.append({
                "session_id":      session_id,
                "source_filename": data.get("source_filename", "unknown"),
                "uploaded_at":     data.get("uploaded_at", ""),
                "total_sentences": len(data.get("sentences", [])),
                "total_versions":  len(data.get("versions", [])),
                "current_version_name": data.get("current_version_name") or "Initial",
                "owner_user_id": owner_user_id,
                "owner_name": owner_name,
                "is_owner": is_owner,
                "can_edit": _can_edit_session_directly(data, p, user),
                "can_suggest": _can_suggest_session(data, p, user),
                "can_approve": _can_approve_session(data, p, user),
                "root_session_id": session_id,
                "is_copy": False,
                "source_owner_user_id": owner_user_id,
                "source_owner_name": owner_name,
                "copied_from_session_id": None,
                "session_average_grade": grading_stats["session_average_grade"],
                "is_completed_grading": grading_stats["is_completed_grading"],
                "root_average_grade": None,
                "completed_copy_count": 0,
                "total_unique_graders": grading_stats["total_unique_graders"],
                "completed_grader_count": grading_stats["completed_grader_count"],
                "total_grade_entries": grading_stats["total_grade_entries"],
                "grader_summary": grading_stats["grader_summary"],
                "my_has_activity": user_activity["my_has_activity"],
                "my_graded_triples": user_activity["my_graded_triples"],
                "my_sentence_metric_updates": user_activity["my_sentence_metric_updates"],
                "my_sentence_comment_posts": user_activity["my_sentence_comment_posts"],
                "my_total_actions": user_activity["my_total_actions"],
            })
        except Exception:
            pass
    return sessions


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/storage/info")
async def storage_info():
    return {
        "backend": "database" if use_database_storage() else "json",
        "notes": "Set STORAGE_BACKEND=database and DATABASE_URL for production DB-backed users/tokens/sessions.",
    }


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
    version_name: Optional[str] = None


class VoteRequest(BaseModel):
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    vote: Optional[str] = None  # "yes", "no", numeric grade, or null to clear
    version_name: Optional[str] = None


class EditSuggestionRequest(BaseModel):
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    subject: str
    predicate: str
    object: str
    reason: Optional[str] = None
    version_name: Optional[str] = None


class ApproveSuggestionRequest(BaseModel):
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    version_name: Optional[str] = None


@app.post("/api/suggestions/add")
async def add_suggestion(body: TripleSuggestionRequest, user: Dict[str, Any] = Depends(current_user)):
    """Add a suggested triple edit."""
    user_name = display_name(user)
    json_path, session = _load_session_for_access(body.session_id)

    if not _can_suggest_session(session, json_path, user):
        raise HTTPException(status_code=403, detail="Session owner cannot add triple suggestions.")
    
    sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
    if not sentence or not triple:
        raise HTTPException(status_code=404, detail="Sentence or triple not found.")
    
    # Create suggestion
    suggestion_id = str(uuid.uuid4())
    user_id = str(user.get("id") or "").strip()
    suggestion = {
        "id": suggestion_id,
        "author": user_name,
        "user_id": user_id,
        "subject": body.subject,
        "predicate": body.predicate,
        "object": body.object,
        "reason": body.reason or "",
        "created_at": datetime.utcnow().isoformat(),
        "votes": {},
        "status": "pending",
        "read_by": [user_id] if user_id else [],
        "replies": [],
    }
    
    if "suggestions" not in triple:
        triple["suggestions"] = []
    triple["suggestions"].append(suggestion)

    _save_loaded_session(json_path, session)

    return {"suggestion_id": suggestion_id, "ok": True}


@app.post("/api/suggestions/vote")
async def vote_on_suggestion(body: VoteRequest, user: Dict[str, Any] = Depends(current_user)):
    """Vote on a suggested triple edit."""
    user_name = display_name(user)
    json_path, session = _load_session_for_access(body.session_id)
    
    sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
    if not triple:
        raise HTTPException(status_code=404, detail="Triple not found.")
        
    suggestion = None
    for sug in triple.get("suggestions", []):
        if sug.get("id") == body.suggestion_id:
            suggestion = sug
            break
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    
    # Prevent voting on own suggestions
    if suggestion.get("author") == user_name:
        raise HTTPException(status_code=403, detail="You cannot vote on your own suggestions.")
    
    # Record or clear vote (toggle support)
    if "votes" not in suggestion:
        suggestion["votes"] = {}
    existing_vote = suggestion["votes"].get(user_name)
    if body.vote is None or body.vote == "" or existing_vote == body.vote:
        suggestion["votes"].pop(user_name, None)
    else:
        suggestion["votes"][user_name] = body.vote

    _save_loaded_session(json_path, session)

    return {"ok": True}


@app.post("/api/suggestions/edit")
async def edit_suggestion(body: EditSuggestionRequest, user: Dict[str, Any] = Depends(current_user)):
    """Edit a suggestion (only the author can edit)."""
    user_name = display_name(user)
    json_path, session = _load_session_for_access(body.session_id)

    sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
    if not triple:
        raise HTTPException(status_code=404, detail="Triple not found.")

    for sug in triple.get("suggestions", []):
        if sug.get("id") == body.suggestion_id:
            if sug.get("author") != user_name:
                raise HTTPException(status_code=403, detail="Only the author can edit this suggestion.")
            sug["subject"] = body.subject
            sug["predicate"] = body.predicate
            sug["object"] = body.object
            sug["reason"] = body.reason or ""
            sug["updated_at"] = datetime.utcnow().isoformat()
            _save_loaded_session(json_path, session)
            return {"ok": True}

    raise HTTPException(status_code=404, detail="Suggestion not found.")


@app.delete("/api/suggestions/{session_id}/{sentence_id}/{triple_id}/{suggestion_id}")
async def delete_suggestion(
    session_id: str,
    sentence_id: str,
    triple_id: str,
    suggestion_id: str,
    version_name: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(current_user)
):
    """Delete a suggestion (only the author can delete)."""
    user_name = display_name(user)
    user_id = str(user.get("id") or "").strip()
    json_path, session = _load_session_for_access(session_id)
    
    sentence, triple = _find_target_triple_and_sentence(session, version_name, sentence_id, triple_id)
    if not triple:
        raise HTTPException(status_code=404, detail="Triple not found.")

    suggestions = triple.get("suggestions", [])
    for i, sug in enumerate(suggestions):
        if str(sug.get("id") or sug.get("suggestion_id")) == str(suggestion_id):
            sug_author = str(sug.get("author") or sug.get("user") or sug.get("author_id") or "").strip()
            if sug_author and sug_author != user_name and sug_author != user_id and sug_author != user.get("username"):
                raise HTTPException(status_code=403, detail="Only the author can delete this suggestion.")
            suggestions.pop(i)
            _save_loaded_session(json_path, session)
            return {"ok": True}
    
    raise HTTPException(status_code=404, detail="Suggestion not found.")


@app.post("/api/suggestions/approve")
async def approve_suggestion(body: ApproveSuggestionRequest, user: Dict[str, Any] = Depends(current_user)):
    """Approve a suggestion and apply it to a triple (owner only)."""
    json_path, session = _load_session_for_access(body.session_id)

    if not _can_approve_session(session, json_path, user):
        raise HTTPException(status_code=403, detail="Only the session owner can approve suggestions.")

    owner_name = display_name(user)

    sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
    if not triple:
        raise HTTPException(status_code=404, detail="Triple not found.")

    for sug in triple.get("suggestions", []):
        if sug.get("id") == body.suggestion_id:
            # Save the prior triple so undo approve can restore it exactly.
            sug["approved_from"] = {
                "subject": triple.get("subject"),
                "predicate": triple.get("predicate"),
                "object": triple.get("object"),
                "author": triple.get("author"),
            }
            triple["subject"] = sug.get("subject", triple.get("subject"))
            triple["predicate"] = sug.get("predicate", triple.get("predicate"))
            triple["object"] = sug.get("object", triple.get("object"))
            triple["author"] = owner_name
            sug["status"] = "approved"
            sug["approved_by"] = owner_name
            sug["approved_at"] = datetime.utcnow().isoformat()

            _save_loaded_session(json_path, session)

            return {
                "ok": True,
                "triple": {
                    "id": triple.get("id"),
                    "subject": triple.get("subject"),
                    "predicate": triple.get("predicate"),
                    "object": triple.get("object"),
                    "author": triple.get("author"),
                },
            }

    raise HTTPException(status_code=404, detail="Suggestion not found.")


@app.post("/api/suggestions/unapprove")
async def unapprove_suggestion(body: ApproveSuggestionRequest, user: Dict[str, Any] = Depends(current_user)):
    """Undo approval status for a suggestion (owner only)."""
    json_path, session = _load_session_for_access(body.session_id)

    if not _can_approve_session(session, json_path, user):
        raise HTTPException(status_code=403, detail="Only the session owner can unapprove suggestions.")

    sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
    if not triple:
        raise HTTPException(status_code=404, detail="Triple not found.")

    for sug in triple.get("suggestions", []):
        if sug.get("id") == body.suggestion_id:
            previous_triple = sug.get("approved_from") if isinstance(sug.get("approved_from"), dict) else {}
            if previous_triple:
                triple["subject"] = previous_triple.get("subject", triple.get("subject"))
                triple["predicate"] = previous_triple.get("predicate", triple.get("predicate"))
                triple["object"] = previous_triple.get("object", triple.get("object"))
                triple["author"] = previous_triple.get("author")

            sug["status"] = "pending"
            sug.pop("approved_by", None)
            sug.pop("approved_at", None)
            sug.pop("approved_from", None)
            _save_loaded_session(json_path, session)
            return {
                "ok": True,
                "triple": {
                    "id": triple.get("id"),
                    "subject": triple.get("subject"),
                    "predicate": triple.get("predicate"),
                    "object": triple.get("object"),
                    "author": triple.get("author"),
                },
            }

    raise HTTPException(status_code=404, detail="Suggestion not found.")


# ---------------------------------------------------------------------------
# RESTful Benchmark Session & Curation Workflow Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/sessions")
async def create_session_workflow(body: Optional[CreateSessionRequest] = None):
    """
    RESTful session creation endpoint.
    Creates or registers a benchmark session.
    """
    session_id = (body.id or body.session_id) if body else None
    if not session_id:
        session_id = str(uuid.uuid4())

    owner_user = (body.user or body.owner_name or "owner") if body else "owner"
    owner_user_id = (body.owner_user_id or "owner_001") if body else "owner_001"
    filename = (body.filename or "benchmark_session.json") if body else "benchmark_session.json"
    sentences = (body.sentences or []) if body else []

    session_payload = {
        "id": session_id,
        "session_id": session_id,
        "source_filename": filename,
        "filename": filename,
        "uploaded_at": datetime.utcnow().isoformat(),
        "owner_user_id": owner_user_id,
        "owner_name": owner_user,
        "sentences": sentences,
        "versions": [{
            "name": "Initial",
            "created_at": datetime.utcnow().isoformat(),
            "created_by": owner_user,
            "sentences": sentences,
        }],
        "current_version_name": "Initial",
    }

    _save_loaded_session(None, session_payload, owner_user_id=owner_user_id)
    return {
        "id": session_id,
        "session_id": session_id,
        "ok": True,
        "owner": owner_user,
        "filename": filename,
    }


@app.get("/api/sessions/{session_id}")
async def get_session_workflow(session_id: str):
    """
    RESTful session retrieval endpoint.
    """
    json_path, session = _load_session_for_access(session_id)
    if "id" not in session:
        session["id"] = session.get("session_id", session_id)
    return session


@app.post("/api/sessions/{session_id}/suggestions")
async def add_session_suggestion_workflow(session_id: str, body: WorkflowSuggestionRequest):
    """
    RESTful suggestion submission endpoint for a session.
    """
    json_path, session = _load_session_for_access(session_id)

    target_triple = None
    target_sentence = None
    sentences = session.get("sentences", [])
    for sent in sentences:
        for t in sent.get("triples", []):
            if str(t.get("id") or t.get("triple_id")) == str(body.triple_id):
                target_triple = t
                target_sentence = sent
                break
        if target_triple:
            break

    if not target_triple:
        raise HTTPException(status_code=404, detail=f"Triple {body.triple_id} not found in session.")

    suggestion_id = body.suggestion_id or f"s{uuid.uuid4().hex[:6]}"
    user_name = body.user or "reviewer"

    new_suggestion = {
        "id": suggestion_id,
        "suggestion_id": suggestion_id,
        "triple_id": body.triple_id,
        "author": user_name,
        "user": user_name,
        "subject": body.subject,
        "predicate": body.predicate,
        "object": body.object,
        "comment": body.comment or body.reason or "",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "votes": {},
    }

    if "suggestions" not in target_triple:
        target_triple["suggestions"] = []
    target_triple["suggestions"].append(new_suggestion)

    _save_loaded_session(json_path, session)

    return {
        "ok": True,
        "id": suggestion_id,
        "suggestion_id": suggestion_id,
        "triple_id": body.triple_id,
        "status": "pending",
    }


@app.post("/api/sessions/{session_id}/vote")
async def vote_session_suggestion_workflow(session_id: str, body: WorkflowVoteRequest):
    """
    RESTful voting endpoint for a suggestion.
    Enforces self-voting restriction.
    """
    json_path, session = _load_session_for_access(session_id)

    target_suggestion = None
    sentences = session.get("sentences", [])
    for sent in sentences:
        for t in sent.get("triples", []):
            for sug in t.get("suggestions", []):
                if str(sug.get("id") or sug.get("suggestion_id")) == str(body.suggestion_id):
                    target_suggestion = sug
                    break
            if target_suggestion:
                break
        if target_suggestion:
            break

    if not target_suggestion:
        raise HTTPException(status_code=404, detail=f"Suggestion {body.suggestion_id} not found.")

    voter = body.user.strip()
    author = str(target_suggestion.get("author") or target_suggestion.get("user") or "").strip()
    if voter and author and voter.lower() == author.lower():
        raise HTTPException(status_code=400, detail="Reviewers cannot vote on their own suggestions.")

    if "votes" not in target_suggestion:
        target_suggestion["votes"] = {}
    target_suggestion["votes"][voter] = body.vote

    _save_loaded_session(json_path, session)

    return {
        "ok": True,
        "suggestion_id": body.suggestion_id,
        "user": voter,
        "vote": body.vote,
        "votes": target_suggestion["votes"],
    }


@app.post("/api/sessions/{session_id}/approve")
async def approve_session_suggestion_workflow(session_id: str, body: WorkflowApproveRequest):
    """
    RESTful approval endpoint for suggestion.
    Updates suggestion.status = approved, approved_by = owner,
    original triple = superseded, corrected triple active.
    """
    json_path, session = _load_session_for_access(session_id)

    target_suggestion = None
    target_triple = None
    target_sentence = None

    sentences = session.get("sentences", [])
    for sent in sentences:
        for t in sent.get("triples", []):
            for sug in t.get("suggestions", []):
                if str(sug.get("id") or sug.get("suggestion_id")) == str(body.suggestion_id):
                    target_suggestion = sug
                    target_triple = t
                    target_sentence = sent
                    break
            if target_suggestion:
                break
        if target_suggestion:
            break

    if not target_suggestion or not target_triple:
        raise HTTPException(status_code=404, detail=f"Suggestion {body.suggestion_id} not found.")

    approver = body.user or "owner"

    target_suggestion["status"] = "approved"
    target_suggestion["approved_by"] = approver
    target_suggestion["approved_at"] = datetime.utcnow().isoformat()

    # Original triple superseded
    target_triple["status"] = "superseded"
    target_triple["superseded"] = True

    # Corrected triple active in sentence
    corrected_triple_id = f"{target_triple.get('id') or 't001'}_corrected"
    corrected_triple = {
        "id": corrected_triple_id,
        "triple_id": corrected_triple_id,
        "subject": target_suggestion.get("subject"),
        "predicate": target_suggestion.get("predicate"),
        "object": target_suggestion.get("object"),
        "status": "approved",
        "is_new_suggestion": True,
        "is_corrected": True,
        "source_triple_id": target_triple.get("id"),
        "parent_suggestion_id": target_suggestion.get("id"),
        "author": target_suggestion.get("author") or target_suggestion.get("user"),
        "approved_by": approver,
        "suggestions": [],
    }

    if target_sentence is not None:
        target_sentence["triples"].append(corrected_triple)
    target_triple["superseded_by"] = corrected_triple_id

    _save_loaded_session(json_path, session)

    return {
        "ok": True,
        "suggestion_id": target_suggestion.get("id"),
        "status": "approved",
        "approved_by": approver,
        "original_triple": {
            "id": target_triple.get("id"),
            "status": "superseded",
        },
        "corrected_triple": {
            "id": corrected_triple_id,
            "subject": corrected_triple["subject"],
            "predicate": corrected_triple["predicate"],
            "object": corrected_triple["object"],
            "status": "approved",
        },
    }


@app.post("/api/sessions/{session_id}/unapprove")
async def unapprove_session_suggestion_workflow(session_id: str, body: WorkflowApproveRequest):
    """
    RESTful unapproval endpoint for suggestion.
    Reverts suggestion.status = pending, original triple status = active,
    and removes the generated corrected triple.
    """
    json_path, session = _load_session_for_access(session_id)

    target_suggestion = None
    target_triple = None
    target_sentence = None

    sentences = session.get("sentences", [])
    for sent in sentences:
        for t in sent.get("triples", []):
            for sug in t.get("suggestions", []):
                if str(sug.get("id") or sug.get("suggestion_id")) == str(body.suggestion_id):
                    target_suggestion = sug
                    target_triple = t
                    target_sentence = sent
                    break
            if target_suggestion:
                break
        if target_suggestion:
            break

    if not target_suggestion or not target_triple:
        raise HTTPException(status_code=404, detail=f"Suggestion {body.suggestion_id} not found.")

    target_suggestion["status"] = "pending"
    target_suggestion.pop("approved_by", None)
    target_suggestion.pop("approved_at", None)

    # Revert original triple to active
    target_triple["status"] = "active"
    target_triple.pop("superseded", None)
    target_triple.pop("superseded_by", None)

    # Remove corrected triple from sentence
    if target_sentence is not None:
        target_sentence["triples"] = [
            t for t in target_sentence.get("triples", [])
            if not (t.get("is_corrected") and (
                t.get("source_triple_id") == target_triple.get("id")
                or t.get("parent_suggestion_id") == target_suggestion.get("id")
                or t.get("id") == f"{target_triple.get('id')}_corrected"
            ))
        ]

    _save_loaded_session(json_path, session)

    return {
        "ok": True,
        "suggestion_id": target_suggestion.get("id"),
        "status": "pending",
        "original_triple": {
            "id": target_triple.get("id"),
            "status": "active",
        },
    }


@app.get("/api/sessions/{session_id}/export/json")
async def export_session_workflow_json(session_id: str):
    """Export adjudicated gold set as JSON."""
    json_path, session = _load_session_for_access(session_id)
    gold = build_adjudicated_gold_set(session)
    return {
        "session_id": session_id,
        "count": len(gold),
        "triples": gold,
    }


@app.get("/api/sessions/{session_id}/export/csv")
async def export_session_workflow_csv(session_id: str):
    """Export adjudicated gold set as CSV."""
    import csv
    import io
    from fastapi.responses import Response

    json_path, session = _load_session_for_access(session_id)
    gold = build_adjudicated_gold_set(session)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sentence_id", "source_sentence", "triple_id", "subject", "predicate", "object", "status"])
    for t in gold:
        writer.writerow([
            t.get("sentence_id", ""),
            t.get("source_sentence", ""),
            t.get("id") or t.get("triple_id", ""),
            t.get("subject", ""),
            t.get("predicate", ""),
            t.get("object", ""),
            t.get("status", "approved"),
        ])
    return Response(content=output.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename={session_id}_adjudicated_gold.csv"
    })


# ---------------------------------------------------------------------------
# Triple comments & removal endpoints
# ---------------------------------------------------------------------------


class MarkTripleRemovalRequest(BaseModel):
    session_id: str
    sentence_id: Union[int, str]
    triple_id: str
    marked: bool
    version_name: Optional[str] = None


@app.post("/api/triples/comments/add")
async def add_triple_comment(body: TripleCommentRequest, user: Dict[str, Any] = Depends(current_user)):
    user_name = display_name(user)
    user_id = str(user.get("id") or "").strip()
    json_path, session = _load_session_for_access(body.session_id)

    sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
    if not sentence or not triple:
        raise HTTPException(status_code=404, detail="Sentence or triple not found.")

    comment_id = f"comment_{uuid.uuid4().hex[:8]}"
    comment = {
        "id": comment_id,
        "user_id": user_id,
        "author": user_name,
        "text": body.text,
        "created_at": datetime.utcnow().isoformat(),
    }

    if "triple_comments" not in triple:
        triple["triple_comments"] = []
    triple["triple_comments"].append(comment)

    _save_loaded_session(json_path, session)

    return {"ok": True, "comment": comment}


@app.delete("/api/triples/comments/{session_id}/{sentence_id}/{triple_id}/{comment_id}")
async def delete_triple_comment_endpoint(
    session_id: str,
    sentence_id: int,
    triple_id: str,
    comment_id: str,
    version_name: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(current_user)
):
    user_id = str(user.get("id") or "").strip()
    json_path, session = _load_session_for_access(session_id)

    sentence, triple = _find_target_triple_and_sentence(session, version_name, sentence_id, triple_id)
    if not sentence or not triple:
        raise HTTPException(status_code=404, detail="Sentence or triple not found.")

    comments = triple.get("triple_comments", [])
    found_idx = -1
    for idx, c in enumerate(comments):
        if c.get("id") == comment_id:
            if c.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="You cannot delete someone else's comment.")
            found_idx = idx
            break

    if found_idx == -1:
        raise HTTPException(status_code=404, detail="Comment not found.")

    comments.pop(found_idx)
    _save_loaded_session(json_path, session)

    return {"ok": True}


@app.post("/api/comments/reply")
async def add_comment_reply(body: CommentReplyRequest, user: Dict[str, Any] = Depends(current_user)):
    user_name = display_name(user)
    user_id = str(user.get("id") or "").strip()
    json_path, session = _load_session_for_access(body.session_id)

    if body.triple_id:
        sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
        if not sentence or not triple:
            raise HTTPException(status_code=404, detail="Sentence or triple not found.")
        comments = triple.get("triple_comments", [])
    else:
        sentence = _find_target_sentence(session, body.version_name, body.sentence_id)
        if not sentence:
            raise HTTPException(status_code=404, detail="Sentence not found.")
        comments = sentence.get("sentence_comments", [])

    comment = None
    for c in comments:
        if c.get("id") == body.comment_id:
            comment = c
            break

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")

    reply_id = f"reply_{uuid.uuid4().hex[:8]}"
    reply = {
        "id": reply_id,
        "user_id": user_id,
        "author": user_name,
        "text": body.text,
        "created_at": datetime.utcnow().isoformat(),
        "read_by": [user_id] if user_id else [],
        "parent_reply_id": body.parent_reply_id if body.parent_reply_id else None,
    }

    if "replies" not in comment:
        comment["replies"] = []
    comment["replies"].append(reply)

    # Save the session
    _save_loaded_session(json_path, session)

    return {"ok": True, "reply": reply}


def _delete_reply_recursive(replies: list[Dict[str, Any]], reply_id_to_delete: str, current_user_id: str) -> None:
    # Find the target reply to verify authorization
    target = None
    for r in replies:
        if r.get("id") == reply_id_to_delete:
            target = r
            break
    if not target:
        raise HTTPException(status_code=404, detail="Reply not found.")
    if target.get("user_id") != current_user_id:
        raise HTTPException(status_code=403, detail="You cannot delete someone else's reply.")

    # Find all descendants to delete
    ids_to_remove = {reply_id_to_delete}
    added = True
    while added:
        added = False
        for r in replies:
            rid = r.get("id")
            parent_id = r.get("parent_reply_id")
            if parent_id in ids_to_remove and rid not in ids_to_remove:
                ids_to_remove.add(rid)
                added = True

    # Filter replies in place
    replies[:] = [r for r in replies if r.get("id") not in ids_to_remove]


@app.delete("/api/comments/reply/{session_id}/{sentence_id}/{comment_id}/{reply_id}")
async def delete_comment_reply(
    session_id: str,
    sentence_id: int,
    comment_id: str,
    reply_id: str,
    triple_id: Optional[str] = None,
    version_name: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(current_user)
):
    user_id = str(user.get("id") or "").strip()
    json_path, session = _load_session_for_access(session_id)

    if triple_id:
        sentence, triple = _find_target_triple_and_sentence(session, version_name, sentence_id, triple_id)
        if not sentence or not triple:
            raise HTTPException(status_code=404, detail="Sentence or triple not found.")
        comments = triple.get("triple_comments", [])
    else:
        sentence = _find_target_sentence(session, version_name, sentence_id)
        if not sentence:
            raise HTTPException(status_code=404, detail="Sentence not found.")
        comments = sentence.get("sentence_comments", [])

    comment = None
    for c in comments:
        if c.get("id") == comment_id:
            comment = c
            break

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")

    replies = comment.get("replies", [])
    _delete_reply_recursive(replies, reply_id, user_id)
    _save_loaded_session(json_path, session)

    return {"ok": True}


@app.post("/api/suggestions/reply")
async def add_suggestion_reply(body: SuggestionReplyRequest, user: Dict[str, Any] = Depends(current_user)):
    user_name = display_name(user)
    user_id = str(user.get("id") or "").strip()
    json_path, session = _load_session_for_access(body.session_id)

    sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
    if not sentence or not triple:
        raise HTTPException(status_code=404, detail="Sentence or triple not found.")

    suggestion = None
    for sug in triple.get("suggestions", []):
        if sug.get("id") == body.suggestion_id:
            suggestion = sug
            break

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    reply_id = f"reply_{uuid.uuid4().hex[:8]}"
    reply = {
        "id": reply_id,
        "user_id": user_id,
        "author": user_name,
        "text": body.text,
        "created_at": datetime.utcnow().isoformat(),
        "read_by": [user_id] if user_id else [],
        "parent_reply_id": body.parent_reply_id if body.parent_reply_id else None,
    }

    if "replies" not in suggestion:
        suggestion["replies"] = []
    suggestion["replies"].append(reply)

    _save_loaded_session(json_path, session)

    return {"ok": True, "reply": reply}


@app.delete("/api/suggestions/reply/{session_id}/{sentence_id}/{triple_id}/{suggestion_id}/{reply_id}")
async def delete_suggestion_reply(
    session_id: str,
    sentence_id: int,
    triple_id: str,
    suggestion_id: str,
    reply_id: str,
    version_name: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(current_user)
):
    user_id = str(user.get("id") or "").strip()
    json_path, session = _load_session_for_access(session_id)

    sentence, triple = _find_target_triple_and_sentence(session, version_name, sentence_id, triple_id)
    if not sentence or not triple:
        raise HTTPException(status_code=404, detail="Sentence or triple not found.")

    suggestion = None
    for sug in triple.get("suggestions", []):
        if sug.get("id") == suggestion_id:
            suggestion = sug
            break

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    replies = suggestion.get("replies", [])
    _delete_reply_recursive(replies, reply_id, user_id)
    _save_loaded_session(json_path, session)

    return {"ok": True}


@app.post("/api/notifications/read")
async def mark_notification_read(body: NotificationReadRequest, user: Dict[str, Any] = Depends(current_user)):
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        return {"ok": False, "detail": "User not authenticated"}
        
    json_path, session = _load_session_for_access(body.session_id)
    modified = False

    for sentence in session.get("sentences", []):
        # 1. Check sentence comments
        for comment in sentence.get("sentence_comments", []):
            if comment.get("id") == body.item_id:
                if "read_by" not in comment:
                    comment["read_by"] = []
                if user_id not in comment["read_by"]:
                    comment["read_by"].append(user_id)
                    modified = True
            for r in comment.get("replies", []):
                if r.get("id") == body.item_id:
                    if "read_by" not in r:
                        r["read_by"] = []
                    if user_id not in r["read_by"]:
                        r["read_by"].append(user_id)
                        modified = True

        # 2. Check triples (comments, suggestions, suggestion replies)
        for triple in sentence.get("triples", []):
            for comment in triple.get("triple_comments", []):
                if comment.get("id") == body.item_id:
                    if "read_by" not in comment:
                        comment["read_by"] = []
                    if user_id not in comment["read_by"]:
                        comment["read_by"].append(user_id)
                        modified = True
                for r in comment.get("replies", []):
                    if r.get("id") == body.item_id:
                        if "read_by" not in r:
                            r["read_by"] = []
                        if user_id not in r["read_by"]:
                            r["read_by"].append(user_id)
                            modified = True

            for sug in triple.get("suggestions", []):
                if sug.get("id") == body.item_id:
                    if "read_by" not in sug:
                        sug["read_by"] = []
                    if user_id not in sug["read_by"]:
                        sug["read_by"].append(user_id)
                        modified = True
                for r in sug.get("replies", []):
                    if r.get("id") == body.item_id:
                        if "read_by" not in r:
                            r["read_by"] = []
                        if user_id not in r["read_by"]:
                            r["read_by"].append(user_id)
                            modified = True

    if modified:
        _save_loaded_session(json_path, session)

    return {"ok": True}


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read(body: NotificationReadAllRequest, user: Dict[str, Any] = Depends(current_user)):
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        return {"ok": False, "detail": "User not authenticated"}
        
    json_path, session = _load_session_for_access(body.session_id)
    modified = False

    for sentence in session.get("sentences", []):
        # 1. Sentence comments
        for comment in sentence.get("sentence_comments", []):
            if "read_by" not in comment:
                comment["read_by"] = []
            if user_id not in comment["read_by"]:
                comment["read_by"].append(user_id)
                modified = True
            for r in comment.get("replies", []):
                if "read_by" not in r:
                    r["read_by"] = []
                if user_id not in r["read_by"]:
                    r["read_by"].append(user_id)
                    modified = True

        # 2. Triples
        for triple in sentence.get("triples", []):
            for comment in triple.get("triple_comments", []):
                if "read_by" not in comment:
                    comment["read_by"] = []
                if user_id not in comment["read_by"]:
                    comment["read_by"].append(user_id)
                    modified = True
                for r in comment.get("replies", []):
                    if "read_by" not in r:
                        r["read_by"] = []
                    if user_id not in r["read_by"]:
                        r["read_by"].append(user_id)
                        modified = True

            for sug in triple.get("suggestions", []):
                if "read_by" not in sug:
                    sug["read_by"] = []
                if user_id not in sug["read_by"]:
                    sug["read_by"].append(user_id)
                    modified = True
                for r in sug.get("replies", []):
                    if "read_by" not in r:
                        r["read_by"] = []
                    if user_id not in r["read_by"]:
                        r["read_by"].append(user_id)
                        modified = True

    if modified:
        _save_loaded_session(json_path, session)

    return {"ok": True}



@app.post("/api/triples/mark-removal")
async def mark_triple_removal(body: MarkTripleRemovalRequest, user: Dict[str, Any] = Depends(current_user)):
    json_path, session = _load_session_for_access(body.session_id)

    sentence, triple = _find_target_triple_and_sentence(session, body.version_name, body.sentence_id, body.triple_id)
    if not sentence or not triple:
        raise HTTPException(status_code=404, detail="Sentence or triple not found.")

    triple["marked_for_removal"] = body.marked
    triple["removal_reason"] = "Not needed" if body.marked else None

    # Also sync to top-level sentences if distinct
    for s in session.get("sentences", []):
        sid = str(s.get("id") or s.get("sentence_id") or "")
        target_sid = str(sentence.get("id") or sentence.get("sentence_id") or "")
        if sid == target_sid:
            for t in s.get("triples", []):
                tid = str(t.get("id") or t.get("triple_id") or "")
                target_tid = str(triple.get("id") or triple.get("triple_id") or "")
                if tid == target_tid:
                    t["marked_for_removal"] = body.marked
                    t["removal_reason"] = triple.get("removal_reason")

    _save_loaded_session(json_path, session)

    return {"ok": True}


# ---------------------------------------------------------------------------
# Evaluation endpoints
# ---------------------------------------------------------------------------

class EvaluationRequest(BaseModel):
    match_mode: str = "soft"  # "exact" or "soft"
    gold_source: str = "graded_only"  # "graded_only" or "all"


class EvaluationPreviewRequest(BaseModel):
    gold_source: str = "graded_only"


@app.post("/api/evaluate/{session_id}/preview")
async def evaluate_preview_endpoint(
    session_id: str,
    body: EvaluationPreviewRequest,
    user: Dict[str, Any] = Depends(current_user),
):
    """Return a lightweight preview of which sentences will be evaluated.
    Does NOT run stanza — just returns sentence metadata."""
    _, session = _load_session_for_access(session_id)
    user_scoped_session = _session_for_user_view(session, user)

    sentences = user_scoped_session.get("sentences", [])
    review = []
    total_gold = 0
    for s in sentences:
        all_triples = s.get("triples", [])
        graded_count = sum(1 for t in all_triples if t.get("grade") is not None)
        if body.gold_source == "graded_only":
            gold_count = graded_count
        else:
            gold_count = len(all_triples)
        total_gold += gold_count
        review.append({
            "sentence_id": s.get("id"),
            "text": (s.get("text") or "").strip(),
            "total_triples": len(all_triples),
            "graded_triples": graded_count,
            "gold_triples_used": gold_count,
            "has_text": bool((s.get("text") or "").strip()),
        })

    return {
        "session_id": session_id,
        "gold_source": body.gold_source,
        "total_sentences": len(sentences),
        "sentences_with_text": sum(1 for r in review if r["has_text"]),
        "sentences_with_gold": sum(1 for r in review if r["gold_triples_used"] > 0),
        "total_gold_triples": total_gold,
        "sentences": review,
    }


@app.post("/api/evaluate/{session_id}")
async def evaluate_session_endpoint(
    session_id: str,
    body: EvaluationRequest,
    user: Dict[str, Any] = Depends(current_user),
):
    """Run OpenIE evaluation against a graded session and return P/R/F1 results."""
    _, session = _load_session_for_access(session_id)
    user_scoped_session = _session_for_user_view(session, user)

    if body.match_mode not in ("exact", "soft"):
        raise HTTPException(status_code=400, detail="match_mode must be 'exact' or 'soft'.")
    if body.gold_source not in ("graded_only", "all"):
        raise HTTPException(status_code=400, detail="gold_source must be 'graded_only' or 'all'.")

    # Lazy import so stanza only loads when this endpoint is called
    try:
        from openie_eval import evaluate_session as _eval_session
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="OpenIE evaluation module not available. Ensure stanza is installed.",
        )

    try:
        result = _eval_session(
            user_scoped_session,
            match_mode=body.match_mode,
            gold_source=body.gold_source,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(exc)}")

    # Store result on the session so it can be retrieved later
    session["evaluation"] = result
    session["evaluation"]["evaluated_at"] = datetime.utcnow().isoformat()
    session_path, _ = _load_session_for_access(session_id)
    _save_loaded_session(session_path, session)

    return result


@app.get("/api/evaluate/{session_id}/download/{fmt}")
async def download_evaluation(
    session_id: str,
    fmt: str,
    user: Dict[str, Any] = Depends(current_user),
):
    """Download the last evaluation result for a session as JSON or CSV."""
    _, session = _load_session_for_access(session_id)

    evaluation = session.get("evaluation")
    if not evaluation:
        raise HTTPException(
            status_code=404,
            detail="No evaluation found for this session. Run POST /api/evaluate/{session_id} first.",
        )

    fmt = fmt.lower()
    filename_base = session.get("source_filename", "session").rsplit(".", 1)[0]

    if fmt == "json":
        data = json.dumps(evaluation, indent=2, ensure_ascii=False).encode("utf-8")
        media_type = "application/json"
        disposition = f'attachment; filename="{filename_base}_evaluation.json"'

    elif fmt == "csv":
        import io as _io
        import csv as _csv
        rows = []
        for s in evaluation.get("per_sentence", []):
            gold_str = "; ".join(
                f"{t.get('subject','')} | {t.get('predicate','')} | {t.get('object','')}"
                for t in s.get("gold_triples", [])
            )
            pred_str = "; ".join(
                f"{t.get('subject','')} | {t.get('predicate','')} | {t.get('object','')}"
                for t in s.get("pred_triples", [])
            )
            rows.append({
                "session_id":     evaluation.get("session_id", ""),
                "source_file":    evaluation.get("source_filename", ""),
                "match_mode":     evaluation.get("match_mode", ""),
                "gold_source":    evaluation.get("gold_source", "graded_only"),
                "sentence_id":    s["sentence_id"],
                "sentence_text":  s["sentence_text"],
                "n_gold":         s["n_gold"],
                "n_pred":         s["n_pred"],
                "true_positives": s["true_positives"],
                "precision":      s["precision"],
                "recall":         s["recall"],
                "f1":             s["f1"],
                "gold_triples":   gold_str,
                "pred_triples":   pred_str,
            })
        for agg_key in ("macro", "micro"):
            agg = evaluation.get(agg_key, {})
            rows.append({
                "session_id": evaluation.get("session_id", ""),
                "source_file": evaluation.get("source_filename", ""),
                "match_mode": evaluation.get("match_mode", ""),
                "gold_source": evaluation.get("gold_source", "graded_only"),
                "sentence_id": f"[{agg_key}]",
                "sentence_text": "",
                "n_gold": agg.get("n_gold", ""),
                "n_pred": agg.get("n_pred", ""),
                "true_positives": agg.get("true_positives", ""),
                "precision": agg.get("precision", ""),
                "recall": agg.get("recall", ""),
                "f1": agg.get("f1", ""),
                "gold_triples": "",
                "pred_triples": "",
            })
        fieldnames = [
            "session_id", "source_file", "match_mode", "sentence_id",
            "gold_source",
            "sentence_text", "n_gold", "n_pred", "true_positives",
            "precision", "recall", "f1", "gold_triples", "pred_triples",
        ]
        buf = _io.StringIO()
        writer = _csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        data = buf.getvalue().encode("utf-8-sig")
        media_type = "text/csv"
        disposition = f'attachment; filename="{filename_base}_evaluation.csv"'

    else:
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'.")

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


# ---------------------------------------------------------------------------
# Serve the React build in production
# Mount AFTER all API routes so /api/* is never intercepted.
# ---------------------------------------------------------------------------
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="static")
else:
    from fastapi.responses import RedirectResponse

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/docs")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
