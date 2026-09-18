"""
services/ — Business logic services for the Ontology Triple Grading Tool.
"""

from .grading_service import (
    calculate_average,
    calculate_session_activity_for_user,
    calculate_session_grading_stats,
)
from .normalization import (
    normalize_grade_value,
    normalize_grades_by_user,
    normalize_sentence_comments,
    normalize_sentence_metric_by_user,
    normalize_sentence_metric_value,
)
from .adjudicated_gold import (
    build_adjudicated_gold_set,
    include_in_adjudicated_gold,
)
from .session_service import (
    apply_collaborative_grades,
    can_approve_session,
    can_edit_session_directly,
    can_suggest_session,
    is_session_owner,
    merge_existing_sentence_comments,
    merge_existing_suggestions,
    project_session_for_view,
    root_session_id,
    sentence_groups_to_draft_sentences,
    session_for_user_view,
    with_session_access_flags,
)

__all__ = [
    # Normalization
    "normalize_grade_value",
    "normalize_grades_by_user",
    "normalize_sentence_metric_value",
    "normalize_sentence_metric_by_user",
    "normalize_sentence_comments",
    # Grading
    "calculate_session_grading_stats",
    "calculate_session_activity_for_user",
    "calculate_average",
    # Session
    "apply_collaborative_grades",
    "can_approve_session",
    "can_edit_session_directly",
    "can_suggest_session",
    "is_session_owner",
    "merge_existing_sentence_comments",
    "merge_existing_suggestions",
    "project_session_for_view",
    "root_session_id",
    "sentence_groups_to_draft_sentences",
    "session_for_user_view",
    "with_session_access_flags",
    # Adjudicated gold
    "include_in_adjudicated_gold",
    "build_adjudicated_gold_set",
]
