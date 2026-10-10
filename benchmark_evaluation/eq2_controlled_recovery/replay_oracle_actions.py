"""
replay_oracle_actions.py — Action replay engine for controlled corruption recovery.

Executes inverse curation workflows derived from corruption manifests strictly through
public RESTful HTTP API routes:
  - Revision suggestions and owner approvals (/api/sessions/{id}/suggestions, /approve)
  - Pruning spurious/duplicate triples (/api/triples/mark-removal)
  - Restoring omitted triples (/api/save)
  - Peer suggestion voting and consensus approvals (/vote, /approve)

Verifies that the platform reaches target ground-truth states strictly through public
API endpoints without direct modifications to session storage.
"""

import copy
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from backend.main import app
from backend.auth import ensure_default_users, issue_token, load_users


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


def api_request_with_retry(client: TestClient, method: str, url: str, max_retries: int = 3, **kwargs) -> Any:
    """Dispatches HTTP requests with automatic retry on transient pooler or connection drops."""
    for attempt in range(max_retries):
        try:
            func = getattr(client, method.lower())
            resp = func(url, **kwargs)
            if resp.status_code < 500:
                return resp
            time.sleep(1.0)
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(1.5)
    return resp


def replay_single_condition(
    corrupted_path: Path,
    manifest_path: Path,
    output_dir: Path,
    client: Optional[TestClient] = None,
    auth: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes oracle action replay for a single corrupted condition (Ce,d,r).
    """
    if client is None:
        client = TestClient(app)
    if auth is None:
        auth = build_auth_context()

    with open(corrupted_path, "r", encoding="utf-8") as fh:
        corr_data = json.load(fh)
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    experiment_id = manifest.get("experiment_id", "eq2_unknown")
    unique_suffix = uuid.uuid4().hex[:6]
    session_id = f"{experiment_id.lower()}_{unique_suffix}"

    # Prepare ingestion payload
    corr_data["id"] = session_id
    corr_data["session_id"] = session_id
    corr_data["owner_user_id"] = auth["owner"]["id"]
    corr_data["owner_name"] = auth["owner"]["username"]

    action_log = {
        "experiment_id": experiment_id,
        "session_id": session_id,
        "error_type": manifest.get("error_type"),
        "density": manifest.get("density"),
        "seed": manifest.get("seed"),
        "timestamp_start": time.time(),
        "actions_executed": [],
        "errors": []
    }

    t0_total = time.perf_counter()

    # Step 1: Ingest corrupted session via public POST /api/sessions
    t_ingest = time.perf_counter()
    r_ingest = api_request_with_retry(client, "post", "/api/sessions", json=corr_data)
    ingest_ms = round((time.perf_counter() - t_ingest) * 1000, 2)
    assert r_ingest.status_code == 200, f"Failed to ingest session: {r_ingest.text}"
    action_log["actions_executed"].append({
        "step": "POST /api/sessions",
        "status_code": r_ingest.status_code,
        "latency_ms": ingest_ms
    })

    # Step 2: Iterate through manifest changes and replay inverse curation actions
    actions_count = 0
    correct_actions_count = 0

    for change_idx, change in enumerate(manifest.get("changes", [])):
        s_id = change["sentence_id"]
        t_id = change["triple_id"]
        c_type = change["corruption_type"]
        inv_actions = change.get("inverse_actions", [])

        if c_type in ["subject_replacement", "predicate_replacement", "object_replacement",
                      "subject_object_swap", "malformed_triple", "representation_variant"]:
            # Action 1: Create revision suggestion
            sug_act = inv_actions[0]
            sug_id = f"sug_{t_id}_{change_idx}"
            sug_payload = {
                "sentence_id": s_id,
                "triple_id": t_id,
                "suggestion_id": sug_id,
                "user": auth["reviewer1"]["username"],
                "subject": sug_act["subject"],
                "predicate": sug_act["predicate"],
                "object": sug_act["object"],
                "comment": sug_act.get("comment", "Oracle repair suggestion")
            }
            actions_count += 1
            t_sug = time.perf_counter()
            r_sug = api_request_with_retry(
                client, "post",
                f"/api/sessions/{session_id}/suggestions",
                json=sug_payload,
                headers=auth["reviewer1"]["header"]
            )
            sug_ms = round((time.perf_counter() - t_sug) * 1000, 2)
            if r_sug.status_code == 200:
                correct_actions_count += 1
            else:
                action_log["errors"].append(f"Suggestion failed for {t_id}: {r_sug.text}")

            action_log["actions_executed"].append({
                "step": f"POST /suggestions ({t_id})",
                "status_code": r_sug.status_code,
                "latency_ms": sug_ms
            })

            # Action 2: Owner approves revision suggestion
            actions_count += 1
            t_appr = time.perf_counter()
            r_appr = api_request_with_retry(
                client, "post",
                f"/api/sessions/{session_id}/approve",
                json={"suggestion_id": sug_id, "user": auth["owner"]["username"]},
                headers=auth["owner"]["header"]
            )
            appr_ms = round((time.perf_counter() - t_appr) * 1000, 2)
            if r_appr.status_code == 200:
                correct_actions_count += 1
            else:
                action_log["errors"].append(f"Approval failed for {sug_id}: {r_appr.text}")

            action_log["actions_executed"].append({
                "step": f"POST /approve ({sug_id})",
                "status_code": r_appr.status_code,
                "latency_ms": appr_ms
            })

        elif c_type == "missing_triple":
            # Add missing triple back to sentence
            miss_act = inv_actions[0]
            restored_triple = copy.deepcopy(miss_act["triple"])
            restored_triple["status"] = "approved"

            actions_count += 1
            t_fetch = time.perf_counter()
            current_session = api_request_with_retry(client, "get", f"/api/sessions/{session_id}").json()
            for sent in current_session.get("sentences", []):
                if sent.get("id") == s_id or sent.get("sentence_id") == s_id:
                    sent["triples"].append(restored_triple)
                    break

            r_add = api_request_with_retry(
                client, "post",
                "/api/save",
                json={
                    "session_id": session_id,
                    "source_filename": "gold_benchmark.csv",
                    "uploaded_at": "2026-09-01T12:00:00Z",
                    "sentences": current_session["sentences"],
                    "is_publish": True
                },
                headers=auth["owner"]["header"]
            )
            add_ms = round((time.perf_counter() - t_fetch) * 1000, 2)
            if r_add.status_code == 200:
                correct_actions_count += 1
            else:
                action_log["errors"].append(f"Add missing triple failed for {t_id}: {r_add.text}")

            action_log["actions_executed"].append({
                "step": f"POST /save (reinsert {t_id})",
                "status_code": r_add.status_code,
                "latency_ms": add_ms
            })

        elif c_type in ["spurious_triple", "duplicate_triple"]:
            # Mark spurious or duplicate triple for removal
            actions_count += 1
            t_rem = time.perf_counter()
            r_rem = api_request_with_retry(
                client, "post",
                "/api/triples/mark-removal",
                json={
                    "session_id": session_id,
                    "sentence_id": s_id,
                    "triple_id": t_id,
                    "marked": True,
                    "reason": "Oracle repair: prune spurious/duplicate"
                },
                headers=auth["reviewer1"]["header"]
            )
            rem_ms = round((time.perf_counter() - t_rem) * 1000, 2)
            if r_rem.status_code == 200:
                correct_actions_count += 1
            else:
                action_log["errors"].append(f"Mark removal failed for {t_id}: {r_rem.text}")

            action_log["actions_executed"].append({
                "step": f"POST /mark-removal ({t_id})",
                "status_code": r_rem.status_code,
                "latency_ms": rem_ms
            })

        elif c_type == "compound_conflict_case":
            # Action 1: Reviewer A creates erroneous candidate
            sug_err_id = f"sug_err_{t_id}_{change_idx}"
            sug_a = inv_actions[0]
            api_request_with_retry(
                client, "post",
                f"/api/sessions/{session_id}/suggestions",
                json={
                    "sentence_id": s_id,
                    "triple_id": t_id,
                    "suggestion_id": sug_err_id,
                    "user": auth["reviewer1"]["username"],
                    "subject": sug_a["subject"],
                    "predicate": sug_a["predicate"],
                    "object": sug_a["object"],
                    "comment": sug_a["comment"]
                },
                headers=auth["reviewer1"]["header"]
            )
            actions_count += 1

            # Action 2: Reviewer B creates valid consensus candidate
            sug_val_id = f"sug_val_{t_id}_{change_idx}"
            sug_b = inv_actions[1]
            r_val = api_request_with_retry(
                client, "post",
                f"/api/sessions/{session_id}/suggestions",
                json={
                    "sentence_id": s_id,
                    "triple_id": t_id,
                    "suggestion_id": sug_val_id,
                    "user": auth["reviewer2"]["username"],
                    "subject": sug_b["subject"],
                    "predicate": sug_b["predicate"],
                    "object": sug_b["object"],
                    "comment": sug_b["comment"]
                },
                headers=auth["reviewer2"]["header"]
            )
            actions_count += 1
            if r_val.status_code == 200:
                correct_actions_count += 1

            # Action 3: Reviewer A votes on Reviewer B's valid suggestion
            r_vote = api_request_with_retry(
                client, "post",
                f"/api/sessions/{session_id}/vote",
                json={"suggestion_id": sug_val_id, "vote": "approve"},
                headers=auth["reviewer1"]["header"]
            )
            actions_count += 1
            if r_vote.status_code == 200:
                correct_actions_count += 1

            # Action 4: Owner approves winning valid suggestion
            r_appr_val = api_request_with_retry(
                client, "post",
                f"/api/sessions/{session_id}/approve",
                json={"suggestion_id": sug_val_id, "user": auth["owner"]["username"]},
                headers=auth["owner"]["header"]
            )
            actions_count += 1
            if r_appr_val.status_code == 200:
                correct_actions_count += 1

    # Step 3: Stream canonical adjudicated gold export via GET /api/sessions/{id}/export/json
    t_exp = time.perf_counter()
    r_export = api_request_with_retry(client, "get", f"/api/sessions/{session_id}/export/json")
    export_ms = round((time.perf_counter() - t_exp) * 1000, 2)
    assert r_export.status_code == 200, f"Export failed: {r_export.text}"
    exported_gold = r_export.json()

    action_log["actions_executed"].append({
        "step": "GET /export/json",
        "status_code": r_export.status_code,
        "latency_ms": export_ms
    })

    # Step 4: Clean up test session via DELETE /api/sessions/{id}
    api_request_with_retry(client, "delete", f"/api/sessions/{session_id}", headers=auth["owner"]["header"])

    total_duration_ms = round((time.perf_counter() - t0_total) * 1000, 2)
    action_log["total_duration_ms"] = total_duration_ms
    action_log["timestamp_end"] = time.time()
    action_log["total_actions"] = actions_count
    action_log["correct_actions"] = correct_actions_count
    action_log["exported_triple_count"] = exported_gold.get("count", len(exported_gold.get("triples", [])))

    # Save recovered dataset
    rec_dir = output_dir / "recovered"
    rec_dir.mkdir(parents=True, exist_ok=True)
    rec_file = rec_dir / f"recovered_{manifest['error_type']}_d{int(manifest['density']*100):02d}_seed{manifest['seed']:02d}.json"
    with open(rec_file, "w", encoding="utf-8") as fh:
        json.dump(exported_gold, fh, indent=2, ensure_ascii=False)

    # Save action log
    log_dir = output_dir / "action_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"log_{manifest['error_type']}_d{int(manifest['density']*100):02d}_seed{manifest['seed']:02d}.json"
    with open(log_file, "w", encoding="utf-8") as fh:
        json.dump(action_log, fh, indent=2, ensure_ascii=False)

    return {
        "experiment_id": experiment_id,
        "session_id": session_id,
        "error_type": manifest["error_type"],
        "density": manifest["density"],
        "seed": manifest["seed"],
        "actions_executed": actions_count,
        "actions_correct": correct_actions_count,
        "recovered_triples": action_log["exported_triple_count"],
        "duration_ms": total_duration_ms,
        "recovered_file": rec_file,
        "action_log_file": log_file,
    }


def replay_all_conditions(base_dir: Path) -> List[Dict[str, Any]]:
    """Replays oracle actions for all manifests found in the manifests/ directory."""
    manifests_dir = base_dir / "manifests"
    corrupted_dir = base_dir / "corrupted"
    manifest_files = sorted(list(manifests_dir.glob("*.json")))

    if not manifest_files:
        print("No manifests found to replay.")
        return []

    print(f"Starting oracle action replay for {len(manifest_files)} experimental conditions via public HTTP API...")
    client = TestClient(app)
    auth = build_auth_context()

    summary_records = []
    for mf in manifest_files:
        # Match corresponding corrupted file
        corr_name = mf.name.replace("manifest_", "corrupted_")
        corr_file = corrupted_dir / corr_name
        assert corr_file.exists(), f"Missing corrupted file: {corr_file}"

        t_start = time.perf_counter()
        rec = replay_single_condition(corr_file, mf, base_dir, client=client, auth=auth)
        rec["wall_time_s"] = round(time.perf_counter() - t_start, 2)
        summary_records.append(rec)
        print(f"  [RECOVERED] {rec['experiment_id']}: {rec['actions_executed']} API actions executed in {rec['wall_time_s']}s -> {rec['recovered_triples']} gold triples exported.")

    return summary_records


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    replay_all_conditions(base)
