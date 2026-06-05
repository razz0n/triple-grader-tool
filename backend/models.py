"""
models.py — Pydantic models for the Ontology Triple Grading Tool.
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SaveRequest(BaseModel):
    """Request model for saving sessions."""
    session_id: str
    source_filename: str
    uploaded_at: str
    sentences: list
    manual_mode: bool = False


class AuthRequest(BaseModel):
    """Request model for authentication."""
    login: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    """Request model for user registration."""
    name: str = Field(min_length=2, max_length=80)
    username: str = Field(min_length=3, max_length=24)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TripleSuggestionRequest(BaseModel):
    """Request model for adding triple suggestions."""
    session_id: str
    sentence_id: int
    triple_id: str
    subject: str
    predicate: str
    object: str
    reason: Optional[str] = None


class VoteRequest(BaseModel):
    """Request model for voting on suggestions."""
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    vote: Optional[str] = None  # "yes", "no", numeric grade, or null to clear


class EditSuggestionRequest(BaseModel):
    """Request model for editing suggestions."""
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    subject: str
    predicate: str
    object: str
    reason: Optional[str] = None


class ApproveSuggestionRequest(BaseModel):
    """Request model for approving suggestions."""
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str


class EvaluationRequest(BaseModel):
    """Request model for evaluation."""
    match_mode: str = "soft"  # "exact" or "soft"
    gold_source: str = "graded_only"  # "graded_only" or "all"


class TripleCommentRequest(BaseModel):
    """Request model for adding a comment to a triple."""
    session_id: str
    sentence_id: int
    triple_id: str
    text: str


class MarkTripleRemovalRequest(BaseModel):
    """Request model for marking a triple as not needed."""
    session_id: str
    sentence_id: int
    triple_id: str
    marked: bool
