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
                os.environ[key] = val
    print(f"Loaded environment from {env_path}")
    print(f"  DATABASE_URL: {os.environ.get('DATABASE_URL', 'NOT SET')[:50]}...")
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
