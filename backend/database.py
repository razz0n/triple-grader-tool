"""
database.py - Optional database-backed persistence for users and auth tokens.

This module lets the app run in two modes:
- json (default): existing file-based storage
- database: SQLAlchemy tables (recommended for production)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import Column, String, Text, create_engine, select, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def _default_sqlite_url() -> str:
    base_dir = Path(__file__).parent
    return f"sqlite:///{(base_dir / 'storage' / 'app.db').as_posix()}"


# Load local .env manually if present
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    # Variables already set in the environment (deployment settings, test
                    # harnesses) take precedence over the local .env file.
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

DATABASE_URL = os.getenv("DATABASE_URL", _default_sqlite_url())
_STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "json").strip().lower()

# Convert postgresql:// to postgresql+psycopg:// for SQLAlchemy to use psycopg v3
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# SQLite needs check_same_thread=False when used from FastAPI workers.
_CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_recycle=60,
    connect_args=_CONNECT_ARGS
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class UserRecord(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    username = Column(String(64), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_salt = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(String(64), nullable=False)
    security_question = Column(String(255), nullable=True)
    security_answer = Column(String(255), nullable=True)


class TokenRecord(Base):
    __tablename__ = "tokens"

    token = Column(Text, primary_key=True)
    user_id = Column(String(64), nullable=False)
    created_at = Column(String(64), nullable=False)
    last_active_at = Column(String(64), nullable=True)


class SessionRecord(Base):
    __tablename__ = "sessions"

    session_id = Column(String(64), primary_key=True)
    owner_user_id = Column(String(64), nullable=True)
    source_filename = Column(String(255), nullable=False)
    uploaded_at = Column(String(64), nullable=False)
    payload_json = Column(Text, nullable=False)


def use_database_storage() -> bool:
    return _STORAGE_BACKEND == "database"


def init_database(
    users_json_path: Path | None = None,
    tokens_json_path: Path | None = None,
    sessions_root: Path | None = None,
) -> None:
    """Create DB tables and optionally bootstrap from existing JSON files."""
    if not use_database_storage():
        return

    Base.metadata.create_all(bind=engine)

    # Check and run database migrations if columns are missing
    try:
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("users")]
        if "security_question" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN security_question VARCHAR(255)"))
        if "security_answer" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN security_answer VARCHAR(255)"))
        
        # Check and migrate tokens table for last_active_at column
        token_columns = [c["name"] for c in inspector.get_columns("tokens")]
        if "last_active_at" not in token_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE tokens ADD COLUMN last_active_at VARCHAR(64)"))
    except Exception as e:
        print("Migration error:", e)

    with SessionLocal() as db:
        has_users = db.scalar(select(UserRecord.id).limit(1)) is not None
        has_tokens = db.scalar(select(TokenRecord.token).limit(1)) is not None
        has_sessions = db.scalar(select(SessionRecord.session_id).limit(1)) is not None

    if not has_users and users_json_path and users_json_path.exists():
        try:
            with open(users_json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            save_users_db(data if isinstance(data, dict) else {"users": []})
        except Exception:
            pass

    if not has_tokens and tokens_json_path and tokens_json_path.exists():
        try:
            with open(tokens_json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            save_tokens_db(data if isinstance(data, dict) else {"tokens": {}})
        except Exception:
            pass

    if not has_sessions and sessions_root and sessions_root.exists():
        try:
            session_files = sorted(sessions_root.glob("*/*.json"))
            for p in session_files:
                with open(p, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)

                session_id = str(payload.get("session_id") or p.stem)
                owner_user_id = str(payload.get("owner_user_id") or p.parent.name)
                source_filename = str(payload.get("source_filename") or "unknown")
                uploaded_at = str(payload.get("uploaded_at") or "")
                save_single_session_db(
                    {
                        "session_id": session_id,
                        "owner_user_id": owner_user_id,
                        "source_filename": source_filename,
                        "uploaded_at": uploaded_at,
                        **payload,
                    }
                )
        except Exception:
            pass


def load_users_db() -> Dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(select(UserRecord)).scalars().all()
    users = [
        {
            "id": row.id,
            "username": row.username,
            "name": row.name,
            "email": row.email,
            "password_salt": row.password_salt,
            "password_hash": row.password_hash,
            "created_at": row.created_at,
            "security_question": row.security_question,
            "security_answer": row.security_answer,
        }
        for row in rows
    ]
    return {"users": users}


def save_users_db(users_data: Dict[str, Any]) -> None:
    """Bulk-upsert all users from a dict; rows for IDs not in the list are deleted."""
    users = users_data.get("users", []) if isinstance(users_data, dict) else []
    incoming_ids = {str(u.get("id", "")) for u in users if u.get("id")}
    with SessionLocal() as db:
        # Remove rows whose IDs are no longer present
        if incoming_ids:
            db.query(UserRecord).filter(UserRecord.id.notin_(incoming_ids)).delete(synchronize_session=False)
        else:
            db.query(UserRecord).delete(synchronize_session=False)
        # Upsert each incoming user
        for user in users:
            _upsert_user(db, user)
        db.commit()


def upsert_user_db(user_dict: Dict[str, Any]) -> None:
    """Upsert a single user record (used for registration / profile updates)."""
    with SessionLocal() as db:
        _upsert_user(db, user_dict)
        db.commit()


def _upsert_user(db, user: Dict[str, Any]) -> None:
    uid = str(user.get("id", "")).strip()
    if not uid:
        return
    row = db.get(UserRecord, uid)
    if row:
        row.username = user.get("username")
        row.name = str(user.get("name", ""))
        row.email = str(user.get("email", ""))
        row.password_salt = str(user.get("password_salt", ""))
        row.password_hash = str(user.get("password_hash", ""))
        row.created_at = str(user.get("created_at", ""))
        row.security_question = user.get("security_question")
        row.security_answer = user.get("security_answer")
    else:
        db.add(UserRecord(
            id=uid,
            username=user.get("username"),
            name=str(user.get("name", "")),
            email=str(user.get("email", "")),
            password_salt=str(user.get("password_salt", "")),
            password_hash=str(user.get("password_hash", "")),
            created_at=str(user.get("created_at", "")),
            security_question=user.get("security_question"),
            security_answer=user.get("security_answer"),
        ))


def load_tokens_db() -> Dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(select(TokenRecord)).scalars().all()
    return {
        "tokens": {
            row.token: {
                "user_id": row.user_id,
                "created_at": row.created_at,
                "last_active_at": row.last_active_at,
            }
            for row in rows
        }
    }


def save_tokens_db(tokens_data: Dict[str, Any]) -> None:
    """Bulk-upsert all tokens from a dict; tokens not in the list are deleted."""
    tokens = tokens_data.get("tokens", {}) if isinstance(tokens_data, dict) else {}
    incoming_keys = set(tokens.keys())
    with SessionLocal() as db:
        # Remove tokens no longer present
        if incoming_keys:
            db.query(TokenRecord).filter(TokenRecord.token.notin_(incoming_keys)).delete(synchronize_session=False)
        else:
            db.query(TokenRecord).delete(synchronize_session=False)
        # Upsert each incoming token
        for token, payload in tokens.items():
            _upsert_token(db, token, payload)
        db.commit()


def add_token_db(token: str, user_id: str, created_at: str, last_active_at: str | None = None) -> None:
    """Insert a single new auth token (used right after login/register)."""
    with SessionLocal() as db:
        _upsert_token(db, token, {"user_id": user_id, "created_at": created_at, "last_active_at": last_active_at})
        db.commit()


def delete_token_db(token: str) -> None:
    """Delete a single token (used on logout)."""
    with SessionLocal() as db:
        db.query(TokenRecord).filter(TokenRecord.token == token).delete(synchronize_session=False)
        db.commit()


def _upsert_token(db, token: str, payload: Dict[str, Any]) -> None:
    row = db.get(TokenRecord, token)
    if row:
        row.user_id = str(payload.get("user_id", ""))
        row.created_at = str(payload.get("created_at", ""))
        row.last_active_at = payload.get("last_active_at")
    else:
        db.add(TokenRecord(
            token=str(token),
            user_id=str(payload.get("user_id", "")),
            created_at=str(payload.get("created_at", "")),
            last_active_at=payload.get("last_active_at"),
        ))


def update_token_activity_db(token: str, last_active_at: str) -> None:
    """Update only the last_active_at timestamp for a token."""
    with SessionLocal() as db:
        row = db.get(TokenRecord, token)
        if row:
            row.last_active_at = last_active_at
            db.commit()


def load_session_db(session_id: str) -> Dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.get(SessionRecord, session_id)
    if not row:
        return None
    payload = json.loads(row.payload_json)
    if not payload.get("session_id"):
        payload["session_id"] = row.session_id
    if not payload.get("owner_user_id") and row.owner_user_id:
        payload["owner_user_id"] = row.owner_user_id
    if not payload.get("source_filename"):
        payload["source_filename"] = row.source_filename
    if not payload.get("uploaded_at"):
        payload["uploaded_at"] = row.uploaded_at
    return payload


def list_sessions_db() -> list[Dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(select(SessionRecord)).scalars().all()
    sessions: list[Dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row.payload_json)
        payload.setdefault("session_id", row.session_id)
        payload.setdefault("owner_user_id", row.owner_user_id)
        payload.setdefault("source_filename", row.source_filename)
        payload.setdefault("uploaded_at", row.uploaded_at)
        sessions.append(payload)
    return sessions


def save_single_session_db(session_data: Dict[str, Any]) -> None:
    session_id = str(session_data.get("session_id", "")).strip()
    if not session_id:
        raise ValueError("session_id is required")

    owner_user_id = session_data.get("owner_user_id")
    source_filename = str(session_data.get("source_filename") or "unknown")
    uploaded_at = str(session_data.get("uploaded_at") or "")
    payload_json = json.dumps(session_data, ensure_ascii=False)

    with SessionLocal() as db:
        existing = db.get(SessionRecord, session_id)
        if existing:
            existing.owner_user_id = str(owner_user_id or existing.owner_user_id or "") or None
            existing.source_filename = source_filename
            existing.uploaded_at = uploaded_at
            existing.payload_json = payload_json
        else:
            db.add(
                SessionRecord(
                    session_id=session_id,
                    owner_user_id=str(owner_user_id) if owner_user_id is not None else None,
                    source_filename=source_filename,
                    uploaded_at=uploaded_at,
                    payload_json=payload_json,
                )
            )
        db.commit()


def delete_sessions_db(session_ids: list[str]) -> int:
    """Delete multiple saved sessions by session_id and return deleted row count."""
    normalized_ids = [str(session_id).strip() for session_id in session_ids if str(session_id).strip()]
    if not normalized_ids:
        return 0

    with SessionLocal() as db:
        deleted = (
            db.query(SessionRecord)
            .filter(SessionRecord.session_id.in_(normalized_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
    return int(deleted)


def delete_session_db(session_id: str) -> None:
    """Delete a single saved session by session_id."""
    delete_sessions_db([session_id])
