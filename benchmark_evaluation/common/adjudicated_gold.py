"""
adjudicated_gold.py — Centralized gold-standard adjudication membership criteria.

Defines the authoritative predicate determining whether a candidate ontology triple belongs
to the adjudicated gold benchmark based on consensus grading, reviewer approval thresholds,
and curator decisions. Serves as the single source of truth across all empirical evaluation pipelines.
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
