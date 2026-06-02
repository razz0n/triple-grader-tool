"""  
main.py — FastAPI backend for the Ontology Triple Grading Tool. 

Endpoints:
  POST /api/upload              → parse uploaded file → return session data
  POST /api/save                → persist graded session to storage/
  GET  /api/download/{id}/{fmt} → stream file in chosen format
  GET  /api/preview/{id}        → render HTML preview of graded session
  GET  /api/sessions            → list saved sessions
"""

import hashlib
import html
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
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
    load_users,
    revoke_token,
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
)
from parser import parse_file_rich
from services import (
    apply_collaborative_grades,
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
# Models
# ---------------------------------------------------------------------------


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

            created_at = payload.get("created_at")
            if created_at is None:
                created_at = payload.get("posted_at")
            if created_at is None:
                created_at = fallback_created_at or datetime.utcnow().isoformat()

            normalized.append({
                "id": comment_id,
                "user_id": user_id,
                "author": author,
                "text": text,
                "created_at": created_at,
            })

    if not normalized:
        legacy_text = str(fallback_text or "").strip()
        if legacy_text:
            legacy_author = str(fallback_author or "Legacy comment").strip() or "Legacy comment"
            legacy_user_id = str(fallback_user_id or "").strip()
            legacy_hash = hashlib.sha1(legacy_text.encode("utf-8")).hexdigest()[:10]
            normalized.append({
                "id": f"legacy_comment_{legacy_hash}",
                "user_id": legacy_user_id,
                "author": legacy_author,
                "text": legacy_text,
                "created_at": fallback_created_at or datetime.utcnow().isoformat(),
            })

    normalized.sort(key=lambda row: str(row.get("created_at") or ""))
    return normalized


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

        my_external = _normalize_sentence_metric_value(
            sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation")
        )
        if not user_can_grade:
            merged_external.pop(user_id, None)
            sentence["external_relation"] = None
            sentence.pop("external_relation_updated_at", None)
        elif my_external is None:
            merged_external.pop(user_id, None)
            sentence["external_relation"] = None
            sentence.pop("external_relation_updated_at", None)
        else:
            merged_external[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "value": my_external,
                "updated_at": now_iso,
            }
            sentence["external_relation"] = my_external
            sentence["external_relation_updated_at"] = now_iso
        sentence["external_relation_by_user"] = merged_external

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
    stats = _session_grading_stats(data)

    user_id = str(user.get("id") or "").strip()
    owner_fallback_user_id = str(data.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(data.get("owner_name") or "").strip()
    for sentence in data.get("sentences", []):
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
            "sentence_comments": [],
            "comment_count": 0,
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


def _merge_existing_sentence_comments(incoming_session: Dict[str, Any], existing_session: Dict[str, Any]) -> None:
    """Preserve and merge sentence comment threads across full-session saves."""
    existing_sentences = {
        s.get("id"): s
        for s in existing_session.get("sentences", [])
        if s.get("id") is not None
    }

    owner_fallback_user_id = str(existing_session.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(existing_session.get("owner_name") or "").strip()

    for sentence in incoming_session.get("sentences", []):
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
    }

    users_data["users"].append(user)
    if use_database_storage():
        upsert_user_db(user)
    else:
        save_users(users_data)

    return {
        "ok": True,
        "message": "Account created successfully. Please log in.",
        "user": {"id": user["id"], "username": user["username"], "name": display_name(user), "email": user["email"]},
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
            "username": user.get("username", ""),
            "name": display_name(user),
            "email": user["email"],
        },
    }


@app.get("/api/auth/me")
async def me(user: Dict[str, Any] = Depends(current_user)):
    return {
        "id": user["id"],
        "username": user.get("username", ""),
        "name": display_name(user),
        "email": user["email"],
    }


@app.post("/api/auth/logout")
async def logout(creds: Optional[HTTPAuthorizationCredentials] = Depends(_AUTH_SCHEME)):
    if creds and creds.scheme.lower() == "bearer":
        revoke_token(creds.credentials)
    return {"ok": True}

def _json_to_sentence_groups(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Convert a downloaded session JSON into sentence_groups for review."""
    if isinstance(payload.get("sentence_groups"), list):
        return payload["sentence_groups"]

    sentences = payload.get("sentences")
    if not isinstance(sentences, list):
        raise ValueError("JSON upload must contain either 'sentence_groups' or exported 'sentences'.")

    groups: list[Dict[str, Any]] = []
    for idx, sentence in enumerate(sentences, start=1):
        text = str(sentence.get("text") or sentence.get("sentence_text") or "").strip()
        triples = sentence.get("triples") or []
        if not isinstance(triples, list) or not triples:
            continue

        version_triples = []
        for ti, triple in enumerate(triples, start=1):
            version_triples.append({
                "id": str(triple.get("id") or f"{idx}_1_{ti}"),
                "subject": str(triple.get("subject") or ""),
                "predicate": str(triple.get("predicate") or ""),
                "object": str(triple.get("object") or ""),
            })

        groups.append({
            "group_id": idx,
            "sentence_text": text,
            "selected_version_id": f"{idx}_1",
            "versions": [
                {
                    "version_id": f"{idx}_1",
                    "version_label": "Imported",
                    "sentence_candidate": text,
                    "triples": version_triples,
                }
            ],
        })

    if not groups:
        raise ValueError("Uploaded JSON contains no valid sentences or triples.")

    return groups


def _parse_uploaded_json(file_bytes: bytes) -> list[Dict[str, Any]]:
    try:
        payload = json.loads(file_bytes.decode("utf-8-sig"))
    except Exception:
        try:
            payload = json.loads(file_bytes.decode("latin-1"))
        except Exception as exc:
            raise ValueError(f"Invalid JSON upload: {str(exc)}")

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


@app.post("/api/save")
async def save_session(body: SaveRequest, user: Dict[str, Any] = Depends(current_user)):
    """Persist a graded session to the storage directory."""
    session_data = body.model_dump()

    existing_path, existing_session = _load_existing_session(body.session_id)

    if existing_session:
        try:
            _merge_existing_suggestions(session_data, existing_session)
        except Exception:
            # Fall back to incoming payload if previous session cannot be read.
            pass

        try:
            _merge_existing_sentence_comments(session_data, existing_session)
        except Exception:
            # Fall back to incoming payload if previous session cannot be read.
            pass

    _apply_collaborative_grades(session_data, existing_session, user)

    # Capture user info and recompute sentence grades server-side for integrity
    for s in session_data["sentences"]:
        sentence_comments = _normalize_sentence_comments(
            s.get("sentence_comments"),
            fallback_text=str(s.get("suggestion") or ""),
            fallback_author=display_name(user),
            fallback_user_id=str(user.get("id") or "").strip(),
            fallback_created_at=s.get("comment_created_at"),
        )
        s["sentence_comments"] = sentence_comments
        s["comment_count"] = len(sentence_comments)
        s["suggestion"] = sentence_comments[-1].get("text", "") if sentence_comments else ""

        # Normalize sentence-level metrics from collaborator-specific maps.
        s["completeness"] = _normalize_sentence_metric_value(s.get("completeness"))

        external_relation = s.get("external_relation")
        if external_relation is None:
            external_relation = s.get("relation")
        s["external_relation"] = _normalize_sentence_metric_value(external_relation)
        s.pop("relation", None)

        s["completeness_by_user"] = _normalize_sentence_metric_by_user(
            s.get("completeness_by_user"),
            fallback_value=s.get("completeness"),
            fallback_user_id=str(user.get("id") or "").strip(),
            fallback_user_name=display_name(user),
            fallback_updated_at=s.get("completeness_updated_at"),
        )
        s["external_relation_by_user"] = _normalize_sentence_metric_by_user(
            s.get("external_relation_by_user"),
            fallback_value=s.get("external_relation"),
            fallback_user_id=str(user.get("id") or "").strip(),
            fallback_user_name=display_name(user),
            fallback_updated_at=s.get("external_relation_updated_at"),
        )

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
        owner_user = get_user_by_id(owner_user_id)

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
            or (display_name(owner_user) if owner_user else None)
            or display_name(user)
        )
        session_data["owner_email"] = norm_email(str(owner_email or user.get("email", "")))
        session_data["owner_username"] = norm_username(str(owner_username or user.get("username", "")))

        # Keep prior evaluation payload unless overwritten explicitly.
        if existing_session.get("evaluation") and not session_data.get("evaluation"):
            session_data["evaluation"] = existing_session.get("evaluation")
    else:
        session_data["manual_mode"] = bool(session_data.get("manual_mode"))
        session_data["owner_user_id"] = user["id"]
        session_data["owner_name"] = display_name(user)
        session_data["owner_email"] = norm_email(user.get("email", ""))
        session_data["owner_username"] = norm_username(user.get("username", ""))

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

    data["session_average_grade"] = _avg_or_none(overall_triple_grades)
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
):
    """Download a saved session in the requested format."""
    user = current_user_from_bearer_or_query(request, token)
    _, raw_session = _load_session_for_access(session_id)
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
async def get_session(session_id: str, user: Dict[str, Any] = Depends(current_user)):
    """Return the full saved session JSON (used by the frontend to resume a session)."""
    session_path, session = _load_session_for_access(session_id)
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
):
    """Render an HTML preview of a saved graded session (opens in browser tab)."""
    user = current_user_from_bearer_or_query(request, token)
    if True:
        _, raw_session = _load_session_for_access(session_id)
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
async def add_suggestion(body: TripleSuggestionRequest, user: Dict[str, Any] = Depends(current_user)):
    """Add a suggested triple edit."""
    user_name = display_name(user)
    json_path, session = _load_session_for_access(body.session_id)

    if not _can_suggest_session(session, json_path, user):
        raise HTTPException(status_code=403, detail="Session owner cannot add triple suggestions.")
    
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
async def vote_on_suggestion(body: VoteRequest, user: Dict[str, Any] = Depends(current_user)):
    """Vote on a suggested triple edit."""
    user_name = display_name(user)
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
    user: Dict[str, Any] = Depends(current_user)
):
    """Delete a suggestion (only the author can delete)."""
    user_name = display_name(user)
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
async def approve_suggestion(body: ApproveSuggestionRequest, user: Dict[str, Any] = Depends(current_user)):
    """Approve a suggestion and apply it to a triple (owner only)."""
    json_path, session = _load_session_for_access(body.session_id)

    if not _can_approve_session(session, json_path, user):
        raise HTTPException(status_code=403, detail="Only the session owner can approve suggestions.")

    owner_name = display_name(user)

    for s in session.get("sentences", []):
        if s.get("id") == body.sentence_id:
            for t in s.get("triples", []):
                if t.get("id") == body.triple_id:
                    for sug in t.get("suggestions", []):
                        if sug.get("id") == body.suggestion_id:
                            # Save the prior triple so undo approve can restore it exactly.
                            sug["approved_from"] = {
                                "subject": t.get("subject"),
                                "predicate": t.get("predicate"),
                                "object": t.get("object"),
                                "author": t.get("author"),
                            }
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
async def unapprove_suggestion(body: ApproveSuggestionRequest, user: Dict[str, Any] = Depends(current_user)):
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
                            previous_triple = sug.get("approved_from") if isinstance(sug.get("approved_from"), dict) else {}
                            if previous_triple:
                                t["subject"] = previous_triple.get("subject", t.get("subject"))
                                t["predicate"] = previous_triple.get("predicate", t.get("predicate"))
                                t["object"] = previous_triple.get("object", t.get("object"))
                                t["author"] = previous_triple.get("author")

                            sug["status"] = "pending"
                            sug.pop("approved_by", None)
                            sug.pop("approved_at", None)
                            sug.pop("approved_from", None)
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
