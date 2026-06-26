"""
auth.py — Authentication and user management for the Ontology Triple Grading Tool.
"""

import hashlib
import secrets
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import (
    add_token_db,
    delete_token_db,
    load_tokens_db,
    load_users_db,
    save_tokens_db,
    save_users_db,
    upsert_user_db,
    use_database_storage,
)
from utils import display_name, load_json, norm_email, norm_username, save_json

# Constants
DEFAULT_USERS = [
    {"username": "user_ysh", "name": "user_ysh", "email": "user_ysh@example.com", "password": "psd_ysh_psd"},
    {"username": "user_jw", "name": "user_jw", "email": "user_jw@example.com", "password": "psd_jw_psd"},
    {"username": "user_rl", "name": "user_rl", "email": "user_rl@example.com", "password": "psd_rl_psd"},
    {"username": "user_ab", "name": "user_ab", "email": "user_ab@example.com", "password": "psd_ab_psd"},
    {"username": "user_cd", "name": "user_cd", "email": "user_cd@example.com", "password": "psd_cd_psd"},
]

# File paths
STORAGE_DIR = Path(__file__).parent / "storage"
USERS_FILE = STORAGE_DIR / "users.json"
TOKENS_FILE = STORAGE_DIR / "tokens.json"
_AUTH_SCHEME = HTTPBearer(auto_error=False)


def hash_password(password: str, salt_hex: Optional[str] = None) -> Dict[str, str]:
    """Hash password with PBKDF2."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260000)
    return {"salt": salt.hex(), "hash": dk.hex()}


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """Verify password against hash."""
    computed = hash_password(password, salt_hex=salt_hex)["hash"]
    return secrets.compare_digest(computed, hash_hex)


def load_users() -> Dict[str, Any]:
    """Load users from storage."""
    if use_database_storage():
        users = load_users_db()
        if "users" not in users:
            users = {"users": []}
        return users

    users = load_json(USERS_FILE, {"users": []})
    if "users" not in users:
        users = {"users": []}
    return users


def save_users(users: Dict[str, Any]):
    """Save users to storage."""
    if use_database_storage():
        save_users_db(users)
        return
    save_json(USERS_FILE, users)


def load_tokens() -> Dict[str, Any]:
    """Load tokens from storage."""
    if use_database_storage():
        tokens = load_tokens_db()
        if "tokens" not in tokens:
            tokens = {"tokens": {}}
        return tokens

    tokens = load_json(TOKENS_FILE, {"tokens": {}})
    if "tokens" not in tokens:
        tokens = {"tokens": {}}
    return tokens


def save_tokens(tokens: Dict[str, Any]):
    """Save tokens to storage."""
    if use_database_storage():
        save_tokens_db(tokens)
        return
    save_json(TOKENS_FILE, tokens)


def make_unique_username(base_username: str, users: list) -> str:
    """Generate unique username."""
    from utils import norm_username
    base = norm_username(base_username) or "user"
    existing = {norm_username(user.get("username", "")) for user in users}
    if base not in existing:
        return base
    suffix = 2
    while f"{base}_{suffix}" in existing:
        suffix += 1
    return f"{base}_{suffix}"


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Find user by email."""
    users = load_users()["users"]
    target = norm_email(email)
    for user in users:
        if user.get("email") == target:
            return user
    return None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Find user by username."""
    users = load_users()["users"]
    target = norm_username(username)
    for user in users:
        if norm_username(user.get("username", "")) == target:
            return user
    return None


def find_user_for_login(login_value: str) -> Optional[Dict[str, Any]]:
    """Find user for login (by email or username)."""
    identifier = login_value.strip()
    if not identifier:
        return None
    if "@" in identifier:
        by_email = get_user_by_email(identifier)
        if by_email:
            return by_email
    by_username = get_user_by_username(identifier)
    if by_username:
        return by_username
    return get_user_by_email(identifier)


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Find user by ID."""
    users = load_users()["users"]
    for user in users:
        if user.get("id") == user_id:
            return user
    return None


def issue_token(user_id: str) -> str:
    """Issue new authentication token."""
    token = secrets.token_urlsafe(40)
    created_at = datetime.utcnow().isoformat()
    if use_database_storage():
        add_token_db(token, user_id, created_at, created_at)
    else:
        tokens = load_tokens()
        tokens["tokens"][token] = {"user_id": user_id, "created_at": created_at, "last_active_at": created_at}
        save_tokens(tokens)
    return token


def user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Get user from token."""
    tokens = load_tokens()["tokens"]
    token_data = tokens.get(token)
    if not token_data:
        return None
    return get_user_by_id(token_data.get("user_id", ""))


def update_token_activity(token: str, last_active_at: str):
    """Update a token's last active time in DB or JSON file."""
    if use_database_storage():
        from database import update_token_activity_db
        update_token_activity_db(token, last_active_at)
    else:
        tokens = load_tokens()
        if token in tokens["tokens"]:
            tokens["tokens"][token]["last_active_at"] = last_active_at
            save_tokens(tokens)


def validate_and_update_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate token, enforce 6-hour inactivity limit, and update activity timestamp."""
    tokens = load_tokens()["tokens"]
    token_data = tokens.get(token)
    if not token_data:
        return None

    last_active_str = token_data.get("last_active_at") or token_data.get("created_at")
    now = datetime.utcnow()
    
    if last_active_str:
        try:
            last_active = datetime.fromisoformat(last_active_str)
            elapsed = (now - last_active).total_seconds()
            if elapsed > 21600:  # 6 hours
                revoke_token(token)
                return None
        except Exception:
            pass

    update_token_activity(token, now.isoformat())
    return get_user_by_id(token_data.get("user_id", ""))


def revoke_token(token: str):
    """Revoke authentication token."""
    if use_database_storage():
        delete_token_db(token)
    else:
        tokens = load_tokens()
        if token in tokens["tokens"]:
            del tokens["tokens"][token]
            save_tokens(tokens)


async def current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_AUTH_SCHEME),
) -> Dict[str, Any]:
    """Get current authenticated user from Bearer token."""
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = validate_and_update_token(creds.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


def current_user_from_bearer_or_query(request: Request, token_qs: Optional[str]) -> Dict[str, Any]:
    """Get current user from Bearer token or query parameter."""
    token = token_qs
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = validate_and_update_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user


def ensure_default_users():
    """Ensure default users exist in the system."""
    users_data = load_users()
    users = users_data.get("users", [])
    changed = False

    for seed in DEFAULT_USERS:
        email = norm_email(seed["email"])
        username = norm_username(seed["username"])
        existing = next((u for u in users if norm_email(u.get("email", "")) == email), None)

        if existing:
            if not existing.get("username"):
                existing["username"] = username
                changed = True
            continue

        if any(norm_username(u.get("username", "")) == username for u in users):
            continue

        hashed = hash_password(seed["password"])
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
        save_users(users_data)