"""
session_service.py — Session management business logic for the Ontology Triple Grading Tool.

This module provides functions for session view projection, collaborative grading,
and session data transformation.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from utils import display_name, norm_email, norm_username
from .grading_service import calculate_average, calculate_session_grading_stats
from .normalization import (
    normalize_grade_value,
    normalize_grades_by_user,
    normalize_sentence_comments,
    normalize_sentence_metric_by_user,
    normalize_sentence_metric_value,
)


def sentence_groups_to_draft_sentences(sentence_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert parser sentence groups into a saved draft sentence list.
    
    Args:
        sentence_groups: List of sentence groups from the parser
        
    Returns:
        List of sentence dictionaries ready for grading
    """
    sentences: List[Dict[str, Any]] = []
    sentence_id = 1
    
    for group in sentence_groups:
        versions = group.get("versions") or []
        selected_version_id = str(group.get("selected_version_id") or "").strip()
        
        selected_version = next(
            (v for v in versions if str(v.get("version_id") or "").strip() == selected_version_id),
            None,
        )
        if not selected_version and versions:
            selected_version = versions[0]
        
        raw_triples = selected_version.get("triples", []) if isinstance(selected_version, dict) else []
        triples: List[Dict[str, Any]] = []
        
        for idx, triple in enumerate(raw_triples, start=1):
            subject = str(triple.get("subject") or "").strip()
            predicate = str(triple.get("predicate") or "").strip()
            obj = str(triple.get("object") or "").strip()
            if not (subject and predicate and obj):
                continue
            
            triple_id = str(triple.get("id") or f"{sentence_id}_{idx}")
            triples.append({
                "id": triple_id,
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "grade": None,
            })
        
        if not triples:
            continue
        
        sentence_text = str(group.get("sentence_text") or "").strip()
        if not sentence_text and isinstance(selected_version, dict):
            sentence_text = str(selected_version.get("sentence_candidate") or "").strip()
        
        sentences.append({
            "id": sentence_id,
            "text": sentence_text or "(no sentence text)",
            "suggestion": "",
            "sentence_comments": [],
            "comment_count": 0,
            "sentence_grade": None,
            "completeness": None,
            "external_relation": None,
            "triples": triples,
        })
        sentence_id += 1
    
    return sentences


def apply_collaborative_grades(
    incoming_session: Dict[str, Any],
    existing_session: Optional[Dict[str, Any]],
    user: Dict[str, Any],
) -> None:
    """
    Apply collaborative grading logic to merge user grades with existing session data.
    
    Args:
        incoming_session: The session data from the client
        existing_session: The existing session data from storage (if any)
        user: The current user
    """
    user_id = str(user.get("id") or "").strip()
    user_name = display_name(user)
    now_iso = datetime.utcnow().isoformat()
    user_can_grade = not is_session_owner(existing_session or incoming_session, None, user)
    
    existing_sentences = {
        s.get("id"): s
        for s in (existing_session or {}).get("sentences", [])
        if s.get("id") is not None
    }
    owner_fallback_user_id = str((existing_session or {}).get("owner_user_id") or "").strip()
    owner_fallback_user_name = str((existing_session or {}).get("owner_name") or "").strip()
    
    for sentence in incoming_session.get("sentences", []):
        existing_sentence = existing_sentences.get(sentence.get("id"))
        
        # Process completeness metric
        existing_completeness = normalize_sentence_metric_by_user(
            (existing_sentence or {}).get("completeness_by_user"),
            fallback_value=(existing_sentence or {}).get("completeness"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=(existing_sentence or {}).get("completeness_updated_at"),
        )
        incoming_completeness = normalize_sentence_metric_by_user(
            sentence.get("completeness_by_user"),
            fallback_value=sentence.get("completeness"),
            fallback_user_id=user_id,
            fallback_user_name=user_name,
            fallback_updated_at=sentence.get("completeness_updated_at"),
        )
        merged_completeness = dict(existing_completeness)
        for metric_user_id, payload in incoming_completeness.items():
            if metric_user_id not in merged_completeness:
                merged_completeness[metric_user_id] = payload
        
        my_completeness = normalize_sentence_metric_value(sentence.get("completeness"))
        if not user_can_grade:
            merged_completeness.pop(user_id, None)
            sentence["completeness"] = None
            sentence.pop("completeness_updated_at", None)
        elif my_completeness is None:
            merged_completeness.pop(user_id, None)
            sentence["completeness"] = None
            sentence.pop("completeness_updated_at", None)
        else:
            merged_completeness[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "value": my_completeness,
                "updated_at": now_iso,
            }
            sentence["completeness"] = my_completeness
            sentence["completeness_updated_at"] = now_iso
        sentence["completeness_by_user"] = merged_completeness
        
        # Process external relation metric
        existing_external = normalize_sentence_metric_by_user(
            (existing_sentence or {}).get("external_relation_by_user"),
            fallback_value=(existing_sentence or {}).get("external_relation"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=(existing_sentence or {}).get("external_relation_updated_at"),
        )
        incoming_external = normalize_sentence_metric_by_user(
            sentence.get("external_relation_by_user"),
            fallback_value=sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation"),
            fallback_user_id=user_id,
            fallback_user_name=user_name,
            fallback_updated_at=sentence.get("external_relation_updated_at"),
        )
        merged_external = dict(existing_external)
        for metric_user_id, payload in incoming_external.items():
            if metric_user_id not in merged_external:
                merged_external[metric_user_id] = payload
        
        my_external = normalize_sentence_metric_value(
            sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation")
        )
        if not user_can_grade:
            merged_external.pop(user_id, None)
            sentence["external_relation"] = None
            sentence.pop("external_relation_updated_at", None)
        elif my_external is None:
            merged_external.pop(user_id, None)
            sentence["external_relation"] = None
            sentence.pop("external_relation_updated_at", None)
        else:
            merged_external[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "value": my_external,
                "updated_at": now_iso,
            }
            sentence["external_relation"] = my_external
            sentence["external_relation_updated_at"] = now_iso
        sentence["external_relation_by_user"] = merged_external
        
        # Process triple grades
        existing_triples = {
            t.get("id"): t
            for t in (existing_sentence or {}).get("triples", [])
            if t.get("id") is not None
        }
        
        for triple in sentence.get("triples", []):
            triple_id = triple.get("id")
            existing_triple = existing_triples.get(triple_id, {})
            
            if existing_triple:
                # Triple text and suggestion threads are collaborative shared state;
                # preserve the latest server copy to avoid stale client overwrites.
                triple["subject"] = existing_triple.get("subject", triple.get("subject"))
                triple["predicate"] = existing_triple.get("predicate", triple.get("predicate"))
                triple["object"] = existing_triple.get("object", triple.get("object"))
                if isinstance(existing_triple.get("suggestions"), list):
                    triple["suggestions"] = existing_triple.get("suggestions", [])
            
            existing_grades = normalize_grades_by_user(
                existing_triple.get("grades_by_user"),
                fallback_grade=existing_triple.get("grade"),
                fallback_author=str(existing_triple.get("author") or ""),
                fallback_user_id=owner_fallback_user_id,
                fallback_graded_at=existing_triple.get("graded_at"),
            )
            incoming_grades = normalize_grades_by_user(triple.get("grades_by_user"))
            
            merged_grades = dict(existing_grades)
            for grader_id, grade_payload in incoming_grades.items():
                if grader_id not in merged_grades:
                    merged_grades[grader_id] = grade_payload
            
            my_grade = normalize_grade_value(triple.get("grade"))
            if not user_can_grade:
                merged_grades.pop(user_id, None)
                triple["grade"] = None
                triple["author"] = None
                triple.pop("graded_at", None)
            elif my_grade is None:
                merged_grades.pop(user_id, None)
                triple["grade"] = None
                triple["author"] = None
                triple.pop("graded_at", None)
            else:
                merged_grades[user_id] = {
                    "user_id": user_id,
                    "user_name": user_name,
                    "grade": my_grade,
                    "graded_at": now_iso,
                }
                triple["grade"] = my_grade
                triple["author"] = user_name
                triple["graded_at"] = now_iso
            
            triple["grades_by_user"] = merged_grades


def merge_existing_suggestions(incoming_session: Dict[str, Any], existing_session: Dict[str, Any]) -> None:
    """
    Keep suggestions persisted via suggestion endpoints when owner performs a full save.
    
    Args:
        incoming_session: The session data from the client
        existing_session: The existing session data from storage
    """
    existing_sentences = {
        s.get("id"): s
        for s in existing_session.get("sentences", [])
        if s.get("id") is not None
    }
    
    for sentence in incoming_session.get("sentences", []):
        sentence_id = sentence.get("id")
        existing_sentence = existing_sentences.get(sentence_id)
        if not existing_sentence:
            continue
        
        existing_triples = {
            t.get("id"): t
            for t in existing_sentence.get("triples", [])
            if t.get("id") is not None
        }
        
        for triple in sentence.get("triples", []):
            triple_id = triple.get("id")
            existing_triple = existing_triples.get(triple_id)
            if not existing_triple:
                continue
            
            existing_suggestions = existing_triple.get("suggestions")
            if isinstance(existing_suggestions, list):
                # Suggestion writes are already persisted server-side by dedicated endpoints.
                # Preserve them to avoid stale client payloads wiping comments/posts.
                triple["suggestions"] = existing_suggestions


def merge_existing_sentence_comments(incoming_session: Dict[str, Any], existing_session: Dict[str, Any]) -> None:
    """
    Preserve and merge sentence comment threads across full-session saves.
    
    Args:
        incoming_session: The session data from the client
        existing_session: The existing session data from storage
    """
    existing_sentences = {
        s.get("id"): s
        for s in existing_session.get("sentences", [])
        if s.get("id") is not None
    }
    
    owner_fallback_user_id = str(existing_session.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(existing_session.get("owner_name") or "").strip()
    
    for sentence in incoming_session.get("sentences", []):
        sentence_id = sentence.get("id")
        existing_sentence = existing_sentences.get(sentence_id)
        
        incoming_comments = normalize_sentence_comments(
            sentence.get("sentence_comments"),
            fallback_text=str(sentence.get("suggestion") or ""),
            fallback_author=owner_fallback_user_name,
            fallback_user_id=owner_fallback_user_id,
            fallback_created_at=sentence.get("comment_created_at"),
        )
        
        if not existing_sentence:
            sentence["sentence_comments"] = incoming_comments
            sentence["comment_count"] = len(incoming_comments)
            if incoming_comments:
                sentence["suggestion"] = incoming_comments[-1].get("text", "")
            continue
        
        existing_comments = normalize_sentence_comments(
            existing_sentence.get("sentence_comments"),
            fallback_text=str(existing_sentence.get("suggestion") or ""),
            fallback_author=owner_fallback_user_name,
            fallback_user_id=owner_fallback_user_id,
            fallback_created_at=existing_sentence.get("comment_created_at"),
        )
        
        merged_by_id: Dict[str, Dict[str, Any]] = {
            str(comment.get("id") or ""): comment
            for comment in existing_comments
            if str(comment.get("id") or "").strip()
        }
        
        for comment in incoming_comments:
            comment_id = str(comment.get("id") or "").strip()
            if not comment_id:
                continue
            merged_by_id[comment_id] = comment
        
        merged_comments = sorted(
            merged_by_id.values(),
            key=lambda row: str(row.get("created_at") or ""),
        )
        
        sentence["sentence_comments"] = merged_comments
        sentence["comment_count"] = len(merged_comments)
        if merged_comments:
            sentence["suggestion"] = merged_comments[-1].get("text", "")


def is_session_owner(session: Dict[str, Any], session_path: Optional[Any], user: Dict[str, Any]) -> bool:
    """
    Check if user is session owner.
    
    Args:
        session: The session data
        session_path: Optional path to session file (for legacy checks)
        user: The user to check
        
    Returns:
        True if user is the session owner
    """
    user_id = user.get("id", "")
    user_username = norm_username(user.get("username", ""))
    user_email = norm_email(user.get("email", ""))
    
    owner_user_id = str(session.get("owner_user_id") or "").strip()
    if owner_user_id and (
        owner_user_id == user_id
        or norm_username(owner_user_id) == user_username
        or norm_email(owner_user_id) == user_email
    ):
        return True
    
    owner_email = session.get("owner_email")
    if owner_email and norm_email(owner_email) == user_email:
        return True
    
    owner_username = session.get("owner_username")
    if owner_username and norm_username(owner_username) == user_username:
        return True
    
    owner_name = (session.get("owner_name") or "").strip()
    if owner_name and owner_name in {
        (user.get("name") or "").strip(),
        user_username,
    }:
        return True
    
    # Legacy fallback for sessions saved before owner metadata was persisted
    parent_owner = str(session_path.parent.name or "").strip() if session_path else ""
    return bool(
        parent_owner
        and (
            parent_owner == user_id
            or norm_username(parent_owner) == user_username
            or norm_email(parent_owner) == user_email
        )
    )


def root_session_id(session: Dict[str, Any]) -> str:
    """Get root session ID from session data."""
    return str(session.get("root_session_id") or session.get("session_id") or "").strip()


def can_approve_session(session: Dict[str, Any], session_path: Optional[Any], user: Dict[str, Any]) -> bool:
    """Check if user can approve session (owner only)."""
    return is_session_owner(session, session_path, user)


def can_suggest_session(session: Dict[str, Any], session_path: Optional[Any], user: Dict[str, Any]) -> bool:
    """Check if user can suggest in session (non-owners only)."""
    return not is_session_owner(session, session_path, user)


def can_edit_session_directly(session: Dict[str, Any], session_path: Optional[Any], user: Dict[str, Any]) -> bool:
    """Check if user can edit session directly (non-owners only)."""
    return not is_session_owner(session, session_path, user)


def project_session_for_view(
    session_data: Dict[str, Any],
    view_mode: str,
    view_user_id: str = "",
) -> Dict[str, Any]:
    """
    Project session data for display based on view mode.
    
    Args:
        session_data: The session data
        view_mode: "combined" or "user"
        view_user_id: User ID for user-specific view
        
    Returns:
        Projected session data for display
    """
    data = json.loads(json.dumps(session_data, ensure_ascii=False))
    
    owner_fallback_user_id = str(data.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(data.get("owner_name") or "").strip()
    
    overall_triple_grades: List[float] = []
    total_triples = 0
    graded_triples = 0
    
    for sentence in data.get("sentences", []):
        sentence_user_grades: Dict[str, List[float]] = {}
        
        completeness_by_user = normalize_sentence_metric_by_user(
            sentence.get("completeness_by_user"),
            fallback_value=sentence.get("completeness"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("completeness_updated_at"),
        )
        external_relation_by_user = normalize_sentence_metric_by_user(
            sentence.get("external_relation_by_user"),
            fallback_value=sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("external_relation_updated_at"),
        )
        
        sentence["completeness_by_user"] = completeness_by_user
        sentence["external_relation_by_user"] = external_relation_by_user
        
        for triple in sentence.get("triples", []):
            total_triples += 1
            
            grades_by_user = normalize_grades_by_user(
                triple.get("grades_by_user"),
                fallback_grade=triple.get("grade"),
                fallback_author=str(triple.get("author") or ""),
                fallback_user_id=owner_fallback_user_id,
                fallback_graded_at=triple.get("graded_at"),
            )
            triple["grades_by_user"] = grades_by_user
            
            for grader_id, payload in grades_by_user.items():
                grade_value = normalize_grade_value(payload.get("grade"))
                if grade_value is None:
                    continue
                sentence_user_grades.setdefault(grader_id, []).append(float(grade_value))
            
            if view_mode == "user" and view_user_id:
                selected_payload = grades_by_user.get(view_user_id)
                selected_grade = (
                    normalize_grade_value(selected_payload.get("grade"))
                    if isinstance(selected_payload, dict)
                    else None
                )
                triple["grade"] = selected_grade
                triple["author"] = (
                    str(selected_payload.get("user_name") or view_user_id)
                    if isinstance(selected_payload, dict) and selected_grade is not None
                    else None
                )
                triple["grade_count"] = 1 if selected_grade is not None else 0
                triple["grade_average"] = selected_grade
            else:
                grade_values = [
                    float(grade_value)
                    for payload in grades_by_user.values()
                    for grade_value in [normalize_grade_value(payload.get("grade"))]
                    if grade_value is not None
                ]
                combined_grade = calculate_average(grade_values)
                triple["grade"] = combined_grade
                triple["author"] = "Combined" if combined_grade is not None else None
                triple["grade_count"] = len(grade_values)
                triple["grade_average"] = combined_grade
            
            if triple.get("grade") is not None:
                graded_triples += 1
                overall_triple_grades.append(float(triple["grade"]))
        
        if view_mode == "user" and view_user_id:
            selected_comp = completeness_by_user.get(view_user_id)
            selected_ext = external_relation_by_user.get(view_user_id)
            
            comp_value = (
                normalize_sentence_metric_value(selected_comp.get("value"))
                if isinstance(selected_comp, dict)
                else None
            )
            ext_value = (
                normalize_sentence_metric_value(selected_ext.get("value"))
                if isinstance(selected_ext, dict)
                else None
            )
            
            sentence["completeness"] = comp_value
            sentence["completeness_count"] = 1 if comp_value is not None else 0
            sentence["completeness_average"] = comp_value
            
            sentence["external_relation"] = ext_value
            sentence["external_relation_count"] = 1 if ext_value is not None else 0
            sentence["external_relation_average"] = ext_value
            
            sentence_grade_values = [float(v) for v in sentence_user_grades.get(view_user_id, [])]
            sentence["sentence_grade"] = calculate_average(sentence_grade_values)
        else:
            comp_values = [
                float(metric_value)
                for payload in completeness_by_user.values()
                for metric_value in [normalize_sentence_metric_value(payload.get("value"))]
                if metric_value is not None
            ]
            ext_values = [
                float(metric_value)
                for payload in external_relation_by_user.values()
                for metric_value in [normalize_sentence_metric_value(payload.get("value"))]
                if metric_value is not None
            ]
            
            sentence["completeness"] = calculate_average(comp_values)
            sentence["completeness_count"] = len(comp_values)
            sentence["completeness_average"] = calculate_average(comp_values)
            
            sentence["external_relation"] = calculate_average(ext_values)
            sentence["external_relation_count"] = len(ext_values)
            sentence["external_relation_average"] = calculate_average(ext_values)
            
            per_user_sentence_grades = [
                calculate_average(values)
                for values in sentence_user_grades.values()
                if values
            ]
            sentence["sentence_grade"] = calculate_average([
                float(v)
                for v in per_user_sentence_grades
                if v is not None
            ])
    
    data["session_average_grade"] = calculate_average(overall_triple_grades)
    data["is_completed_grading"] = total_triples > 0 and graded_triples == total_triples
    data["graded_triples"] = graded_triples
    data["total_triples"] = total_triples
    data["preview_view_mode"] = view_mode
    data["preview_view_user_id"] = view_user_id if view_mode == "user" and view_user_id else None
    return data


def session_for_user_view(session: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a user-scoped view of a session.
    
    Args:
        session: The session data
        user: The current user
        
    Returns:
        User-scoped session data
    """
    # Deep copy so caller gets a user-scoped projection without mutating storage payload
    data = json.loads(json.dumps(session, ensure_ascii=False))
    stats = calculate_session_grading_stats(data)
    
    user_id = str(user.get("id") or "").strip()
    owner_fallback_user_id = str(data.get("owner_user_id") or "").strip()
    owner_fallback_user_name = str(data.get("owner_name") or "").strip()
    
    for sentence in data.get("sentences", []):
        sentence_comments = normalize_sentence_comments(
            sentence.get("sentence_comments"),
            fallback_text=str(sentence.get("suggestion") or ""),
            fallback_author=owner_fallback_user_name,
            fallback_user_id=owner_fallback_user_id,
            fallback_created_at=sentence.get("comment_created_at"),
        )
        sentence["sentence_comments"] = sentence_comments
        sentence["comment_count"] = len(sentence_comments)
        sentence["suggestion"] = sentence_comments[-1].get("text", "") if sentence_comments else ""
        
        completeness_by_user = normalize_sentence_metric_by_user(
            sentence.get("completeness_by_user"),
            fallback_value=sentence.get("completeness"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("completeness_updated_at"),
        )
        completeness_values = [
            float(payload.get("value"))
            for payload in completeness_by_user.values()
            if normalize_sentence_metric_value(payload.get("value")) is not None
        ]
        current_user_completeness = completeness_by_user.get(user_id) if user_id else None
        sentence["completeness"] = (
            current_user_completeness.get("value")
            if isinstance(current_user_completeness, dict)
            else None
        )
        sentence["completeness_by_user"] = completeness_by_user
        sentence["completeness_count"] = len(completeness_values)
        sentence["completeness_average"] = (
            calculate_average(completeness_values)
            if completeness_values
            else None
        )
        
        external_relation_by_user = normalize_sentence_metric_by_user(
            sentence.get("external_relation_by_user"),
            fallback_value=sentence.get("external_relation") if sentence.get("external_relation") is not None else sentence.get("relation"),
            fallback_user_id=owner_fallback_user_id,
            fallback_user_name=owner_fallback_user_name,
            fallback_updated_at=sentence.get("external_relation_updated_at"),
        )
        external_relation_values = [
            float(payload.get("value"))
            for payload in external_relation_by_user.values()
            if normalize_sentence_metric_value(payload.get("value")) is not None
        ]
        current_user_external = external_relation_by_user.get(user_id) if user_id else None
        sentence["external_relation"] = (
            current_user_external.get("value")
            if isinstance(current_user_external, dict)
            else None
        )
        sentence["external_relation_by_user"] = external_relation_by_user
        sentence["external_relation_count"] = len(external_relation_values)
        sentence["external_relation_average"] = (
            calculate_average(external_relation_values)
            if external_relation_values
            else None
        )
        
        for triple in sentence.get("triples", []):
            grades_by_user = triple.get("grades_by_user") if isinstance(triple.get("grades_by_user"), dict) else {}
            grade_values = [
                float(payload.get("grade"))
                for payload in grades_by_user.values()
                if normalize_grade_value(payload.get("grade")) is not None
            ]
            current_user_grade = grades_by_user.get(user_id) if user_id else None
            
            triple["grade"] = current_user_grade.get("grade") if isinstance(current_user_grade, dict) else None
            triple["author"] = current_user_grade.get("user_name") if isinstance(current_user_grade, dict) else None
            triple["grade_count"] = len(grade_values)
            triple["grade_average"] = calculate_average(grade_values)
    
    data["session_average_grade"] = stats["session_average_grade"]
    data["is_completed_grading"] = stats["is_completed_grading"]
    data["total_grade_entries"] = stats["total_grade_entries"]
    data["total_unique_graders"] = stats["total_unique_graders"]
    data["completed_grader_count"] = stats["completed_grader_count"]
    data["grader_summary"] = stats["grader_summary"]
    
    my_summary = next((row for row in stats["grader_summary"] if row.get("user_id") == user_id), None)
    data["my_graded_triples"] = int(my_summary.get("graded_triples") or 0) if my_summary else 0
    return data


def with_session_access_flags(
    session: Dict[str, Any],
    session_path: Optional[Any],
    user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Add access flags to session data for the current user.
    
    Args:
        session: The session data
        session_path: Optional path to session file
        user: The current user
        
    Returns:
        Session data with access flags
    """
    data = session_for_user_view(session, user)
    session_id = str(data.get("session_id") or "").strip()
    data["root_session_id"] = session_id
    data["is_copy"] = False
    data["can_edit"] = can_edit_session_directly(session, session_path, user)
    data["can_suggest"] = can_suggest_session(session, session_path, user)
    data["can_approve"] = can_approve_session(session, session_path, user)
    data["is_owner"] = is_session_owner(session, session_path, user)
    return data