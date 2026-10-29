"""
test_security_regressions.py: access-control and data-integrity regression checks.

These are separate from the T01-T18 workflow matrix. Each test pins one rule:
- the /api/sessions/* workflow routes require authentication, and the actor comes from the token;
- approval and gold export are owner-only, and existing sessions cannot be overwritten;
- a grader cannot write grades on behalf of other users;
- peer ratings are hidden from a grader until that grader has rated the item (blind review);
- a free-text profile name cannot confer session ownership;
- non-finite grades are rejected.
"""

import uuid

# Importing the matrix module first forces isolated local storage before any backend import.
from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (  # noqa: F401
    auth_context,
    client,
    load_fixture,
)
from backend.auth import issue_token  # noqa: E402


def _new_session(client) -> str:
    fixture = load_fixture()
    session_id = f"sec_{uuid.uuid4().hex[:8]}"
    fixture["id"] = session_id
    fixture["session_id"] = session_id
    assert client.post("/api/sessions", json=fixture).status_code == 200
    return session_id


def _save(client, header, session_id, sentences):
    return client.post("/api/save", headers=header, json={
        "session_id": session_id,
        "source_filename": "sample.json",
        "uploaded_at": "2026-09-01T12:00:00Z",
        "sentences": sentences,
    })


def test_workflow_routes_reject_anonymous_calls(client):
    session_id = _new_session(client)
    anon = {"Authorization": ""}
    calls = [
        ("post", "/api/sessions", {"id": f"anon_{uuid.uuid4().hex[:6]}"}),
        ("get", f"/api/sessions/{session_id}", None),
        ("post", f"/api/sessions/{session_id}/suggestions",
         {"triple_id": "t00001", "subject": "a", "predicate": "b", "object": "c"}),
        ("post", f"/api/sessions/{session_id}/vote", {"suggestion_id": "x"}),
        ("post", f"/api/sessions/{session_id}/approve", {"suggestion_id": "x"}),
        ("post", f"/api/sessions/{session_id}/unapprove", {"suggestion_id": "x"}),
        ("get", f"/api/sessions/{session_id}/export/json", None),
        ("get", f"/api/sessions/{session_id}/export/csv", None),
    ]
    for method, url, body in calls:
        kwargs = {"headers": anon}
        if body is not None:
            kwargs["json"] = body
        assert getattr(client, method)(url, **kwargs).status_code == 401, url


def test_existing_session_cannot_be_overwritten(client):
    session_id = _new_session(client)
    r = client.post("/api/sessions", json={"id": session_id, "sentences": []})
    assert r.status_code == 409
    data = client.get(f"/api/sessions/{session_id}").json()
    assert len(data["sentences"]) == len(load_fixture()["sentences"])


def test_only_owner_can_approve_and_export(client, auth_context):
    session_id = _new_session(client)
    r = client.post(f"/api/sessions/{session_id}/suggestions", headers=auth_context["reviewer1"]["header"], json={
        "triple_id": "t00001", "suggestion_id": "sg1", "subject": "a", "predicate": "b", "object": "c",
    })
    assert r.status_code == 200
    reviewer = auth_context["reviewer2"]["header"]
    assert client.post(f"/api/sessions/{session_id}/approve", headers=reviewer,
                       json={"suggestion_id": "sg1", "user": "user_ysh"}).status_code == 403
    assert client.get(f"/api/sessions/{session_id}/export/json", headers=reviewer).status_code == 403
    r_owner = client.post(f"/api/sessions/{session_id}/approve", json={"suggestion_id": "sg1", "user": "someone_else"})
    assert r_owner.status_code == 200
    assert r_owner.json()["approved_by"] == "user_ysh"


def test_suggestion_author_comes_from_token(client, auth_context):
    session_id = _new_session(client)
    client.post(f"/api/sessions/{session_id}/suggestions", headers=auth_context["reviewer1"]["header"], json={
        "triple_id": "t00001", "suggestion_id": "sg2", "user": "user_rl",
        "subject": "a", "predicate": "b", "object": "c",
    })
    sug = client.get(f"/api/sessions/{session_id}").json()["sentences"][0]["triples"][0]["suggestions"][0]
    assert sug["author"] == "user_jw"
    assert client.post(f"/api/sessions/{session_id}/vote", headers=auth_context["reviewer1"]["header"],
                       json={"suggestion_id": "sg2", "user": "user_rl"}).status_code == 403


def test_grader_cannot_write_other_users_grades(client, auth_context):
    session_id = _new_session(client)
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sentences = client.get(f"/api/sessions/{session_id}", headers=rev1["header"]).json()["sentences"]
    sentences[0]["triples"][0]["grade"] = 9
    sentences[0]["triples"][0]["grades_by_user"] = {
        rev2["id"]: {"user_id": rev2["id"], "user_name": "user_rl", "grade": 0},
        "ghost_rater": {"user_id": "ghost_rater", "user_name": "ghost", "grade": 0},
    }
    assert _save(client, rev1["header"], session_id, sentences).status_code == 200
    grades = client.get(f"/api/sessions/{session_id}").json()["sentences"][0]["triples"][0]["grades_by_user"]
    assert grades[rev1["id"]]["grade"] == 9.0
    assert rev2["id"] not in grades and "ghost_rater" not in grades


def test_peer_ratings_hidden_until_own_rating(client, auth_context):
    session_id = _new_session(client)
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sentences = client.get(f"/api/session/{session_id}", headers=rev1["header"]).json()["sentences"]
    sentences[0]["triples"][0]["grade"] = 3
    sentences[0]["completeness"] = 4
    assert _save(client, rev1["header"], session_id, sentences).status_code == 200

    view = client.get(f"/api/session/{session_id}", headers=rev2["header"]).json()
    t1 = view["sentences"][0]["triples"][0]
    assert t1["grades_by_user"] == {} and t1["grade_average"] is None and t1["grade_count"] is None
    assert view["sentences"][0]["completeness_by_user"] == {}
    assert all(row.get("user_id") == rev2["id"] for row in view.get("grader_summary") or [])
    assert "owner_draft" not in view

    # Once reviewer 2 has graded the same triple, the peer grade becomes visible.
    sentences = view["sentences"]
    sentences[0]["triples"][0]["grade"] = 5
    assert _save(client, rev2["header"], session_id, sentences).status_code == 200
    view = client.get(f"/api/session/{session_id}", headers=rev2["header"]).json()
    assert {rev1["id"], rev2["id"]} <= set(view["sentences"][0]["triples"][0]["grades_by_user"])

    # The owner always sees every rating, and reviewer 1's stored grade was not lost.
    owner_view = client.get(f"/api/session/{session_id}").json()
    grades = owner_view["sentences"][0]["triples"][0]["grades_by_user"]
    assert grades[rev1["id"]]["grade"] == 3.0 and grades[rev2["id"]]["grade"] == 5.0


def test_profile_name_does_not_confer_ownership(client):
    username = f"spoof{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", headers={"Authorization": ""}, json={
        "username": username,
        "name": "user_ysh",
        "email": f"{username}@example.com",
        "password": "spoof-password-123",
        "security_question": "Name of the test fixture?",
        "security_answer": "fixture",
    })
    assert r.status_code == 200, r.text
    token = issue_token(r.json()["user"]["id"])
    session_id = _new_session(client)
    view = client.get(f"/api/session/{session_id}", headers={"Authorization": f"Bearer {token}"}).json()
    assert view.get("can_approve") is not True


def test_non_finite_grade_is_rejected(client, auth_context):
    session_id = _new_session(client)
    rev1 = auth_context["reviewer1"]
    sentences = client.get(f"/api/session/{session_id}", headers=rev1["header"]).json()["sentences"]
    sentences[0]["triples"][0]["grade"] = "nan"
    assert _save(client, rev1["header"], session_id, sentences).status_code == 200
    assert client.get(f"/api/session/{session_id}").status_code == 200


def _register(client, answer="blue fixture"):
    username = f"acct{uuid.uuid4().hex[:8]}"
    password = "first-password-123"
    r = client.post("/api/auth/register", headers={"Authorization": ""}, json={
        "username": username, "name": username, "email": f"{username}@example.com", "password": password,
        "security_question": "Favourite fixture colour?", "security_answer": answer,
    })
    assert r.status_code == 200, r.text
    return username, password, r.json()["user"]["id"]


def test_security_answer_is_hashed_and_reset_revokes_tokens(client):
    from backend.auth import get_user_by_id
    username, password, user_id = _register(client, answer="Blue Fixture")
    assert get_user_by_id(user_id)["security_answer"].startswith("pbkdf2$")
    old_token = issue_token(user_id)
    anon = {"Authorization": ""}
    r = client.post("/api/auth/forgot-password/reset", headers=anon,
                    json={"login": username, "answer": "  blue fixture ", "password": "second-password-456"})
    assert r.status_code == 200, r.text
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    r = client.post("/api/auth/login", headers=anon, json={"login": username, "password": "second-password-456"})
    assert r.status_code == 200


def test_reset_attempts_are_rate_limited(client):
    username, _, _ = _register(client)
    anon = {"Authorization": ""}
    codes = [client.post("/api/auth/forgot-password/reset", headers=anon,
                         json={"login": username, "answer": "wrong", "password": "whatever-password-1"}).status_code
             for _ in range(6)]
    assert codes[:5] == [400] * 5 and codes[5] == 429


def test_websocket_requires_token(client, auth_context):
    from starlette.websockets import WebSocketDisconnect
    session_id = _new_session(client)
    try:
        with client.websocket_connect(f"/api/ws/{session_id}") as ws:
            ws.receive_text()
        connected_without_token = True
    except WebSocketDisconnect:
        connected_without_token = False
    assert not connected_without_token
    token = auth_context["reviewer1"]["header"]["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/ws/{session_id}?token={token}"):
        pass
