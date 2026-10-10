"""
canonicalize.py — String and Triple Canonicalization Utilities.

Normalizes triple text representations for rigorous exact and normalized matching.
"""

import re
from typing import Any, Dict, Tuple


def normalize_token(text: Any) -> str:
    """Normalize a single token or string (casing, whitespace, underscores)."""
    if text is None:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[\s_]+", "_", s)
    s = re.sub(r"[^\w\-]", "", s)
    return s.strip("_")


def canonicalize_triple(triple: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extract and canonicalize (subject, predicate, object) tuple from a triple dict."""
    s = normalize_token(triple.get("subject", ""))
    p = normalize_token(triple.get("predicate", ""))
    o = normalize_token(triple.get("object", ""))
    return (s, p, o)


def exact_triple_tuple(triple: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extract exact trimmed strings without normalization for strict exact matching."""
    s = str(triple.get("subject") or "").strip()
    p = str(triple.get("predicate") or "").strip()
    o = str(triple.get("object") or "").strip()
    return (s, p, o)
