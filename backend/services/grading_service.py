"""
grading_service.py — Grading statistics and calculations for the Ontology Triple Grading Tool.

This module provides functions to calculate grading statistics, session averages,
and user activity metrics.
"""

from typing import Any, Dict, List, Optional

from .normalization import (
    normalize_grade_value,
    normalize_grades_by_user,
    normalize_sentence_metric_by_user,
    normalize_sentence_metric_value,
    normalize_sentence_comments,
)


def calculate_session_grading_stats(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate comprehensive grading statistics for a session.
    
    Args:
        session_data: The session data containing sentences and triples
        
    Returns:
        Dictionary containing grading statistics including:
        - total_triples: Total number of triples in the session
        - graded_triples: Number of triples that have been graded
        - session_average_grade: Average grade across all graded triples
        - is_completed_grading: Whether all triples have been graded
        - total_grade_entries: Total number of individual grade entries
        - total_unique_graders: Number of unique users who graded
        - completed_grader_count: Number of graders who graded all triples
        - grader_summary: List of per-grader statistics
    """
    total_triples = 0
    graded_triples = 0
    total_grade_entries = 0
    grade_sum = 0.0
    
    per_grader: Dict[str, Dict[str, Any]] = {}
    owner_fallback_user_id = str(session_data.get("owner_user_id") or "").strip()
    
    for sentence in session_data.get("sentences", []):
        for triple in sentence.get("triples", []):
            total_triples += 1
            
            grades_by_user = normalize_grades_by_user(
                triple.get("grades_by_user"),
                fallback_grade=triple.get("grade"),
                fallback_author=str(triple.get("author") or ""),
                fallback_user_id=owner_fallback_user_id,
                fallback_graded_at=triple.get("graded_at"),
            )
            
            # Update the triple with normalized grades
            triple["grades_by_user"] = grades_by_user
            
            if grades_by_user:
                graded_triples += 1
            
            for grader_id, grade_payload in grades_by_user.items():
                grade = normalize_grade_value(grade_payload.get("grade"))
                if grade is None:
                    continue
                
                total_grade_entries += 1
                grade_sum += float(grade)
                
                grader_summary = per_grader.setdefault(
                    grader_id,
                    {
                        "user_id": grader_id,
                        "user_name": str(grade_payload.get("user_name") or grader_id),
                        "graded_triples": 0,
                        "grade_count": 0,
                        "grade_sum": 0.0,
                        "average_grade": None,
                        "latest_graded_at": None,
                    },
                )
                grader_summary["graded_triples"] += 1
                grader_summary["grade_count"] += 1
                grader_summary["grade_sum"] += float(grade)
                
                graded_at = grade_payload.get("graded_at")
                latest = grader_summary.get("latest_graded_at")
                if graded_at and (not latest or str(graded_at) > str(latest)):
                    grader_summary["latest_graded_at"] = graded_at
    
    # Calculate per-grader averages
    grader_summary_rows: List[Dict[str, Any]] = []
    for item in per_grader.values():
        grade_count = int(item.get("grade_count") or 0)
        grade_sum_local = float(item.get("grade_sum") or 0.0)
        item["average_grade"] = round(grade_sum_local / grade_count, 2) if grade_count > 0 else None
        item.pop("grade_sum", None)
        grader_summary_rows.append(item)
    
    # Sort by graded triples (descending) then by name
    grader_summary_rows.sort(
        key=lambda row: (
            -(int(row.get("graded_triples") or 0)),
            str(row.get("user_name") or "").lower(),
        )
    )
    
    overall_avg = round(grade_sum / total_grade_entries, 2) if total_grade_entries > 0 else None
    is_completed = total_triples > 0 and graded_triples == total_triples
    completed_grader_count = sum(
        1
        for row in grader_summary_rows
        if total_triples > 0 and int(row.get("graded_triples") or 0) >= total_triples
    )
    
    return {
        "total_triples": total_triples,
        "graded_triples": graded_triples,
        "session_average_grade": overall_avg,
        "is_completed_grading": is_completed,
        "total_grade_entries": total_grade_entries,
        "total_unique_graders": len(grader_summary_rows),
        "completed_grader_count": completed_grader_count,
        "grader_summary": grader_summary_rows,
    }


def calculate_session_activity_for_user(
    session_data: Dict[str, Any],
    user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate user activity metrics for a session.
    
    Args:
        session_data: The session data
        user: The user to calculate activity for
        
    Returns:
        Dictionary containing user activity metrics
    """
    user_id = str(user.get("id") or "").strip()
    if not user_id:
        return {
            "my_has_activity": False,
            "my_graded_triples": 0,
            "my_sentence_metric_updates": 0,
            "my_sentence_comment_posts": 0,
            "my_total_actions": 0,
        }
    
    owner_fallback_user_id = str(session_data.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(session_data.get("owner_name") or "").strip()
    
    my_graded_triples = 0
    my_sentence_metric_updates = 0
    my_sentence_comment_posts = 0
    
    for sentence in session_data.get("sentences", []):
        # Check completeness metrics
        completeness_by_user = normalize_sentence_metric_by_user(
            sentence.get("completeness_by_user"),
            fallback_value=sentence.get("completeness"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("completeness_updated_at"),
        )
        my_completeness = completeness_by_user.get(user_id)
        if isinstance(my_completeness, dict) and normalize_sentence_metric_value(my_completeness.get("value")) is not None:
            my_sentence_metric_updates += 1
        
        # Check external relation metrics
        external_relation_by_user = normalize_sentence_metric_by_user(
            sentence.get("external_relation_by_user"),
            fallback_value=sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("external_relation_updated_at"),
        )
        my_external_relation = external_relation_by_user.get(user_id)
        if isinstance(my_external_relation, dict) and normalize_sentence_metric_value(my_external_relation.get("value")) is not None:
            my_sentence_metric_updates += 1
        
        # Check sentence comments
        sentence_comments = normalize_sentence_comments(sentence.get("sentence_comments"))
        my_sentence_comment_posts += sum(
            1
            for comment in sentence_comments
            if str(comment.get("user_id") or "").strip() == user_id
        )
        
        # Check triple grades
        for triple in sentence.get("triples", []):
            grades_by_user = normalize_grades_by_user(
                triple.get("grades_by_user"),
                fallback_grade=triple.get("grade"),
                fallback_author=str(triple.get("author") or ""),
                fallback_user_id=owner_fallback_user_id,
                fallback_graded_at=triple.get("graded_at"),
            )
            my_grade = grades_by_user.get(user_id)
            if isinstance(my_grade, dict) and normalize_grade_value(my_grade.get("grade")) is not None:
                my_graded_triples += 1
    
    my_total_actions = my_graded_triples + my_sentence_metric_updates + my_sentence_comment_posts
    
    return {
        "my_has_activity": my_total_actions > 0,
        "my_graded_triples": my_graded_triples,
        "my_sentence_metric_updates": my_sentence_metric_updates,
        "my_sentence_comment_posts": my_sentence_comment_posts,
        "my_total_actions": my_total_actions,
    }


def calculate_average(values: List[float]) -> Optional[float]:
    """
    Calculate the average of a list of values.
    
    Args:
        values: List of float values
        
    Returns:
        Average rounded to 2 decimal places, or None if list is empty
    """
    if not values:
        return None
    return round(sum(values) / len(values), 2)