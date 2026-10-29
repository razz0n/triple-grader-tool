"""
Pytest entry points for scenarios T02, T05, T13, T17 and T18: grades, completeness and
external-relation ratings and threaded sentence comments survive a save and reload, saves from
two clients are both kept, and malformed session identifiers are rejected.
"""

from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (
    TestEQ1WorkflowMatrix as _TestRunner,
    client,
    auth_context,
)

_runner = _TestRunner()


def test_t02_persistence(client, auth_context):
    _runner.test_t02_reviewer_saves_grade(client, auth_context)


def test_t05_completeness_persistence(client, auth_context):
    _runner.test_t05_save_completeness_and_relation(client, auth_context)


def test_t13_comments_persistence(client, auth_context):
    _runner.test_t13_comments_and_nested_replies(client, auth_context)


def test_t17_concurrent_save(client, auth_context):
    _runner.test_t17_concurrent_stale_save_simulation(client, auth_context)


def test_t18_malformed_reject(client, auth_context):
    _runner.test_t18_malformed_identifiers(client, auth_context)
