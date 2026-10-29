"""
Re-exports the backend's rule for which triples enter the exported gold set, so the
evaluation code and the platform use the same rule.
"""

from typing import Any, Dict, List
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.services.adjudicated_gold import (
    include_in_adjudicated_gold,
    build_adjudicated_gold_set,
)

__all__ = ["include_in_adjudicated_gold", "build_adjudicated_gold_set"]
