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

from sqlalchemy import Column, String, Text, create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def _default_sqlite_url() -> str:
    base_dir = Path(__file__).parent
    return f"sqlite:///{(base_dir / 'storage' / 'app.db').as_posix()}"


DATABASE_URL = os.getenv("DATABASE_URL", _default_sqlite_url())
_STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "json").strip().lower()

# SQLite needs check_same_thread=False when used from FastAPI workers.
_CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True, connect_args=_CONNECT_ARGS)
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


class TokenRecord(Base):
    __tablename__ = "tokens"

    token = Column(Text, primary_key=True)
    user_id = Column(String(64), nullable=False)
    created_at = Column(String(64), nullable=False)


def use_database_storage() -> bool:
    return _STORAGE_BACKEND == "database"


def init_database(users_json_path: Path | None = None, tokens_json_path: Path | None = None) -> None:
    """Create DB tables and optionally bootstrap from existing JSON files."""
    if not use_database_storage():
        return

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        has_users = db.scalar(select(UserRecord.id).limit(1)) is not None
        has_tokens = db.scalar(select(TokenRecord.token).limit(1)) is not None

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
        }
        for row in rows
    ]
    return {"users": users}


def save_users_db(users_data: Dict[str, Any]) -> None:
    users = users_data.get("users", []) if isinstance(users_data, dict) else []
    with SessionLocal() as db:
        db.query(UserRecord).delete()
        for user in users:
            db.add(
                UserRecord(
                    id=str(user.get("id", "")),
                    username=user.get("username"),
                    name=str(user.get("name", "")),
                    email=str(user.get("email", "")),
                    password_salt=str(user.get("password_salt", "")),
                    password_hash=str(user.get("password_hash", "")),
                    created_at=str(user.get("created_at", "")),
                )
            )
        db.commit()


def load_tokens_db() -> Dict[str, Any]:
    with SessionLocal() as db:
        rows = db.execute(select(TokenRecord)).scalars().all()
    return {
        "tokens": {
            row.token: {
                "user_id": row.user_id,
                "created_at": row.created_at,
            }
            for row in rows
        }
    }


def save_tokens_db(tokens_data: Dict[str, Any]) -> None:
    tokens = tokens_data.get("tokens", {}) if isinstance(tokens_data, dict) else {}
    with SessionLocal() as db:
        db.query(TokenRecord).delete()
        for token, payload in tokens.items():
            db.add(
                TokenRecord(
                    token=str(token),
                    user_id=str(payload.get("user_id", "")),
                    created_at=str(payload.get("created_at", "")),
                )
            )
        db.commit()
