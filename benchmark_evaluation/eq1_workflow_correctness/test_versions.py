"""
test_versions.py — Benchmark version snapshotting and snapshot immutability validation suite.

Verifies version management invariants in the collaborative benchmark lifecycle:
- Published milestone snapshots remain strictly immutable when owners subsequently save draft edits.
- Milestone deletion protection preventing removal of the initial base version and unauthorized deletion.
- Version history integrity ensuring all snapshot sentences, metadata, and grader summaries are preserved.
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
