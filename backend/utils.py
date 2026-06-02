"""
utils.py — Utility functions for the Ontology Triple Grading Tool.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,23}$")


def load_json(path: Path, default: Any):
    """Load JSON data from file, return default if file doesn't exist or is invalid."""
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_json(path: Path, data: Any):
    """Save data as JSON to file with atomic write."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())  # Force write to disk immediately


def norm_email(email: str) -> str:
    """Normalize email address."""
    return email.strip().lower()


def norm_username(username: str) -> str:
    """Normalize username."""
    return username.strip().lower()


def is_valid_username(username: str) -> bool:
    """Check if username is valid."""
    return bool(USERNAME_PATTERN.fullmatch(norm_username(username)))


def display_name(user: Dict[str, Any]) -> str:
    """Get display name for user."""
    name = (user.get("name") or "").strip()
    if name:
        return name
    email = user.get("email", "")
    local = email.split("@", 1)[0] if "@" in email else "User"
    return local or "User"