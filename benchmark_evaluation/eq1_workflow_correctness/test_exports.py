"""
Pytest entry point for scenario T16: the gold JSON and CSV exports list the same triples, with
the same identifiers, text, grades and agreement flags.
"""

from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (
    TestEQ1WorkflowMatrix as _TestRunner,
    client,
    auth_context,
)

_runner = _TestRunner()


def test_t16_exports(client, auth_context):
    _runner.test_t16_multi_format_export_integrity(client, auth_context)
