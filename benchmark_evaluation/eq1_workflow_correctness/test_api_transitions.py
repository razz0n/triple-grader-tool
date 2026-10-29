"""
Pytest entry points for the permitted-operation scenarios T01, T02, T04, T06, T09, T10, T11 and
T12: importing a session, saving and clearing a grade, creating, approving and unapproving a
suggestion, marking a triple for removal, and adding a missing triple. Each test checks the
HTTP status and the stored session.
"""

from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (
    TestEQ1WorkflowMatrix as _TestRunner,
    client,
    auth_context,
)

_runner = _TestRunner()


def test_t01_import(client, auth_context):
    _runner.test_t01_import_valid_file(client, auth_context)


def test_t02_save_grade(client, auth_context):
    _runner.test_t02_reviewer_saves_grade(client, auth_context)


def test_t04_clear_grade(client, auth_context):
    _runner.test_t04_clear_grade(client, auth_context)


def test_t06_create_suggestion(client, auth_context):
    _runner.test_t06_create_correction_suggestion(client, auth_context)


def test_t09_approve_suggestion(client, auth_context):
    _runner.test_t09_owner_approves_suggestion(client, auth_context)


def test_t10_unapprove_suggestion(client, auth_context):
    _runner.test_t10_owner_unapproves_suggestion(client, auth_context)


def test_t11_mark_removal(client, auth_context):
    _runner.test_t11_mark_for_removal(client, auth_context)


def test_t12_add_missing(client, auth_context):
    _runner.test_t12_add_missing_triple(client, auth_context)
