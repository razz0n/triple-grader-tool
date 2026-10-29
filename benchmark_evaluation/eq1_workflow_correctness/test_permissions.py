"""
Pytest entry points for scenarios T03, T07, T08 and T15, which expect HTTP 403: a non-owner's
unapproved edits are rejected while their grades are accepted, a grader cannot vote on their own
suggestion, only its author or the owner can change a suggestion, and only the owner can delete a
version.
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
