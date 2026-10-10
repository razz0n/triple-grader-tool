"""
test_permissions.py — Role-based access control (RBAC) and security boundary validation suite.

Verifies authorization policies and invalid-action rejection (HTTP 403 Forbidden) across:
- Non-owner restricted modifications (grade updates permitted; unapproved edits rejected).
- Suggestion voting constraints, including strict self-vote rejection.
- Suggestion author authorization boundaries (only the author or owner may modify suggestions).
- Milestone deletion protection (only session owners may delete non-base versions).
"""

from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (
    TestEQ1WorkflowMatrix as _TestRunner,
    client,
    auth_context,
)

_runner = _TestRunner()


def test_t03_non_owner(client, auth_context):
    _runner.test_t03_non_owner_saves_grade(client, auth_context)


def test_t07_self_vote_rejection(client, auth_context):
    _runner.test_t07_suggestion_voting_and_self_vote_rejection(client, auth_context)


def test_t08_author_permissions(client, auth_context):
    _runner.test_t08_suggestion_author_permissions(client, auth_context)


def test_t15_delete_protection(client, auth_context):
    _runner.test_t15_delete_version_protection(client, auth_context)
