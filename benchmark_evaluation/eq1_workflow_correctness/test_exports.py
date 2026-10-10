"""
test_exports.py — Multi-format dataset serialization and export integrity validation suite.

Verifies cross-format parity and zero information loss across supported export targets (JSON, CSV).
Ensures exported relational tables preserve identical triple counts, canonical identifiers,
subject-predicate-object string tokens, adjudicated grades, and consensus agreement flags.
"""

from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (
    TestEQ1WorkflowMatrix as _TestRunner,
    client,
    auth_context,
)

_runner = _TestRunner()


def test_t16_exports(client, auth_context):
    _runner.test_t16_multi_format_export_integrity(client, auth_context)
