"""
local_backend.py — Runs the evaluation suites against an isolated local store.

The EQ1/EQ2 suites drive the FastAPI app in-process. Without isolation, the
backend would read backend/.env and could point at a hosted database. Call
use_isolated_local_storage() BEFORE importing backend modules, then
assert_local_storage() after importing them.
"""

import os
import tempfile
from pathlib import Path

_DB_DIR = Path(tempfile.gettempdir()) / "triplegrader_eval"


def use_isolated_local_storage() -> None:
    """Forces JSON session storage and a throwaway SQLite URL for this process."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["STORAGE_BACKEND"] = "json"
    os.environ["DATABASE_URL"] = f"sqlite:///{(_DB_DIR / 'eval.db').as_posix()}"


def assert_local_storage() -> None:
    """Stops the run if the imported backend is not using local storage."""
    import database  # backend/database.py, resolved through sys.path

    if database.use_database_storage() or not str(database.DATABASE_URL).startswith("sqlite"):
        raise RuntimeError("Evaluation suites must run against local storage, not a hosted database.")
