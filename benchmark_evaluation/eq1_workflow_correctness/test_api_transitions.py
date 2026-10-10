"""
test_api_transitions.py — State transition validation suite for collaborative ontology curation.

Executes end-to-end integration tests verifying core lifecycle state transitions across
session import, reviewer grade submission, grade retraction, correction suggestion creation,
owner approval/rejection workflows, entity removal flags, and missing triple insertions.
Validates HTTP response codes, session state invariants, and payload integrity.
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
