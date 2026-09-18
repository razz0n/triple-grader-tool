"""
test_task1_workflow.py — Interactive Verification Script for Task 1.

Run this script to verify all Task 1 requirements:
1. Unique sentence IDs in gold benchmark (s0001 - s0038).
2. User anonymization (no email address leakage).
3. Removal of session-level average grades.
4. Full RESTful HTTP curation API workflow:
   - Session creation
   - Suggestion submission
   - Voting and self-vote rejection
   - Owner approval
   - Original triple supersession & corrected triple activation
   - Adjudicated gold JSON and CSV exports
"""

import csv
import sys
from pathlib import Path

# Add backend to path for module resolution
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
from services.adjudicated_gold import build_adjudicated_gold_set, include_in_adjudicated_gold
from services.grading_service import calculate_session_grading_stats
from utils import display_name


def run_all_checks():
    print("=" * 70)
    print("Triple Grader — Task 1 Interactive Verification Suite")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Check 1: Sentence Identifiers in backend/gold_benchmark.csv
    # -------------------------------------------------------------------------
    print("\n[Check 1] Verifying sentence identifiers in backend/gold_benchmark.csv...")
    csv_path = BACKEND_DIR / "gold_benchmark.csv"
    assert csv_path.exists(), f"File not found: {csv_path}"

    with open(csv_path, mode="r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    unique_sentences = set(r["source_sentence"].strip() for r in rows)
    unique_ids = set(r["sentence_id"].strip() for r in rows)

    print(f"  • Total triple rows in gold benchmark: {len(rows)}")
    print(f"  • Unique source sentences count:      {len(unique_sentences)}")
    print(f"  • Unique sentence identifiers count:   {len(unique_ids)}")

    assert len(unique_ids) == len(unique_sentences), (
        f"Mismatch! Found {len(unique_ids)} sentence IDs for {len(unique_sentences)} unique sentences."
    )
    assert len(unique_ids) == 38, f"Expected 38 unique sentences, got {len(unique_ids)}"
    assert "s0001" in unique_ids and "s0038" in unique_ids, "Expected IDs from s0001 to s0038"
    print("  --> PASS: Sentence IDs are uniquely and sequentially assigned (s0001 - s0038).")

    # -------------------------------------------------------------------------
    # Check 2: User Anonymization and Privacy Enforcement
    # -------------------------------------------------------------------------
    print("\n[Check 2] Verifying user anonymization and display_name privacy...")
    test_user_email_only = {"email": "john.doe@university.edu"}
    name1 = display_name(test_user_email_only)
    print(f"  • Input: email='john.doe@university.edu' -> Display name: '{name1}'")
    assert "@" not in name1, "Display name must not contain '@'!"
    assert "john.doe" not in name1, "Display name must not leak personal email prefix!"

    test_user_with_id = {"id": "a6060386-f28e-471e-8f3a-d7a0ce9a012e", "email": "reviewer@lab.org"}
    name2 = display_name(test_user_with_id)
    print(f"  • Input: id='a6060386...', email='reviewer@lab.org' -> Display name: '{name2}'")
    assert name2 == "user_a6060386", f"Expected 'user_a6060386', got '{name2}'"

    test_user_valid_code = {"username": "user_rl", "name": "user_rl", "email": "rl@domain.com"}
    name3 = display_name(test_user_valid_code)
    print(f"  • Input: username='user_rl' -> Display name: '{name3}'")
    assert name3 == "user_rl"
    print("  --> PASS: User identity is strictly anonymized; email addresses are never leaked.")

    # -------------------------------------------------------------------------
    # Check 3: Removal of Session-Level Average Grade
    # -------------------------------------------------------------------------
    print("\n[Check 3] Verifying removal of session-level average grades...")
    mock_session = {
        "sentences": [{
            "id": "s001",
            "triples": [
                {"id": "t1", "grade": 8, "grades_by_user": {"u1": {"grade": 8}}},
                {"id": "t2", "grade": 10, "grades_by_user": {"u1": {"grade": 10}}},
            ],
        }]
    }
    stats = calculate_session_grading_stats(mock_session)
    print(f"  • session_average_grade in stats: {stats.get('session_average_grade')}")
    assert stats.get("session_average_grade") is None, (
        "Session-level average grade must be None!"
    )
    print("  --> PASS: Session average grade successfully removed while retaining individual triple grades.")

    # -------------------------------------------------------------------------
    # Check 4: RESTful HTTP API Workflow End-to-End
    # -------------------------------------------------------------------------
    print("\n[Check 4] Verifying RESTful Curation Workflow API endpoints...")
    client = TestClient(app)
    test_session_id = "test_manual_check_001"

    # Step 4a: Create Session
    create_payload = {
        "id": test_session_id,
        "filename": "ethics_curation_pilot.json",
        "user": "owner_alice",
        "sentences": [{
            "id": "s001",
            "sentence": "Software engineers develop software.",
            "triples": [{
                "id": "t001",
                "subject": "engineers",
                "predicate": "make",
                "object": "code",
                "status": "active"
            }]
        }]
    }
    r = client.post("/api/sessions", json=create_payload)
    assert r.status_code == 200, f"Create session failed: {r.text}"
    session_id = r.json()["id"]
    print(f"  • Step A [POST /api/sessions]: Created session '{session_id}' (Status {r.status_code})")

    # Step 4b: Submit Suggestion
    sug_payload = {
        "triple_id": "t001",
        "suggestion_id": "s001",
        "user": "reviewer_a",
        "subject": "software_engineers",
        "predicate": "develop",
        "object": "software",
        "comment": "Clarified subject and predicate to match ontology vocabulary"
    }
    r = client.post(f"/api/sessions/{session_id}/suggestions", json=sug_payload)
    assert r.status_code == 200, f"Add suggestion failed: {r.text}"
    print(f"  • Step B [POST /api/sessions/{session_id}/suggestions]: Added suggestion 's001' (Status {r.status_code})")

    # Step 4c: Vote on Suggestion
    vote_payload = {
        "suggestion_id": "s001",
        "user": "reviewer_b",
        "vote": "approve"
    }
    r = client.post(f"/api/sessions/{session_id}/vote", json=vote_payload)
    assert r.status_code == 200, f"Vote failed: {r.text}"
    print(f"  • Step C [POST /api/sessions/{session_id}/vote]: Reviewer B voted 'approve' (Status {r.status_code})")

    # Step 4d: Test Self-Vote Rejection
    self_vote_payload = {
        "suggestion_id": "s001",
        "user": "reviewer_a",
        "vote": "approve"
    }
    r_self = client.post(f"/api/sessions/{session_id}/vote", json=self_vote_payload)
    assert r_self.status_code == 400, "Self-voting must be rejected with 400 Bad Request!"
    print(f"  • Step D [Self-Vote Restriction]: Author Reviewer A voting on own suggestion rejected (Status {r_self.status_code})")

    # Step 4e: Owner Approves Suggestion
    approve_payload = {
        "suggestion_id": "s001",
        "user": "owner_alice"
    }
    r = client.post(f"/api/sessions/{session_id}/approve", json=approve_payload)
    assert r.status_code == 200, f"Approve failed: {r.text}"
    approve_res = r.json()
    print(f"  • Step E [POST /api/sessions/{session_id}/approve]: Owner approved suggestion (Status {r.status_code})")
    assert approve_res["status"] == "approved"
    assert approve_res["approved_by"] == "owner_alice"

    # Step 4f: Verify Session State
    session = client.get(f"/api/sessions/{session_id}").json()
    triples = session["sentences"][0]["triples"]
    orig_triple = next((t for t in triples if t["id"] == "t001"), None)
    corr_triple = next((t for t in triples if t["id"] == "t001_corrected"), None)

    assert orig_triple is not None and orig_triple["status"] == "superseded"
    assert corr_triple is not None and corr_triple["status"] == "approved"
    assert corr_triple["subject"] == "software_engineers"
    assert corr_triple["predicate"] == "develop"
    assert corr_triple["object"] == "software"
    print("  • Step F [GET /api/sessions/{session_id}]: Original triple marked 'superseded'; corrected triple active.")

    # Step 4g: Export Adjudicated Gold Set (JSON & CSV)
    r_json = client.get(f"/api/sessions/{session_id}/export/json").json()
    assert r_json["count"] == 1, f"Expected exactly 1 active gold triple, got {r_json['count']}"
    assert r_json["triples"][0]["subject"] == "software_engineers"
    print(f"  • Step G [GET .../export/json]: Export returned {r_json['count']} gold triple (superseded triple excluded)")

    r_csv = client.get(f"/api/sessions/{session_id}/export/csv")
    assert r_csv.status_code == 200
    assert "software_engineers,develop,software" in r_csv.text
    print("  • Step H [GET .../export/csv]: CSV export verified and content matches canonical state.")

    # Clean up test session file
    storage_users = BACKEND_DIR / "storage" / "users"
    if storage_users.exists():
        for p in storage_users.glob(f"*/{test_session_id}.json"):
            try:
                p.unlink()
            except Exception:
                pass

    print("\n" + "=" * 70)
    print("ALL TASK 1 CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_checks()
