"""
Pytest entry points for scenarios T14 and T15: draft edits saved after a version is published
leave the published version unchanged, and a version cannot be deleted by a non-owner or when it
is the only one left.
"""

from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (
    TestEQ1WorkflowMatrix as _TestRunner,
    client,
    auth_context,
)

_runner = _TestRunner()


def test_t14_publish_version(client, auth_context):
    _runner.test_t14_publish_version_isolation(client, auth_context)


def test_t15_delete_version(client, auth_context):
    _runner.test_t15_delete_version_protection(client, auth_context)
