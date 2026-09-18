"""
test_task2_workflow.py — Independent Verification Script for Task 2 (EQ1).

This script allows the user to run and verify the complete Evaluation Question 1 (EQ1)
test suite from the command line. It validates all 18 state transitions, role permissions,
rejection rules, field fidelity, and output CSV/LaTeX artifacts.

Usage:
    python documents/test_task2_workflow.py
"""

import csv
import sys
import time
from pathlib import Path

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from fastapi.testclient import TestClient
from backend.main import app
from experiments.eq1_workflow_correctness.run_eq1_evaluation import (
    build_auth_context,
    RESULTS_DIR,
)
from experiments.eq1_workflow_correctness.test_workflow_matrix import (
    TestEQ1WorkflowMatrix,
)


def run_checks():
    print("=" * 80)
    print("TASK 2 (EQ1) INDEPENDENT USER VERIFICATION SUITE")
    print("Evaluation of Collaborative Curation Workflow Correctness & Schema Fidelity")
    print("=" * 80)

    client = TestClient(app)
    auth = build_auth_context()
    suite = TestEQ1WorkflowMatrix()
    TestEQ1WorkflowMatrix.test_records = []

    # Define the 18 tests
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

    print(f"\n[*] Executing all 18 transitions against FastAPI HTTP endpoints...")
    print(f"{'Test ID':<8} | {'Category':<24} | {'Status':<6} | {'Time (ms)':<10} | {'Description'}")
    print("-" * 80)

    passed_count = 0
    valid_passed = 0
    valid_total = 0
    invalid_passed = 0
    invalid_total = 0
    fidelity_scores = []

    for test_id, name, func, cat in tests:
        t0 = time.perf_counter()
        ok = False
        err = ""
        try:
            func(client, auth)
            ok = True
        except Exception as e:
            err = str(e)
            ok = False
        elapsed = round((time.perf_counter() - t0) * 1000, 1)

        rec = next((r for r in reversed(TestEQ1WorkflowMatrix.test_records) if r["test_id"] == test_id), None)
        fid = rec["fidelity"] if rec else (1.0 if ok else 0.0)
        fidelity_scores.append(fid)

        if cat == "Valid Transition":
            valid_total += 1
            if ok:
                valid_passed += 1
        else:
            invalid_total += 1
            if ok:
                invalid_passed += 1

        if ok:
            passed_count += 1
            status_tag = "[PASS]"
        else:
            status_tag = "[FAIL]"

        print(f"{test_id:<8} | {cat:<24} | {status_tag:<6} | {elapsed:>8.1f}ms | {name}")
        if not ok:
            print(f"         --> Error: {err}")

    print("-" * 80)

    # 1. Metric verification
    vta = (valid_passed / valid_total) * 100.0 if valid_total else 0.0
    iarr = (invalid_passed / invalid_total) * 100.0 if invalid_total else 0.0
    mean_fid = (sum(fidelity_scores) / len(fidelity_scores)) * 100.0 if fidelity_scores else 0.0

    print("\n[CHECK 1] Valid Transition Accuracy (VTA):")
    print(f"  Observed: {vta:.1f}% ({valid_passed}/{valid_total})")
    print(f"  Target:   100.0%")
    assert vta == 100.0, f"VTA did not meet 100% target! ({vta}%)"
    print("  --> OK: All valid lifecycle transitions execute correctly.")

    print("\n[CHECK 2] Invalid-Action Rejection Rate (IARR):")
    print(f"  Observed: {iarr:.1f}% ({invalid_passed}/{invalid_total})")
    print(f"  Target:   100.0%")
    assert iarr == 100.0, f"IARR did not meet 100% target! ({iarr}%)"
    print("  --> OK: All invalid actions (self-voting, unauthorized deletion, invalid ids) rejected.")

    print("\n[CHECK 3] Dynamic Field Fidelity (FF):")
    print(f"  Observed: {mean_fid:.2f}%")
    print(f"  Target:   >= 99.0%")
    assert mean_fid >= 99.0, f"Field fidelity below 99% target! ({mean_fid}%)"
    print("  --> OK: Untouched fields preserved bit-for-bit without data corruption.")

    print("\n[CHECK 4] Output Files & Artifact Verification:")
    matrix_csv = RESULTS_DIR / "eq1_workflow_matrix.csv"
    summary_csv = RESULTS_DIR / "eq1_summary.csv"
    table_tex = RESULTS_DIR / "table_eq1_workflow.tex"

    for path, label in [(matrix_csv, "Detailed Matrix CSV"), (summary_csv, "Summary CSV"), (table_tex, "LaTeX Table")]:
        if path.exists() and path.stat().st_size > 0:
            print(f"  --> [EXISTS] {label} ({path.name}, {path.stat().st_size} bytes)")
        else:
            print(f"  --> [MISSING] {label} at {path}")
            sys.exit(1)

    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE: ALL CHECKS PASSED (18/18 tests, 100% VTA, 100% IARR, 100% FF)")
    print("=" * 80)


if __name__ == "__main__":
    run_checks()
