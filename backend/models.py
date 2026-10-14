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
    sentences: Optional[list] = None
    versions: Optional[list] = None
    manual_mode: bool = False
    version_name: Optional[str] = None
    last_version_name: Optional[str] = None
    current_version_name: Optional[str] = None
    is_publish: bool = False


class PublishVersionRequest(BaseModel):
    """Request model for publishing a new version."""
    session_id: str
    version_name: str
    sentences: Optional[list] = None


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
    security_question: str = Field(min_length=5, max_length=255)
    security_answer: str = Field(min_length=1, max_length=255)


class TripleSuggestionRequest(BaseModel):
    """Request model for adding triple suggestions."""
    session_id: str
    sentence_id: int
    triple_id: str
    subject: str
    predicate: str
    object: str
    reason: Optional[str] = None
    version_name: Optional[str] = None


class VoteRequest(BaseModel):
    """Request model for voting on suggestions."""
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    vote: Optional[str] = None  # "yes", "no", numeric grade, or null to clear
    version_name: Optional[str] = None


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
    version_name: Optional[str] = None


class ApproveSuggestionRequest(BaseModel):
    """Request model for approving suggestions."""
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    version_name: Optional[str] = None


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
    version_name: Optional[str] = None


class MarkTripleRemovalRequest(BaseModel):
    """Request model for marking a triple as not needed."""
    session_id: str
    sentence_id: int
    triple_id: str
    marked: bool
    version_name: Optional[str] = None


class CommentReplyRequest(BaseModel):
    """Request model for adding a reply to a comment (sentence or triple comment)."""
    session_id: str
    sentence_id: int
    triple_id: Optional[str] = None
    comment_id: str
    text: str
    parent_reply_id: Optional[str] = None
    version_name: Optional[str] = None


class SuggestionReplyRequest(BaseModel):
    """Request model for adding a reply (discussion comment) to a suggestion."""
    session_id: str
    sentence_id: int
    triple_id: str
    suggestion_id: str
    text: str
    parent_reply_id: Optional[str] = None
    version_name: Optional[str] = None


class NotificationReadRequest(BaseModel):
    """Request model for marking a comment reply, suggestion, or suggestion reply as read."""
    session_id: str
    item_id: str


class NotificationReadAllRequest(BaseModel):
    """Request model for marking all items in a session as read."""
    session_id: str


class UpdateProfileRequest(BaseModel):
    """Request model for updating user profile information."""
    name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    security_question: Optional[str] = None
    security_answer: Optional[str] = None
    current_password: Optional[str] = None


class GetSecurityQuestionRequest(BaseModel):
    """Request model for getting a user's security question."""
    login: str = Field(min_length=2, max_length=120)


class ResetPasswordWithQuestionRequest(BaseModel):
    """Request model for resetting password using security question."""
    login: str = Field(min_length=2, max_length=120)
    answer: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    """Request model for deleting user account."""
    password: str = Field(min_length=8, max_length=128)
    security_answer: str = Field(min_length=1, max_length=255)


class CreateSessionRequest(BaseModel):
    """Request model for creating a session via REST API."""
    id: Optional[str] = None
    session_id: Optional[str] = None
    filename: Optional[str] = "benchmark_session.json"
    user: Optional[str] = "owner"
    owner_name: Optional[str] = None
    owner_user_id: Optional[str] = None
    sentences: Optional[list] = None


class WorkflowSuggestionRequest(BaseModel):
    """Request model for RESTful suggestion creation."""
    triple_id: str
    user: Optional[str] = None  # ignored: the author is taken from the bearer token
    subject: str
    predicate: str
    object: str
    suggestion_id: Optional[str] = None
    comment: Optional[str] = None
    reason: Optional[str] = None
    sentence_id: Optional[str] = None


class WorkflowVoteRequest(BaseModel):
    """Request model for RESTful suggestion voting."""
    suggestion_id: str
    user: Optional[str] = None  # ignored: the voter is taken from the bearer token
    vote: str = "approve"
    triple_id: Optional[str] = None
    sentence_id: Optional[str] = None


class WorkflowApproveRequest(BaseModel):
    """Request model for RESTful suggestion approval."""
    suggestion_id: str
    user: Optional[str] = None  # ignored: the approver is taken from the bearer token
    triple_id: Optional[str] = None
    sentence_id: Optional[str] = None



