"""
run_eq1_evaluation.py — Evaluation test runner for lifecycle state transitions.

Orchestrates the execution of lifecycle transitions T01 through T18 against FastAPI
HTTP routes using an isolated local JSON/SQLite store. Gathers transition metrics including valid transition
accuracy, invalid-action rejection, field fidelity, and response latencies, and writes
the aggregated results to CSV and LaTeX tables.
"""

import csv
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

# Ensure repository roots are in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from benchmark_evaluation.common.local_backend import assert_local_storage, use_isolated_local_storage

use_isolated_local_storage()

from backend.auth import ensure_default_users, issue_token, load_users
from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (
    TestEQ1WorkflowMatrix,
    make_client,
)

assert_local_storage()

RESULTS_DIR = ROOT_DIR / "benchmark_evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def build_auth_context() -> Dict[str, Any]:
    ensure_default_users()
    users = load_users().get("users", [])
    u_ysh = next(u for u in users if u.get("username") == "user_ysh")
    u_jw = next(u for u in users if u.get("username") == "user_jw")
    u_rl = next(u for u in users if u.get("username") == "user_rl")

    return {
        "owner": {
            "id": u_ysh["id"],
            "username": "user_ysh",
            "header": {"Authorization": f"Bearer {issue_token(u_ysh['id'])}"},
        },
        "reviewer1": {
            "id": u_jw["id"],
            "username": "user_jw",
            "header": {"Authorization": f"Bearer {issue_token(u_jw['id'])}"},
        },
        "reviewer2": {
            "id": u_rl["id"],
            "username": "user_rl",
            "header": {"Authorization": f"Bearer {issue_token(u_rl['id'])}"},
        },
    }


def run_evaluation() -> Dict[str, Any]:
    auth = build_auth_context()
    client = make_client(auth)
    suite = TestEQ1WorkflowMatrix()

    # Clear previous records
    TestEQ1WorkflowMatrix.test_records = []

    tests = [
        ("T01", "Import valid file", suite.test_t01_import_valid_file, "Valid Transition"),
        ("T02", "Reviewer saves grade", suite.test_t02_reviewer_saves_grade, "Valid Transition"),
        ("T03", "Non-owner saves grade", suite.test_t03_non_owner_saves_grade, "Valid Transition"),
        ("T04", "Clear a grade", suite.test_t04_clear_grade, "Valid Transition"),
        ("T05", "Save completeness & relation", suite.test_t05_save_completeness_and_relation, "Valid Transition"),
        ("T06", "Create correction suggestion", suite.test_t06_create_correction_suggestion, "Valid Transition"),
        ("T07", "Suggestion voting & self-vote rejection", suite.test_t07_suggestion_voting_and_self_vote_rejection, "Invalid Action Rejection"),
        ("T08", "Suggestion author permissions", suite.test_t08_suggestion_author_permissions, "Invalid Action Rejection"),
        ("T09", "Owner approves suggestion", suite.test_t09_owner_approves_suggestion, "Valid Transition"),
        ("T10", "Owner unapproves suggestion", suite.test_t10_owner_unapproves_suggestion, "Valid Transition"),
        ("T11", "Mark triple for removal", suite.test_t11_mark_for_removal, "Valid Transition"),
        ("T12", "Add missing triple", suite.test_t12_add_missing_triple, "Valid Transition"),
        ("T13", "Sentence comments & replies", suite.test_t13_comments_and_nested_replies, "Valid Transition"),
        ("T14", "Publish version isolation", suite.test_t14_publish_version_isolation, "Valid Transition"),
        ("T15", "Delete version protection", suite.test_t15_delete_version_protection, "Invalid Action Rejection"),
        ("T16", "Multi-format export integrity", suite.test_t16_multi_format_export_integrity, "Valid Transition"),
        ("T17", "Concurrent save simulation", suite.test_t17_concurrent_stale_save_simulation, "Valid Transition"),
        ("T18", "Malformed identifiers", suite.test_t18_malformed_identifiers, "Invalid Action Rejection"),
    ]

    detailed_results = []
    print(f"{'Test ID':<8} | {'Category':<24} | {'Status':<6} | {'Fidelity':<8} | {'Latency (ms)':<12} | {'Description'}")
    print("-" * 90)

    for test_id, desc, test_func, category in tests:
        t0 = time.perf_counter()
        passed = False
        error_msg = ""
        try:
            test_func(client, auth)
            passed = True
        except Exception as exc:
            error_msg = str(exc)
            passed = False
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Retrieve record from class
        rec = next((r for r in reversed(TestEQ1WorkflowMatrix.test_records) if r["test_id"] == test_id), None)
        fidelity = rec["fidelity"] if rec else (1.0 if passed else 0.0)
        exp_status = rec["expected_status"] if rec else "Success"
        act_status = rec["actual_status"] if rec else ("Success" if passed else f"Failed: {error_msg}")

        detailed_results.append({
            "test_id": test_id,
            "name": desc,
            "category": category,
            "expected_outcome": exp_status,
            "actual_outcome": act_status,
            "field_fidelity": fidelity,
            "passed": passed,
            "latency_ms": elapsed_ms,
        })

        status_str = "PASS" if passed else "FAIL"
        print(f"{test_id:<8} | {category:<24} | {status_str:<6} | {fidelity * 100:>6.1f}% | {elapsed_ms:>10.2f}ms | {desc}", flush=True)

    # Compute high-level metrics
    valid_transitions = [r for r in detailed_results if r["category"] == "Valid Transition"]
    invalid_actions = [r for r in detailed_results if r["category"] == "Invalid Action Rejection"]

    vta = sum(1 for r in valid_transitions if r["passed"]) / len(valid_transitions) if valid_transitions else 0.0
    iarr = sum(1 for r in invalid_actions if r["passed"]) / len(invalid_actions) if invalid_actions else 0.0
    avg_fidelity = sum(r["field_fidelity"] for r in detailed_results) / len(detailed_results) if detailed_results else 0.0
    total_passed = sum(1 for r in detailed_results if r["passed"])

    print("-" * 90)
    print(f"Valid Transition Accuracy (VTA):      {vta * 100:.1f}% ({sum(1 for r in valid_transitions if r['passed'])}/{len(valid_transitions)}) [Target: 100.0%]")
    print(f"Invalid-Action Rejection Rate (IARR): {iarr * 100:.1f}% ({sum(1 for r in invalid_actions if r['passed'])}/{len(invalid_actions)}) [Target: 100.0%]")
    print(f"Dynamic Field Fidelity (FF):          {avg_fidelity * 100:.2f}% [Target: >99.0%]")
    print(f"Total Transitions Passing:            {total_passed}/{len(detailed_results)}")

    # 1. Write eq1_workflow_matrix.csv
    csv_matrix_path = RESULTS_DIR / "eq1_workflow_matrix.csv"
    with open(csv_matrix_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "test_id", "name", "category", "expected_outcome", "actual_outcome", "field_fidelity", "passed", "latency_ms"
        ])
        writer.writeheader()
        for row in detailed_results:
            writer.writerow(row)
    print(f"\n[Saved] Detailed matrix written to: {csv_matrix_path}")

    # 2. Write eq1_summary.csv
    csv_summary_path = RESULTS_DIR / "eq1_summary.csv"
    with open(csv_summary_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Metric", "Observed_Value", "Benchmark_Target", "Status"])
        writer.writerow(["Valid Transition Accuracy (VTA)", f"{vta * 100:.1f}%", "100.0%", "PASSED" if vta == 1.0 else "FAILED"])
        writer.writerow(["Invalid-Action Rejection Rate (IARR)", f"{iarr * 100:.1f}%", "100.0%", "PASSED" if iarr == 1.0 else "FAILED"])
        writer.writerow(["Dynamic Field Fidelity (FF)", f"{avg_fidelity * 100:.2f}%", ">=99.0%", "PASSED" if avg_fidelity >= 0.99 else "FAILED"])
        writer.writerow(["Total Evaluated Scenarios", str(len(detailed_results)), "18", "PASSED" if total_passed == 18 else "FAILED"])
    print(f"[Saved] Metric summary written to: {csv_summary_path}")

    return {
        "vta": vta,
        "iarr": iarr,
        "fidelity": avg_fidelity,
        "total": len(detailed_results),
        "passed": total_passed,
    }


if __name__ == "__main__":
    run_evaluation()
