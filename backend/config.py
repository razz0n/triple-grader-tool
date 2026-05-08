"""
config.py — Centralized configuration for the Ontology Triple Grading Tool.
"""

from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
SESSIONS_ROOT = STORAGE_DIR / "users"
USERS_FILE = STORAGE_DIR / "users.json"
TOKENS_FILE = STORAGE_DIR / "tokens.json"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

# Ensure storage directories exist
STORAGE_DIR.mkdir(exist_ok=True)
SESSIONS_ROOT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------

CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]

# ---------------------------------------------------------------------------
# Validation Patterns
# ---------------------------------------------------------------------------

import re

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,23}$")

# ---------------------------------------------------------------------------
# Grade Validation
# ---------------------------------------------------------------------------

GRADE_MIN = 0.0
GRADE_MAX = 10.0
GRADE_PRECISION = 2

# ---------------------------------------------------------------------------
# App Metadata
# ---------------------------------------------------------------------------

APP_TITLE = "Ontology Grading Tool"
APP_VERSION = "1.0.0"