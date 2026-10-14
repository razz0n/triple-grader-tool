#!/usr/bin/env python
"""Start the backend with Supabase database configured."""
import os
import sys
from pathlib import Path

# Load .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, val = line.split("=", 1)
                # Variables already set in the environment take precedence over .env.
                os.environ.setdefault(key.strip(), val.strip())
    print(f"Loaded environment from {env_path}")
    # Show only the scheme and host so credentials never reach the console or logs.
    _db_url = os.environ.get("DATABASE_URL", "")
    print(f"  DATABASE_URL: {_db_url.split('://', 1)[0] + '://...@' + _db_url.rsplit('@', 1)[-1] if '@' in _db_url else (_db_url.split('://', 1)[0] + '://...' if _db_url else 'NOT SET')}")
    print(f"  STORAGE_BACKEND: {os.environ.get('STORAGE_BACKEND', 'NOT SET')}")
    print()

# Change to backend directory
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

# Start the server
import uvicorn
uvicorn.run(
    "main:app",
    host="127.0.0.1",
    port=8000,
    reload=True,
)
