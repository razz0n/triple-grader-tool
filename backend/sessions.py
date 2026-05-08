"""
sessions.py — Session management for the Ontology Triple Grading Tool.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException

from database import load_session_db, save_single_session_db, use_database_storage
from utils import load_json, norm_email, norm_username

# Constants
STORAGE_DIR = Path(__file__).parent / "storage"
SESSIONS_ROOT = STORAGE_DIR / "users"


def session_path_for_user(user_id: str, session_id: str) -> Path:
    """Get session file path for user."""
    if not session_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    user_dir = SESSIONS_ROOT / user_id
    user_dir.mkdir(exist_ok=True)
    return user_dir / f"{session_id}.json"


def find_existing_session_path(session_id: str) -> Optional[Path]:
    """Find existing session file path."""
    if not session_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    if use_database_storage():
        return None
    for p in SESSIONS_ROOT.glob(f"*/{session_id}.json"):
        return p
    return None


def get_session_path_for_access(session_id: str, owner_user_id: Optional[str] = None) -> Path:
    """Get session path for access."""
    existing = find_existing_session_path(session_id)
    if existing:
        return existing
    if owner_user_id:
        return session_path_for_user(owner_user_id, session_id)
    raise HTTPException(status_code=404, detail="Session not found.")


def load_session_for_access(session_id: str) -> tuple[Optional[Path], Dict[str, Any]]:
    """Load session for access."""
    if use_database_storage():
        session = load_session_db(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        return None, session

    json_path = get_session_path_for_access(session_id)
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    with open(json_path, "r", encoding="utf-8") as fh:
        session = json.load(fh)
    return json_path, session


def save_loaded_session(session_path: Optional[Path], session: Dict[str, Any], owner_user_id: Optional[str] = None) -> None:
    """Save loaded session."""
    if use_database_storage():
        if owner_user_id and not session.get("owner_user_id"):
            session["owner_user_id"] = owner_user_id
        save_single_session_db(session)
        return

    target_path = session_path
    if not target_path:
        target_user_id = owner_user_id or session.get("owner_user_id")
        target_path = get_session_path_for_access(str(session.get("session_id", "")), owner_user_id=target_user_id)
    with open(target_path, "w", encoding="utf-8") as fh:
        json.dump(session, fh, indent=2, ensure_ascii=False)


def load_existing_session(session_id: str) -> tuple[Optional[Path], Optional[Dict[str, Any]]]:
    """Load existing session if it exists."""
    if use_database_storage():
        return None, load_session_db(session_id)

    existing_path = find_existing_session_path(session_id)
    if not existing_path or not existing_path.exists():
        return None, None
    try:
        with open(existing_path, "r", encoding="utf-8") as fh:
            return existing_path, json.load(fh)
    except Exception:
        return existing_path, None


def is_session_owner(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    """Check if user is session owner."""
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


def root_session_id(session: Dict[str, Any]) -> str:
    """Get root session ID."""
    return str(session.get("root_session_id") or session.get("session_id") or "").strip()


def can_approve_session(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    """Check if user can approve session."""
    # In v2 collaboration mode, only the owner can approve/unapprove suggestions.
    return is_session_owner(session, session_path, user)


def can_suggest_session(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    """Check if user can suggest in session."""
    # In v2 collaboration mode, only collaborators (non-owners) can add triple suggestions.
    return not is_session_owner(session, session_path, user)


def can_edit_session_directly(session: Dict[str, Any], session_path: Optional[Path], user: Dict[str, Any]) -> bool:
    """Check if user can edit session directly."""
    # Shared v2 rule: owner can vote/approve, but does not grade.
    return not is_session_owner(session, session_path, user)