"""
test_review_findings.py — Regression tests for issues found by an independent review of the
save, versioning, and account rules. Each test reproduces the reviewer's scenario with the payload
shape the browser sends.
"""

import copy
import uuid

# Importing these first forces isolated local storage before any backend import.
from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (  # noqa: F401
    auth_context,
    client,
)
from benchmark_evaluation.eq1_workflow_correctness.test_ui_save_flows import (  # noqa: E402
    _comment, _new_session, _save, _stored_triple, _view,
)
from backend.auth import issue_token  # noqa: E402


def _publish(client, sid, sentences, name=None, header=None):
    body = {"session_id": sid, "source_filename": "s.json", "uploaded_at": "2026-09-01T12:00:00Z",
            "sentences": sentences, "is_publish": True}
    if name:
        body["version_name"] = name
    return client.post("/api/save", json=body, headers=header) if header else client.post("/api/save", json=body)


def _register(client, username=None, name=None):
    username = username or f"u{uuid.uuid4().hex[:10]}"
    r = client.post("/api/auth/register", headers={"Authorization": ""}, json={
        "username": username, "name": name or username, "email": f"{username}.{uuid.uuid4().hex[:6]}@example.com",
        "password": "fixture-password-1", "security_question": "Favourite fixture colour?", "security_answer": "blue"})
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    return uid, {"Authorization": f"Bearer {issue_token(uid)}"}


def _add_suggestion(client, sid, rev):
    view = _view(client, sid, rev["header"])
    view["sentences"][0]["triples"][0]["suggestions"] = [{
        "id": "sug-x", "author": rev["username"], "user_id": rev["id"], "subject": "Code_001", "predicate": "includes",
        "object": "parts", "reason": "", "status": "pending", "votes": {}, "replies": [], "created_at": "2026-10-13T10:00:00Z"}]
    assert _save(client, rev["header"], view, view["sentences"]).status_code == 200


def test_approve_then_unapprove_keeps_grades(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    for rev, g in ((rev1, 8), (rev2, 9)):
        view = _view(client, sid, rev["header"])
        view["sentences"][0]["triples"][0]["grade"] = g
        assert _save(client, rev["header"], view, view["sentences"]).status_code == 200
    _add_suggestion(client, sid, rev1)

    owner_view = _view(client, sid)
    sentences = copy.deepcopy(owner_view["sentences"])
    t1, sug = sentences[0]["triples"][0], sentences[0]["triples"][0]["suggestions"][0]
    original = {k: t1[k] for k in ("subject", "predicate", "object", "author")}
    sug["approved_from"] = original
    t1.update({k: sug[k] for k in ("subject", "predicate", "object")})
    sug.update({"status": "approved", "approved_by": "user_ysh"})
    assert _save(client, None, owner_view, sentences).status_code == 200
    # Unapprove from the same page: original wording comes back.
    t1.update({k: original[k] for k in ("subject", "predicate", "object")})
    sug.pop("approved_from")
    sug.update({"status": "pending", "approved_by": None})
    assert _save(client, None, owner_view, sentences).status_code == 200

    _, t = _stored_triple(client, sid)
    assert {rev1["id"], rev2["id"]} <= set(t["grades_by_user"])
    assert _publish(client, sid, _view(client, sid)["sentences"], "V1").status_code == 200
    v1 = next(v for v in client.get(f"/api/sessions/{sid}").json()["versions"] if v["name"] == "V1")
    p1 = v1["sentences"][0]["triples"][0]
    assert {rev1["id"], rev2["id"]} <= set(p1["grades_by_user"]) and not p1.get("is_modified_in_version")


def test_publish_resets_sentence_ratings_only_where_triples_changed(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["completeness"] = 7
    view["sentences"][1]["completeness"] = 9
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    owner_view = _view(client, sid)
    sentences = copy.deepcopy(owner_view["sentences"])
    sentences[0]["triples"][0]["object"] = "edited_before_first_publish"
    assert _save(client, None, owner_view, sentences).status_code == 200  # owner edit on the unpublished version
    assert _publish(client, sid, _view(client, sid)["sentences"], "V1").status_code == 200
    v1 = next(v for v in client.get(f"/api/sessions/{sid}").json()["versions"] if v["name"] == "V1")
    # The grader's rating was given for the old triple set and is dropped (fixture ratings without a
    # recorded triple set are legacy data and are not part of this check).
    assert rev1["id"] not in v1["sentences"][0]["completeness_by_user"]
    assert rev1["id"] in v1["sentences"][1]["completeness_by_user"]


def test_old_version_view_is_read_only_and_active_version_stays(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    assert _publish(client, sid, _view(client, sid)["sentences"], "V1").status_code == 200
    owner_old = client.get(f"/api/session/{sid}?version_name=Initial").json()
    owner_old["sentences"][0]["triples"][0]["triple_comments"] = [_comment({"username": "user_ysh", "id": "x"}, "c")]
    assert _save(client, None, owner_old, owner_old["sentences"]).status_code == 409
    assert client.get(f"/api/sessions/{sid}").json()["current_version_name"] == "V1"
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["grade"] = 9
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200


def test_grader_recovers_after_owner_deletes_active_version(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    assert _publish(client, sid, _view(client, sid)["sentences"], "V1").status_code == 200
    stale = _view(client, sid, rev1["header"])
    assert client.delete(f"/api/session/{sid}/version/V1").status_code == 200
    stale["sentences"][0]["triples"][0]["grade"] = 9
    assert _save(client, rev1["header"], stale, stale["sentences"]).status_code == 409
    fresh = _view(client, sid, rev1["header"])
    fresh["sentences"][0]["triples"][0]["grade"] = 9
    assert _save(client, rev1["header"], fresh, fresh["sentences"]).status_code == 200


def test_released_username_does_not_transfer_ownership(client):
    owner_id, owner_h = _register(client)
    old_username = client.get("/api/auth/me", headers=owner_h).json()["username"]
    sid = f"own_{uuid.uuid4().hex[:8]}"
    assert client.post("/api/sessions", headers=owner_h, json={"id": sid, "sentences": []}).status_code == 200
    assert client.put("/api/auth/profile", headers=owner_h, json={"username": f"n{uuid.uuid4().hex[:10]}"}).status_code == 200
    _, attacker_h = _register(client, username=old_username)
    view = client.get(f"/api/session/{sid}", headers=attacker_h).json()
    assert view.get("can_approve") is not True
    assert client.get(f"/api/sessions/{sid}/export/json", headers=attacker_h).status_code == 403
    assert client.get(f"/api/session/{sid}", headers=owner_h).json().get("can_approve") is True


def test_profile_name_cannot_forge_another_users_vote(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    _add_suggestion(client, sid, rev1)
    view2 = _view(client, sid, rev2["header"])
    view2["sentences"][0]["triples"][0]["suggestions"][0]["votes"] = {"user_rl": "yes"}
    assert _save(client, rev2["header"], view2, view2["sentences"]).status_code == 200
    _, attacker_h = _register(client, name="user_rl")
    view3 = _view(client, sid, attacker_h)
    view3["sentences"][0]["triples"][0]["suggestions"][0]["votes"] = {"user_rl": "no"}
    assert _save(client, attacker_h, view3, view3["sentences"]).status_code == 200
    _, t = _stored_triple(client, sid)
    assert t["suggestions"][0]["votes"].get("user_rl") == "yes"


def test_removal_request_is_filed_under_the_caller(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    view = _view(client, sid, rev2["header"])
    t2 = view["sentences"][0]["triples"][1]
    t2.update({"marked_for_removal": True, "removal_reason": "dup", "marked_for_removal_by": rev1["id"],
               "marked_for_removal_by_name": "user_jw"})
    assert _save(client, rev2["header"], view, view["sentences"]).status_code == 200
    _, stored = _stored_triple(client, sid, "t00002")
    assert stored["marked_for_removal"] is True and stored["marked_for_removal_by"] == rev2["id"]


def test_duplicate_triple_ids_do_not_duplicate_triples(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"].append(copy.deepcopy(view["sentences"][0]["triples"][0]))
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    s, _ = _stored_triple(client, sid)
    assert [t["id"] for t in s["triples"]] == ["t00001", "t00002"]


def test_session_list_hides_peer_summaries_from_graders(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["grade"] = 3
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    rows = client.get("/api/sessions", headers=rev2["header"]).json()
    rows = rows.get("sessions", rows) if isinstance(rows, dict) else rows
    entry = next(r for r in rows if r["session_id"] == sid)
    assert all(row.get("user_id") == rev2["id"] for row in entry["grader_summary"])
    assert entry["session_average_grade"] is None


def test_security_question_change_needs_current_password(client):
    _, h = _register(client)
    body = {"security_question": "What was the name of your first pet?", "security_answer": "rex"}
    assert client.put("/api/auth/profile", headers=h, json=body).status_code == 400
    body["current_password"] = "fixture-password-1"
    assert client.put("/api/auth/profile", headers=h, json=body).status_code == 200


def test_reset_limit_is_per_account(client):
    uid, _ = _register(client)
    me = next(u for u in __import__("backend.auth", fromlist=["load_users"]).load_users()["users"] if u["id"] == uid)
    anon = {"Authorization": ""}
    codes = []
    for login in [me["username"]] * 3 + [me["email"]] * 3:
        codes.append(client.post("/api/auth/forgot-password/reset", headers=anon,
                                 json={"login": login, "answer": "wrong", "password": "whatever-pass-1"}).status_code)
    assert codes[:5] == [400] * 5 and codes[5] == 429


def test_grader_can_delete_own_replies(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    _add_suggestion(client, sid, rev1)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["sentence_comments"] = [_comment(rev1, "sentence note")]
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200

    reply = {"author": "user_rl", "user_id": rev2["id"], "text": "r", "created_at": "2026-10-13T10:05:00Z",
             "parent_reply_id": None}
    view2 = _view(client, sid, rev2["header"])
    view2["sentences"][0]["sentence_comments"][0]["replies"] = [{**reply, "id": "rs"}]
    view2["sentences"][0]["triples"][0]["suggestions"][0]["replies"] = [{**reply, "id": "rg"}]
    assert _save(client, rev2["header"], view2, view2["sentences"]).status_code == 200

    view2 = _view(client, sid, rev2["header"])
    view2["sentences"][0]["sentence_comments"][0]["replies"] = []
    view2["sentences"][0]["triples"][0]["suggestions"][0]["replies"] = []
    assert _save(client, rev2["header"], view2, view2["sentences"]).status_code == 200
    s, t = _stored_triple(client, sid)
    assert s["sentence_comments"][0].get("replies", []) == []
    assert t["suggestions"][0].get("replies", []) == []


def test_owner_changes_reach_graders_after_publish(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    assert _publish(client, sid, _view(client, sid)["sentences"], "V1").status_code == 200
    owner_view = _view(client, sid)
    owner_view["sentences"][0]["triples"][0]["triple_comments"] = [
        {"id": "oc", "author": "user_ysh", "user_id": auth_context["owner"]["id"], "text": "owner note",
         "created_at": "2026-10-13T12:00:00Z", "replies": []}]
    assert _save(client, None, owner_view, owner_view["sentences"]).status_code == 200
    grader_view = _view(client, sid, rev1["header"])
    assert [c["text"] for c in grader_view["sentences"][0]["triples"][0]["triple_comments"]] == ["owner note"]


def test_publish_without_name_gets_an_automatic_name(client):
    sid = _new_session(client)
    sentences = _view(client, sid)["sentences"]
    body = {"session_id": sid, "source_filename": "s.json", "uploaded_at": "2026-09-01T12:00:00Z",
            "sentences": sentences, "is_publish": True, "current_version_name": "Initial"}
    r = client.post("/api/save", json=body)
    assert r.status_code == 200, r.text
    names = [v["name"] for v in client.get(f"/api/sessions/{sid}").json()["versions"]]
    assert names == ["Initial", "Version 2"]


def test_grade_keeps_its_wording_after_an_approved_revision(client, auth_context):
    """A grade given for the old wording is not re-stamped by later saves, and other graders' grades
    for the new wording survive those saves."""
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    for rev, g in ((rev1, 8), (rev2, 9)):
        view = _view(client, sid, rev["header"])
        view["sentences"][0]["triples"][0]["grade"] = g
        assert _save(client, rev["header"], view, view["sentences"]).status_code == 200
    _add_suggestion(client, sid, rev1)

    s, t = _stored_triple(client, sid)
    sentence_id = int(str(s["id"]).lstrip("s") or 0)
    r = client.post("/api/suggestions/approve", json={
        "session_id": sid, "sentence_id": sentence_id, "triple_id": t["id"], "suggestion_id": "sug-x"})
    assert r.status_code == 200, r.text
    assert _stored_triple(client, sid)[1]["object"] == "parts"

    # rev2 grades the new wording; rev1 only comments, sending back the grade it gave the old wording.
    view = _view(client, sid, rev2["header"])
    view["sentences"][0]["triples"][0]["grade"] = 5
    assert _save(client, rev2["header"], view, view["sentences"]).status_code == 200
    view = _view(client, sid, rev1["header"])
    assert view["sentences"][0]["triples"][0]["grade"] == 8
    view["sentences"][0]["triples"][0]["triple_comments"] = [_comment(rev1, "looks fine")]
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200

    assert _publish(client, sid, _view(client, sid)["sentences"], "V1").status_code == 200
    v1 = next(v for v in client.get(f"/api/sessions/{sid}").json()["versions"] if v["name"] == "V1")
    p1 = v1["sentences"][0]["triples"][0]
    assert p1["object"] == "parts"
    # Only the grade given for the new wording is carried into V1, and the triple is flagged.
    assert set(p1["grades_by_user"]) == {rev2["id"]} and p1["grades_by_user"][rev2["id"]]["grade"] == 5
    assert p1.get("is_modified_in_version")


def _save_full(client, header, view):
    """Saves the view's triples with every field, as the current browser build sends them."""
    return client.post("/api/save", headers=header, json={
        "session_id": view["session_id"], "source_filename": view.get("source_filename") or "sample.json",
        "uploaded_at": view.get("uploaded_at") or "2026-09-01T12:00:00Z", "manual_mode": False,
        "current_version_name": view.get("current_version_name"), "sentences": view["sentences"]})


def test_each_grader_files_their_own_deletion_request(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    for rev, grade in ((rev1, 2), (rev2, 3)):
        view = _view(client, sid, rev["header"])
        t = view["sentences"][0]["triples"][0]
        t["grade"] = grade
        t["removal_requests"] = {**(t.get("removal_requests") or {}),
                                 rev["id"]: {"user_id": rev["id"], "user_name": rev["username"], "reason": "wrong"}}
        assert _save_full(client, rev["header"], view).status_code == 200
    _, t = _stored_triple(client, sid)
    assert set(t["removal_requests"]) == {rev1["id"], rev2["id"]} and t["marked_for_removal"] is True

    # rev2 withdraws only their own request; rev1's request stays.
    view = _view(client, sid, rev2["header"])
    t = view["sentences"][0]["triples"][0]
    t["removal_requests"] = {k: v for k, v in t["removal_requests"].items() if k != rev2["id"]}
    assert _save_full(client, rev2["header"], view).status_code == 200
    _, t = _stored_triple(client, sid)
    assert set(t["removal_requests"]) == {rev1["id"]} and t["marked_for_removal_by"] == rev1["id"]

    # A grader cannot withdraw another grader's request.
    view = _view(client, sid, rev2["header"])
    view["sentences"][0]["triples"][0]["removal_requests"] = {}
    assert _save_full(client, rev2["header"], view).status_code == 200
    _, t = _stored_triple(client, sid)
    assert set(t["removal_requests"]) == {rev1["id"]}
    # Both graders' grades on the requested triple are kept.
    assert {rev1["id"], rev2["id"]} <= set(t["grades_by_user"])


def test_grader_can_remove_and_restore_their_grading(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    _add_suggestion(client, sid, rev1)  # rev1's pending suggestion "sug-x" on the first triple
    view = _view(client, sid, rev1["header"])
    s0 = view["sentences"][0]
    t = s0["triples"][0]
    t["grade"] = 8
    t["triple_comments"] = [_comment(rev1, "my note")]
    t["removal_requests"] = {rev1["id"]: {"user_id": rev1["id"], "user_name": rev1["username"], "reason": "dup"}}
    s0["completeness"] = 7
    assert _save_full(client, rev1["header"], view).status_code == 200
    view = _view(client, sid, rev2["header"])
    view["sentences"][0]["triples"][0]["grade"] = 9
    assert _save_full(client, rev2["header"], view).status_code == 200

    # The owner does not grade, so there is nothing to remove.
    assert client.post(f"/api/session/{sid}/withdraw-grading").status_code == 403

    r = client.post(f"/api/session/{sid}/withdraw-grading", headers=rev1["header"])
    assert r.status_code == 200, r.text
    s, t = _stored_triple(client, sid)
    assert rev1["id"] not in t["grades_by_user"] and rev2["id"] in t["grades_by_user"]
    assert not t.get("triple_comments") and not t.get("suggestions")
    assert rev1["id"] not in (t.get("removal_requests") or {}) and not t.get("marked_for_removal")
    assert rev1["id"] not in (s.get("completeness_by_user") or {})
    mine = _view(client, sid, rev1["header"])
    assert mine.get("can_restore_my_grading") is True
    # The backup of removed work is never sent to anyone.
    for header in (rev1["header"], rev2["header"], None):
        assert "withdrawn_grading" not in _view(client, sid, header)

    r = client.post(f"/api/session/{sid}/restore-grading", headers=rev1["header"])
    assert r.status_code == 200, r.text
    s, t = _stored_triple(client, sid)
    assert {rev1["id"], rev2["id"]} <= set(t["grades_by_user"])
    assert [c["text"] for c in t["triple_comments"]] == ["my note"]
    assert [x["id"] for x in t["suggestions"]] == ["sug-x"]
    assert rev1["id"] in t["removal_requests"] and t["marked_for_removal"] is True
    assert rev1["id"] in s["completeness_by_user"]
    assert _view(client, sid, rev1["header"]).get("can_restore_my_grading") is False
    assert client.post(f"/api/session/{sid}/restore-grading", headers=rev1["header"]).status_code == 404


def test_upload_then_review_publish_keeps_each_triple_once(client):
    import json as _json
    upload = {"sentences": [{"text": "WT1 induces E-cadherin.", "triples": [
        {"id": "t054", "subject": "p(MGI:Wt1)", "predicate": "increases", "object": "r(MGI:Cdh1)"}]}]}
    r = client.post("/api/upload", files={"file": ("cand.json", _json.dumps(upload).encode(), "application/json")})
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    # The review screen renumbers triple ids as "<sentence>_<n>" before the first save.
    sentences = [{"id": 1, "text": "WT1 induces E-cadherin.", "suggestion": "", "triples": [
        {"id": "1_1", "subject": "p(MGI:Wt1)", "predicate": "increases", "object": "r(MGI:Cdh1)",
         "is_placeholder": False, "note": "", "grade": None}]}]
    body = {"session_id": sid, "source_filename": "cand.json", "uploaded_at": "2026-10-28T12:00:00Z",
            "manual_mode": False, "total_sentences": 1, "sentences": sentences}
    assert client.post("/api/save", json=body).status_code == 200
    assert len(_view(client, sid)["sentences"][0]["triples"]) == 1
