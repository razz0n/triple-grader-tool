"""
normalization.py — Data normalization utilities for the Ontology Triple Grading Tool.

This module provides functions to normalize and validate grades, metrics, and comments
from various input formats, ensuring consistent data structures across the application.
"""

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import GRADE_MAX, GRADE_MIN, GRADE_PRECISION


def normalize_grade_value(value: Any) -> Optional[float]:
    """
    Normalize a grade value to a float within the valid range.
    
    Args:
        value: The grade value to normalize (can be string, int, float, or None)
        
    Returns:
        Normalized grade as float, or None if invalid
    """
    if value is None or value == "":
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    
    if numeric < GRADE_MIN or numeric > GRADE_MAX:
        return None
    
    if numeric.is_integer():
        return float(int(numeric))
    
    return round(numeric, GRADE_PRECISION)


def normalize_grades_by_user(
    raw_grades: Any,
    *,
    fallback_grade: Any = None,
    fallback_author: str = "",
    fallback_user_id: str = "",
    fallback_graded_at: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Normalize grades from multiple users into a consistent format.
    
    Args:
        raw_grades: Raw grades data (dict of user_id -> grade payload)
        fallback_grade: Legacy grade value to use if raw_grades is empty
        fallback_author: Author name for legacy grade
        fallback_user_id: User ID for legacy grade
        fallback_graded_at: Timestamp for legacy grade
        
    Returns:
        Dictionary mapping user_id to normalized grade payload
    """
    normalized: Dict[str, Dict[str, Any]] = {}
    
    if isinstance(raw_grades, dict):
        for key, payload in raw_grades.items():
            if not isinstance(payload, dict):
                continue
            
            grade = normalize_grade_value(payload.get("grade"))
            if grade is None:
                continue
            
            user_id = str(payload.get("user_id") or key or "").strip()
            if not user_id:
                continue
            
            user_name = str(payload.get("user_name") or user_id).strip() or user_id
            
            normalized[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "grade": grade,
                "graded_at": payload.get("graded_at"),
            }
    
    if normalized:
        return normalized
    
    # Fallback to legacy grade format
    legacy_grade = normalize_grade_value(fallback_grade)
    if legacy_grade is None:
        return normalized
    
    legacy_name = str(fallback_author or "Legacy grader").strip() or "Legacy grader"
    legacy_id = str(fallback_user_id or "").strip()
    
    if not legacy_id:
        slug = re.sub(r"[^a-z0-9_]+", "_", legacy_name.lower()).strip("_") or "grader"
        legacy_id = f"legacy_{slug}"
    
    normalized[legacy_id] = {
        "user_id": legacy_id,
        "user_name": legacy_name,
        "grade": legacy_grade,
        "graded_at": fallback_graded_at,
    }
    
    return normalized


def normalize_sentence_metric_value(value: Any) -> Optional[float]:
    """
    Normalize a sentence-level metric value (completeness, external_relation).
    
    This is currently an alias for normalize_grade_value but provides
    semantic clarity for sentence-level metrics.
    """
    return normalize_grade_value(value)


def normalize_sentence_metric_by_user(
    raw_metrics: Any,
    *,
    fallback_value: Any = None,
    fallback_user_id: str = "",
    fallback_user_name: str = "",
    fallback_updated_at: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Normalize sentence-level metrics from multiple users.
    
    Args:
        raw_metrics: Raw metrics data (dict of user_id -> metric payload)
        fallback_value: Legacy metric value to use if raw_metrics is empty
        fallback_user_id: User ID for legacy metric
        fallback_user_name: User name for legacy metric
        fallback_updated_at: Timestamp for legacy metric
        
    Returns:
        Dictionary mapping user_id to normalized metric payload
    """
    normalized: Dict[str, Dict[str, Any]] = {}
    
    if isinstance(raw_metrics, dict):
        for key, payload in raw_metrics.items():
            if not isinstance(payload, dict):
                continue
            
            value = normalize_sentence_metric_value(payload.get("value"))
            if value is None:
                continue
            
            user_id = str(payload.get("user_id") or key or "").strip()
            if not user_id:
                continue
            
            user_name = str(payload.get("user_name") or user_id).strip() or user_id
            
            normalized[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "value": value,
                "updated_at": payload.get("updated_at"),
            }
    
    if normalized:
        return normalized
    
    # Fallback to legacy metric format
    fallback_metric = normalize_sentence_metric_value(fallback_value)
    if fallback_metric is None:
        return normalized
    
    metric_user_name = str(fallback_user_name or "Legacy grader").strip() or "Legacy grader"
    metric_user_id = str(fallback_user_id or "").strip()
    
    if not metric_user_id:
        slug = re.sub(r"[^a-z0-9_]+", "_", metric_user_name.lower()).strip("_") or "grader"
        metric_user_id = f"legacy_{slug}"
    
    normalized[metric_user_id] = {
        "user_id": metric_user_id,
        "user_name": metric_user_name,
        "value": fallback_metric,
        "updated_at": fallback_updated_at,
    }
    
    return normalized


def normalize_sentence_comments(
    raw_comments: Any,
    *,
    fallback_text: str = "",
    fallback_author: str = "",
    fallback_user_id: str = "",
    fallback_created_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Normalize sentence comments into a consistent format.
    
    Args:
        raw_comments: Raw comments data (list of comment payloads)
        fallback_text: Legacy comment text to use if raw_comments is empty
        fallback_author: Author name for legacy comment
        fallback_user_id: User ID for legacy comment
        fallback_created_at: Timestamp for legacy comment
        
    Returns:
        List of normalized comment dictionaries, sorted by created_at
    """
    normalized: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    
    if isinstance(raw_comments, list):
        for idx, payload in enumerate(raw_comments):
            if not isinstance(payload, dict):
                continue
            
            text = str(payload.get("text") or payload.get("comment") or "").strip()
            if not text:
                continue
            
            comment_id = str(payload.get("id") or "").strip()
            if not comment_id:
                comment_id = f"comment_{idx}_{hashlib.sha1(str(idx).encode()).hexdigest()[:8]}"
            
            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)
            
            user_id = str(payload.get("user_id") or payload.get("author_user_id") or "").strip()
            author = str(payload.get("author") or payload.get("user_name") or "").strip()
            if not author:
                author = user_id or "User"
            
            created_at = payload.get("created_at")
            if created_at is None:
                created_at = payload.get("posted_at")
            if created_at is None:
                created_at = fallback_created_at or datetime.utcnow().isoformat()
            
            normalized.append({
                "id": comment_id,
                "user_id": user_id,
                "author": author,
                "text": text,
                "created_at": created_at,
            })
    
    if not normalized:
        # Fallback to legacy comment format
        legacy_text = str(fallback_text or "").strip()
        if legacy_text:
            legacy_author = str(fallback_author or "Legacy comment").strip() or "Legacy comment"
            legacy_user_id = str(fallback_user_id or "").strip()
            legacy_hash = hashlib.sha1(legacy_text.encode("utf-8")).hexdigest()[:10]
            
            normalized.append({
                "id": f"legacy_comment_{legacy_hash}",
                "user_id": legacy_user_id,
                "author": legacy_author,
                "text": legacy_text,
                "created_at": fallback_created_at or datetime.utcnow().isoformat(),
            })
    
    # Sort by creation time
    normalized.sort(key=lambda row: str(row.get("created_at") or ""))
    
    return normalized