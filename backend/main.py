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

from database import (
    add_token_db,
    delete_token_db,
    delete_sessions_db,
    init_database,
    list_sessions_db,
    load_session_db,
    load_tokens_db,
    load_users_db,
    save_single_session_db,
    save_tokens_db,
    save_users_db,
    upsert_user_db,
    use_database_storage,
)
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
    if use_database_storage():
        users = load_users_db()
        if "users" not in users:
            users = {"users": []}
        return users

    users = _load_json(USERS_FILE, {"users": []})
    if "users" not in users:
        users = {"users": []}
    return users


def _save_users(users: Dict[str, Any]):
    if use_database_storage():
        save_users_db(users)
        return
    _save_json(USERS_FILE, users)


def _load_tokens() -> Dict[str, Any]:
    if use_database_storage():
        tokens = load_tokens_db()
        if "tokens" not in tokens:
            tokens = {"tokens": {}}
        return tokens

    tokens = _load_json(TOKENS_FILE, {"tokens": {}})
    if "tokens" not in tokens:
        tokens = {"tokens": {}}
    return tokens


def _save_tokens(tokens: Dict[str, Any]):
    if use_database_storage():
        save_tokens_db(tokens)
        return
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
    created_at = datetime.utcnow().isoformat()
    if use_database_storage():
        add_token_db(token, user_id, created_at)
    else:
        tokens = _load_tokens()
        tokens["tokens"][token] = {"user_id": user_id, "created_at": created_at}
        _save_tokens(tokens)
    return token


def _user_from_token(token: str) -> Optional[Dict[str, Any]]:
    tokens = _load_tokens()["tokens"]
    token_data = tokens.get(token)
    if not token_data:
        return None
    return _get_user_by_id(token_data.get("user_id", ""))


def _revoke_token(token: str):
    if use_database_storage():
        delete_token_db(token)
    else:
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


def _find_existing_session_path(session_id: str) -> Optional[Path]:
    if not session_id.replace("-", "").isalnum():
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
        target_user_id = owner_user_id or session.get("owner_user_id")
        target_path = _get_session_path_for_access(str(session.get("session_id", "")), owner_user_id=target_user_id)
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
    user_username = _norm_username(user.get("username", ""))
    user_email = _norm_email(user.get("email", ""))

    owner_user_id = str(session.get("owner_user_id") or "").strip()
    if owner_user_id and (
        owner_user_id == user_id
        or _norm_username(owner_user_id) == user_username
        or _norm_email(owner_user_id) == user_email
    ):
        return True

    owner_email = session.get("owner_email")
    if owner_email and _norm_email(owner_email) == user_email:
        return True

    owner_username = session.get("owner_username")
    if owner_username and _norm_username(owner_username) == user_username:
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
            or _norm_username(parent_owner) == user_username
            or _norm_email(parent_owner) == user_email
        )
    )


def _root_session_id(session: Dict[str, Any]) -> str:
    return str(session.get("root_session_id") or session.get("session_id") or "").strip()


def _can_approve_session(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    # In v2 collaboration mode, only the owner can approve/unapprove suggestions.
    return _is_session_owner(session, session_path, user)


def _can_edit_session_directly(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    # Any authenticated collaborator can grade a shared file.
    return True


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


def _apply_collaborative_grades(
    incoming_session: Dict[str, Any],
    existing_session: Optional[Dict[str, Any]],
    user: Dict[str, Any],
) -> None:
    user_id = str(user.get("id") or "").strip()
    user_name = _display_name(user)
    now_iso = datetime.utcnow().isoformat()

    existing_sentences = {
        s.get("id"): s
        for s in (existing_session or {}).get("sentences", [])
        if s.get("id") is not None
    }
    owner_fallback_user_id = str((existing_session or {}).get("owner_user_id") or "").strip()

    for sentence in incoming_session.get("sentences", []):
        existing_sentence = existing_sentences.get(sentence.get("id"))
        existing_triples = {
            t.get("id"): t
            for t in (existing_sentence or {}).get("triples", [])
            if t.get("id") is not None
        }

        for triple in sentence.get("triples", []):
            triple_id = triple.get("id")
            existing_triple = existing_triples.get(triple_id, {})

            if existing_triple:
                # Triple text and suggestion threads are collaborative shared state;
                # preserve the latest server copy to avoid stale client overwrites.
                triple["subject"] = existing_triple.get("subject", triple.get("subject"))
                triple["predicate"] = existing_triple.get("predicate", triple.get("predicate"))
                triple["object"] = existing_triple.get("object", triple.get("object"))
                if isinstance(existing_triple.get("suggestions"), list):
                    triple["suggestions"] = existing_triple.get("suggestions", [])

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
            if my_grade is None:
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


def _session_grading_stats(session_data: Dict[str, Any]) -> Dict[str, Any]:
    total_triples = 0
    graded_triples = 0
    total_grade_entries = 0
    grade_sum = 0.0

    per_grader: Dict[str, Dict[str, Any]] = {}
    owner_fallback_user_id = str(session_data.get("owner_user_id") or "").strip()

    for sentence in session_data.get("sentences", []):
        for triple in sentence.get("triples", []):
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
        "session_average_grade": overall_avg,
        "is_completed_grading": is_completed,
        "total_grade_entries": total_grade_entries,
        "total_unique_graders": len(grader_summary_rows),
        "completed_grader_count": completed_grader_count,
        "grader_summary": grader_summary_rows,
    }


def _session_for_user_view(session: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    # Deep copy so caller gets a user-scoped projection without mutating storage payload.
    data = json.loads(json.dumps(session, ensure_ascii=False))
    stats = _session_grading_stats(data)

    user_id = str(user.get("id") or "").strip()
    for sentence in data.get("sentences", []):
        for triple in sentence.get("triples", []):
            grades_by_user = triple.get("grades_by_user") if isinstance(triple.get("grades_by_user"), dict) else {}
            grade_values = [
                float(payload.get("grade"))
                for payload in grades_by_user.values()
                if _normalize_grade_value(payload.get("grade")) is not None
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

    data["session_average_grade"] = stats["session_average_grade"]
    data["is_completed_grading"] = stats["is_completed_grading"]
    data["total_grade_entries"] = stats["total_grade_entries"]
    data["total_unique_graders"] = stats["total_unique_graders"]
    data["completed_grader_count"] = stats["completed_grader_count"]
    data["grader_summary"] = stats["grader_summary"]

    my_summary = next((row for row in stats["grader_summary"] if row.get("user_id") == user_id), None)
    data["my_graded_triples"] = int(my_summary.get("graded_triples") or 0) if my_summary else 0
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
            })

        if not triples:
            continue

        sentence_text = str(group.get("sentence_text") or "").strip()
        if not sentence_text and isinstance(selected_version, dict):
            sentence_text = str(selected_version.get("sentence_candidate") or "").strip()

        sentences.append({
            "id": sentence_id,
            "text": sentence_text or "(no sentence text)",
            "suggestion": "",
            "sentence_grade": None,
            "completeness": None,
            "external_relation": None,
            "triples": triples,
        })
        sentence_id += 1

    return sentences


def _merge_existing_suggestions(incoming_session: Dict[str, Any], existing_session: Dict[str, Any]) -> None:
    """Keep suggestions persisted via suggestion endpoints when owner performs a full save."""
    existing_sentences = {
        s.get("id"): s
        for s in existing_session.get("sentences", [])
        if s.get("id") is not None
    }

    for sentence in incoming_session.get("sentences", []):
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

            existing_suggestions = existing_triple.get("suggestions")
            if isinstance(existing_suggestions, list):
                # Suggestion writes are already persisted server-side by dedicated endpoints.
                # Preserve them to avoid stale client payloads wiping comments/posts.
                triple["suggestions"] = existing_suggestions




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
    manual_mode: bool = False


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

init_database(users_json_path=USERS_FILE, tokens_json_path=TOKENS_FILE, sessions_root=SESSIONS_ROOT)
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
    if use_database_storage():
        upsert_user_db(user)
    else:
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
        "user": {
            "id": user["id"],
            "username": user.get("username", ""),
            "name": _display_name(user),
            "email": user["email"],
        },
    }


@app.get("/api/auth/me")
async def me(user: Dict[str, Any] = Depends(_current_user)):
    return {
        "id": user["id"],
        "username": user.get("username", ""),
        "name": _display_name(user),
        "email": user["email"],
    }


@app.post("/api/auth/logout")
async def logout(creds: Optional[HTTPAuthorizationCredentials] = Depends(_AUTH_SCHEME)):
    if creds and creds.scheme.lower() == "bearer":
        _revoke_token(creds.credentials)
    return {"ok": True}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user: Dict[str, Any] = Depends(_current_user)):
    """Parse an uploaded file, save an owner draft, and return sentence-group data for review."""
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
    uploaded_at = datetime.utcnow().isoformat()

    draft_session = {
        "session_id": session_id,
        "source_filename": file.filename,
        "uploaded_at": uploaded_at,
        "sentences": _sentence_groups_to_draft_sentences(sentence_groups),
        "manual_mode": False,
        "owner_user_id": user.get("id", ""),
        "owner_name": _display_name(user),
        "owner_email": _norm_email(user.get("email", "")),
        "owner_username": _norm_username(user.get("username", "")),
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


@app.post("/api/save")
async def save_session(body: SaveRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Persist a graded session to the storage directory."""
    session_data = body.model_dump()

    existing_path, existing_session = _load_existing_session(body.session_id)

    if existing_session:
        try:
            _merge_existing_suggestions(session_data, existing_session)
        except Exception:
            # Fall back to incoming payload if previous session cannot be read.
            pass

    _apply_collaborative_grades(session_data, existing_session, user)

    # Capture user info and recompute sentence grades server-side for integrity
    for s in session_data["sentences"]:
        # Normalize sentence-level metrics and preserve backward compatibility.
        if s.get("completeness") is None:
            s["completeness"] = next(
                (t.get("completeness") for t in s.get("triples", []) if t.get("completeness") is not None),
                None,
            )
        external_relation = s.get("external_relation")
        if external_relation is None:
            external_relation = s.get("relation")
        if external_relation is None:
            external_relation = next(
                (t.get("relation") for t in s.get("triples", []) if t.get("relation") is not None),
                None,
            )
        s["external_relation"] = external_relation

        sentence_grades: list[float] = []
        for t in s.get("triples", []):
            t.pop("completeness", None)
            t.pop("relation", None)
            grade = _normalize_grade_value(t.get("grade"))
            if grade is not None:
                sentence_grades.append(grade)

        s["sentence_grade"] = round(sum(sentence_grades) / len(sentence_grades), 2) if sentence_grades else None

    if existing_session:
        owner_user_id = str(existing_session.get("owner_user_id") or "").strip() or user.get("id", "")
        owner_user = _get_user_by_id(owner_user_id)

        owner_email = existing_session.get("owner_email")
        if not owner_email and owner_user:
            owner_email = owner_user.get("email")

        owner_username = existing_session.get("owner_username")
        if not owner_username and owner_user:
            owner_username = owner_user.get("username")

        session_data["manual_mode"] = bool(existing_session.get("manual_mode")) or bool(session_data.get("manual_mode"))
        session_data["owner_user_id"] = owner_user_id
        session_data["owner_name"] = (
            existing_session.get("owner_name")
            or (_display_name(owner_user) if owner_user else None)
            or _display_name(user)
        )
        session_data["owner_email"] = _norm_email(str(owner_email or user.get("email", "")))
        session_data["owner_username"] = _norm_username(str(owner_username or user.get("username", "")))

        # Keep prior evaluation payload unless overwritten explicitly.
        if existing_session.get("evaluation") and not session_data.get("evaluation"):
            session_data["evaluation"] = existing_session.get("evaluation")
    else:
        session_data["manual_mode"] = bool(session_data.get("manual_mode"))
        session_data["owner_user_id"] = user["id"]
        session_data["owner_name"] = _display_name(user)
        session_data["owner_email"] = _norm_email(user.get("email", ""))
        session_data["owner_username"] = _norm_username(user.get("username", ""))

    session_data["root_session_id"] = body.session_id
    session_data["is_copy"] = False
    session_data.pop("copied_from_session_id", None)
    session_data.pop("copied_at", None)

    _save_loaded_session(existing_path, session_data, owner_user_id=user["id"])

    stats = _session_grading_stats(session_data)
    return {
        "session_id": body.session_id,
        "saved_at": datetime.utcnow().isoformat(),
        "total_unique_graders": stats["total_unique_graders"],
        "grader_summary": stats["grader_summary"],
    }


@app.get("/api/download/{session_id}/{fmt}")
async def download_session(session_id: str, fmt: str, user: Dict[str, Any] = Depends(_current_user)):
    """Download a saved session in the requested format."""
    _, session = _load_session_for_access(session_id)
    session = _session_for_user_view(session, user)

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
    session_path, session = _load_session_for_access(session_id)
    return _with_session_access_flags(session, session_path, user)


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, user: Dict[str, Any] = Depends(_current_user)):
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


@app.post("/api/session/{session_id}/copy")
async def get_or_create_session_copy(
    session_id: str,
    user: Dict[str, Any] = Depends(_current_user),
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
):
    """Render an HTML preview of a saved graded session (opens in browser tab)."""
    user = _current_user_from_bearer_or_query(request, token)
    _, session = _load_session_for_access(session_id)
    session = _session_for_user_view(session, user)

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
        completeness = s.get("completeness")
        external_relation = s.get("external_relation")
        metrics_html = ""
        if completeness is not None or external_relation is not None:
            comp_label = "—" if completeness is None else str(completeness)
            rel_label = "—" if external_relation is None else str(external_relation)
            metrics_html = (
            '<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">'
            f'<span style="font-size:11px;padding:3px 8px;background:#ecfdf5;border:1px solid #bbf7d0;border-radius:999px;color:#166534;">Completeness: {comp_label}/10</span>'
            f'<span style="font-size:11px;padding:3px 8px;background:#eef2ff;border:1px solid #c7d2fe;border-radius:999px;color:#3730a3;">External Relation: {rel_label}/10</span>'
            '</div>'
            )
        rows_html.append(f"""
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;margin-bottom:18px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.06);">
            <div style="background:#1e3a5f;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:13px;font-weight:600;">Sentence {s['id']}</span>
              <span style="font-size:18px;font-weight:700;color:{gc};background:rgba(255,255,255,.15);border-radius:8px;padding:2px 10px;">{avg_label}<span style="font-size:11px;font-weight:400;"> / 10</span></span>
            </div>
            <div style="padding:12px 16px 4px;">
              <p style="margin:0 0 10px;font-size:14px;color:#1e293b;line-height:1.6;border-left:3px solid #93c5fd;padding-left:10px;">{s.get('text','')}</p>
                            {metrics_html}
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

            owner_user = _get_user_by_id(owner_user_id)
            is_owner = _is_session_owner(data, None, user)
            owner_name = data.get("owner_name") or (_display_name(owner_user) if owner_user else owner_user_id)

            sessions.append({
                "session_id":      session_id,
                "source_filename": data.get("source_filename", "unknown"),
                "uploaded_at":     data.get("uploaded_at", ""),
                "total_sentences": len(data.get("sentences", [])),
                "owner_user_id": owner_user_id,
                "owner_name": owner_name,
                "is_owner": is_owner,
                "can_edit": True,
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

            owner_user = _get_user_by_id(owner_user_id)
            is_owner = _is_session_owner(data, p, user)
            owner_name = data.get("owner_name") or (_display_name(owner_user) if owner_user else owner_user_id)

            sessions.append({
                "session_id":      session_id,
                "source_filename": data.get("source_filename", "unknown"),
                "uploaded_at":     data.get("uploaded_at", ""),
                "total_sentences": len(data.get("sentences", [])),
                "owner_user_id": owner_user_id,
                "owner_name": owner_name,
                "is_owner": is_owner,
                "can_edit": True,
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


class ApproveSuggestionRequest(BaseModel):
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str


@app.post("/api/suggestions/add")
async def add_suggestion(body: TripleSuggestionRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Add a suggested triple edit."""
    user_name = _display_name(user)
    json_path, session = _load_session_for_access(body.session_id)
    
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

    _save_loaded_session(json_path, session)

    return {"suggestion_id": suggestion_id, "ok": True}


@app.post("/api/suggestions/vote")
async def vote_on_suggestion(body: VoteRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Vote on a suggested triple edit."""
    user_name = _display_name(user)
    json_path, session = _load_session_for_access(body.session_id)
    
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

    _save_loaded_session(json_path, session)

    return {"ok": True}


@app.post("/api/suggestions/edit")
async def edit_suggestion(body: EditSuggestionRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Edit a suggestion (only the author can edit)."""
    user_name = _display_name(user)
    json_path, session = _load_session_for_access(body.session_id)

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
                            _save_loaded_session(json_path, session)
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
    json_path, session = _load_session_for_access(session_id)
    
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
                            _save_loaded_session(json_path, session)
                            return {"ok": True}
    
    raise HTTPException(status_code=404, detail="Suggestion not found.")


@app.post("/api/suggestions/approve")
async def approve_suggestion(body: ApproveSuggestionRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Approve a suggestion and apply it to a triple (owner only)."""
    json_path, session = _load_session_for_access(body.session_id)

    if not _can_approve_session(session, json_path, user):
        raise HTTPException(status_code=403, detail="Only the session owner can approve suggestions.")

    owner_name = _display_name(user)

    for s in session.get("sentences", []):
        if s.get("id") == body.sentence_id:
            for t in s.get("triples", []):
                if t.get("id") == body.triple_id:
                    for sug in t.get("suggestions", []):
                        if sug.get("id") == body.suggestion_id:
                            t["subject"] = sug.get("subject", t.get("subject"))
                            t["predicate"] = sug.get("predicate", t.get("predicate"))
                            t["object"] = sug.get("object", t.get("object"))
                            t["author"] = owner_name
                            sug["status"] = "approved"
                            sug["approved_by"] = owner_name
                            sug["approved_at"] = datetime.utcnow().isoformat()

                            _save_loaded_session(json_path, session)

                            return {
                                "ok": True,
                                "triple": {
                                    "id": t.get("id"),
                                    "subject": t.get("subject"),
                                    "predicate": t.get("predicate"),
                                    "object": t.get("object"),
                                    "author": t.get("author"),
                                },
                            }

    raise HTTPException(status_code=404, detail="Suggestion not found.")


@app.post("/api/suggestions/unapprove")
async def unapprove_suggestion(body: ApproveSuggestionRequest, user: Dict[str, Any] = Depends(_current_user)):
    """Undo approval status for a suggestion (owner only)."""
    json_path, session = _load_session_for_access(body.session_id)

    if not _can_approve_session(session, json_path, user):
        raise HTTPException(status_code=403, detail="Only the session owner can unapprove suggestions.")

    for s in session.get("sentences", []):
        if s.get("id") == body.sentence_id:
            for t in s.get("triples", []):
                if t.get("id") == body.triple_id:
                    for sug in t.get("suggestions", []):
                        if sug.get("id") == body.suggestion_id:
                            sug["status"] = "pending"
                            sug.pop("approved_by", None)
                            sug.pop("approved_at", None)
                            _save_loaded_session(json_path, session)
                            return {"ok": True}

    raise HTTPException(status_code=404, detail="Suggestion not found.")


# ---------------------------------------------------------------------------
# Evaluation endpoints
# ---------------------------------------------------------------------------

class EvaluationRequest(BaseModel):
    match_mode: str = "soft"  # "exact" or "soft"
    gold_source: str = "graded_only"  # "graded_only" or "all"


@app.post("/api/evaluate/{session_id}")
async def evaluate_session_endpoint(
    session_id: str,
    body: EvaluationRequest,
    user: Dict[str, Any] = Depends(_current_user),
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
    user: Dict[str, Any] = Depends(_current_user),
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
