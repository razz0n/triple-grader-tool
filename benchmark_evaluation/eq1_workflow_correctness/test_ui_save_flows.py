"""
test_ui_save_flows.py: in the browser, grading, commenting, suggesting, voting and approving all
go through full-session saves (/api/save). These tests send the payload the frontend sends
(GradingForm.saveStateInstantly) and check both the permitted flows and the rules that protect
other users' data.
"""

import copy
import uuid

# Importing the matrix module first forces isolated local storage before any backend import.
from benchmark_evaluation.eq1_workflow_correctness.test_workflow_matrix import (  # noqa: F401
    auth_context,
    client,
    load_fixture,
)

TRIPLE_FIELDS = ("id", "subject", "predicate", "object", "grade", "author", "grades_by_user", "is_new_suggestion",
                 "status", "suggested_by", "marked_for_removal", "removal_reason", "marked_for_removal_by",
                 "marked_for_removal_by_name", "triple_comments", "suggestions")
SENTENCE_FIELDS = ("id", "text", "completeness", "external_relation", "completeness_by_user",
                   "external_relation_by_user", "sentence_comments")


def _new_session(client) -> str:
    fixture = load_fixture()
    for s in fixture["sentences"]:
        s.setdefault("text", s.get("sentence"))
        for t in s.get("triples", []):
            t.setdefault("polarity", "affirmative")
            t.setdefault("modality", "obligation")
    session_id = f"ui_{uuid.uuid4().hex[:8]}"
    fixture["id"] = session_id
    fixture["session_id"] = session_id
    assert client.post("/api/sessions", json=fixture).status_code == 200
    return session_id


def _view(client, session_id, header=None):
    r = client.get(f"/api/session/{session_id}", headers=header) if header else client.get(f"/api/session/{session_id}")
    assert r.status_code == 200, r.text
    return r.json()


def _save(client, header, view, sentences):
    """Sends the payload exactly as GradingForm.saveStateInstantly builds it."""
    payload = {
        "session_id": view["session_id"],
        "source_filename": view.get("source_filename") or "sample.json",
        "uploaded_at": view.get("uploaded_at") or "2026-09-01T12:00:00Z",
        "manual_mode": False,
        "current_version_name": view.get("current_version_name"),
        "sentences": [
            {**{k: s.get(k) for k in SENTENCE_FIELDS},
             "triples": [{k: t.get(k) for k in TRIPLE_FIELDS} for t in s.get("triples", [])]}
            for s in sentences
        ],
    }
    return client.post("/api/save", headers=header, json=payload)


def _stored_triple(client, session_id, triple_id="t00001"):
    owner_view = _view(client, session_id)
    for s in owner_view["sentences"]:
        for t in s["triples"]:
            if t["id"] == triple_id:
                return s, t
    return None, None


def _comment(user, text):
    return {"id": f"c-{uuid.uuid4().hex[:6]}", "author": user["username"], "user_id": user["id"], "text": text,
            "created_at": "2026-10-13T10:00:00Z", "replies": []}


# Permitted flows


def test_grader_comment_reply_and_delete_own(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    c = _comment(rev1, "check modality")
    view["sentences"][0]["triples"][0]["triple_comments"] = [c]
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200

    view2 = _view(client, sid, rev2["header"])
    reply = {"id": "r-1", "author": "user_rl", "user_id": rev2["id"], "text": "agree",
             "created_at": "2026-10-13T10:01:00Z", "parent_reply_id": None}
    view2["sentences"][0]["triples"][0]["triple_comments"][0]["replies"] = [reply]
    assert _save(client, rev2["header"], view2, view2["sentences"]).status_code == 200
    _, t = _stored_triple(client, sid)
    assert [r["text"] for r in t["triple_comments"][0]["replies"]] == ["agree"]

    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["triple_comments"] = []
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    _, t = _stored_triple(client, sid)
    assert t["triple_comments"] == []


def test_grader_suggestion_edit_vote_delete(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    sug = {"id": "sug-1", "author": "user_jw", "user_id": rev1["id"], "subject": "a", "predicate": "b",
           "object": "c", "reason": "", "status": "pending", "votes": {}, "replies": [],
           "created_at": "2026-10-13T10:00:00Z"}
    view["sentences"][0]["triples"][0]["suggestions"] = [sug]
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200

    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["suggestions"][0]["object"] = "c2"
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200

    view2 = _view(client, sid, rev2["header"])
    view2["sentences"][0]["triples"][0]["suggestions"][0]["votes"] = {"user_rl": "yes"}
    assert _save(client, rev2["header"], view2, view2["sentences"]).status_code == 200
    _, t = _stored_triple(client, sid)
    assert t["suggestions"][0]["object"] == "c2"
    assert t["suggestions"][0]["votes"] == {"user_rl": "yes"}

    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["suggestions"] = []
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    _, t = _stored_triple(client, sid)
    assert t["suggestions"] == []


def test_grader_new_triple_and_removal_request(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    new_t = {"id": "suggested-1", "subject": "x", "predicate": "y", "object": "z", "grade": None,
             "author": "user_jw", "grades_by_user": {}, "is_new_suggestion": True, "status": "pending",
             "suggested_by": "user_jw", "marked_for_removal": False, "removal_reason": "",
             "triple_comments": [], "suggestions": []}
    view["sentences"][0]["triples"].append(new_t)
    view["sentences"][0]["triples"][1]["marked_for_removal"] = True
    view["sentences"][0]["triples"][1]["removal_reason"] = "Requested removal"
    view["sentences"][0]["triples"][1]["marked_for_removal_by"] = rev1["id"]
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    s, t = _stored_triple(client, sid, "suggested-1")
    assert t is not None and t["status"] == "pending"
    assert s["triples"][1]["marked_for_removal"] is True

    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"] = [t for t in view["sentences"][0]["triples"] if t["id"] != "suggested-1"]
    view["sentences"][0]["triples"][1]["marked_for_removal"] = False
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    _, t = _stored_triple(client, sid, "suggested-1")
    assert t is None
    _, t2 = _stored_triple(client, sid, "t00002")
    assert t2["marked_for_removal"] is False


def test_owner_approves_suggestion_and_new_triple(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["grade"] = 9
    view["sentences"][0]["triples"][0]["suggestions"] = [{
        "id": "sug-2", "author": "user_jw", "user_id": rev1["id"], "subject": "Code_001", "predicate": "includes",
        "object": "parts", "reason": "", "status": "pending", "votes": {}, "replies": [],
        "created_at": "2026-10-13T10:00:00Z"}]
    view["sentences"][0]["triples"].append({
        "id": "suggested-2", "subject": "x", "predicate": "y", "object": "z", "grade": None, "author": "user_jw",
        "grades_by_user": {}, "is_new_suggestion": True, "status": "pending", "suggested_by": "user_jw",
        "marked_for_removal": False, "removal_reason": "", "triple_comments": [], "suggestions": []})
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200

    owner_view = _view(client, sid)
    sentences = copy.deepcopy(owner_view["sentences"])
    t1 = sentences[0]["triples"][0]
    sug = t1["suggestions"][0]
    sug["approved_from"] = {k: t1[k] for k in ("subject", "predicate", "object", "author")}
    t1.update({k: sug[k] for k in ("subject", "predicate", "object")})
    sug.update({"status": "approved", "approved_by": "user_ysh", "approved_at": "2026-10-13T11:00:00Z"})
    for t in sentences[0]["triples"]:
        if t["id"] == "suggested-2":
            t["status"] = "approved"
    assert _save(client, None, owner_view, sentences).status_code == 200

    s, t = _stored_triple(client, sid)
    assert (t["subject"], t["predicate"], t["object"]) == ("Code_001", "includes", "parts")
    assert t["suggestions"][0]["status"] == "approved"
    assert next(x for x in s["triples"] if x["id"] == "suggested-2")["status"] == "approved"


def test_owner_deletes_grader_comment(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["triple_comments"] = [_comment(rev1, "spam")]
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    owner_view = _view(client, sid)
    owner_view["sentences"][0]["triples"][0]["triple_comments"] = []
    assert _save(client, None, owner_view, owner_view["sentences"]).status_code == 200
    _, t = _stored_triple(client, sid)
    assert t["triple_comments"] == []


def test_sentence_comment_by_grader(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["sentence_comments"] = [_comment(rev1, "sentence note")]
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    s, _ = _stored_triple(client, sid)
    assert [c["text"] for c in s["sentence_comments"]] == ["sentence note"]


# Rules that protect other users' data


def _seed_rev1_suggestion_and_comment(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    t = view["sentences"][0]["triples"][0]
    t["grade"] = 8
    t["triple_comments"] = [_comment(rev1, "original text")]
    t["suggestions"] = [{"id": "sug-p", "author": "user_jw", "user_id": rev1["id"], "subject": "a", "predicate": "b",
                         "object": "c", "reason": "", "status": "pending", "votes": {}, "replies": [],
                         "created_at": "2026-10-13T10:00:00Z"}]
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    return sid


def test_grader_cannot_alter_others_items_or_shared_content(client, auth_context):
    rev1, rev2 = auth_context["reviewer1"], auth_context["reviewer2"]
    sid = _seed_rev1_suggestion_and_comment(client, auth_context)
    view = _view(client, sid, rev2["header"])
    s = view["sentences"][0]
    original_text = s["text"]
    s["text"] = "TAMPERED SENTENCE"
    t = s["triples"][0]
    t["triple_comments"][0]["text"] = "edited by someone else"
    t["triple_comments"].append({**_comment(rev1, "forged as rev1")})
    sug = t["suggestions"][0]
    sug.update({"object": "OTHER", "status": "approved", "votes": {"user_jw": "yes", "user_rl": "yes"}})
    t["suggestions"].append({"id": "sug-forged", "author": "user_jw", "user_id": rev1["id"], "subject": "q",
                             "predicate": "q", "object": "q", "status": "approved", "votes": {}, "replies": []})
    s["triples"] = [t]  # drop t00002
    s["triples"].append({"id": "inj", "subject": "i", "predicate": "j", "object": "k", "is_new_suggestion": True,
                         "status": "approved", "suggested_by": "user_jw", "grades_by_user": {}})
    assert _save(client, rev2["header"], view, view["sentences"]).status_code == 200

    stored_s, stored_t = _stored_triple(client, sid)
    assert stored_s["text"] == original_text
    assert [x["id"] for x in stored_s["triples"]] == ["t00001", "t00002"]
    assert [c["text"] for c in stored_t["triple_comments"]] == ["original text"]
    assert len(stored_t["suggestions"]) == 1
    stored_sug = stored_t["suggestions"][0]
    assert stored_sug["object"] == "c" and stored_sug["status"] == "pending"
    assert stored_sug["votes"] == {"user_rl": "yes"}


def test_grader_cannot_vote_on_own_suggestion(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _seed_rev1_suggestion_and_comment(client, auth_context)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["suggestions"][0]["votes"] = {"user_jw": "yes"}
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    _, t = _stored_triple(client, sid)
    assert t["suggestions"][0]["votes"] == {}


def test_grader_save_on_outdated_version_is_rejected(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    stale = _view(client, sid, rev1["header"])
    owner_view = _view(client, sid)
    r = client.post("/api/save", json={"session_id": sid, "source_filename": "s.json",
                                       "uploaded_at": "2026-09-01T12:00:00Z", "sentences": owner_view["sentences"],
                                       "is_publish": True, "version_name": "V1"})
    assert r.status_code == 200
    stale["sentences"][0]["triples"][0]["grade"] = 9
    assert _save(client, rev1["header"], stale, stale["sentences"]).status_code == 409


def test_owner_save_keeps_newer_grades_and_resets_revised_triples(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    owner_stale = _view(client, sid)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["grade"] = 7
    view["sentences"][0]["triples"][1]["grade"] = 6
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200

    # The owner's stale copy has no grades; an approval changes the wording of t00001.
    sentences = copy.deepcopy(owner_stale["sentences"])
    sentences[0]["triples"][0]["object"] = "revised_object"
    assert _save(client, None, owner_stale, sentences).status_code == 200
    s, t1 = _stored_triple(client, sid)
    t2 = s["triples"][1]
    assert t2["grades_by_user"][rev1["id"]]["grade"] == 6.0
    assert t1["grades_by_user"][rev1["id"]]["grade"] == 7.0  # kept until publication

    # Publishing drops grades given for the old wording and flags the triple; t2 keeps its grade.
    owner_view = _view(client, sid)
    r = client.post("/api/save", json={"session_id": sid, "source_filename": "s.json",
                                       "uploaded_at": "2026-09-01T12:00:00Z", "sentences": owner_view["sentences"],
                                       "is_publish": True, "version_name": "V1"})
    assert r.status_code == 200, r.text
    v1 = next(v for v in client.get(f"/api/sessions/{sid}").json()["versions"] if v["name"] == "V1")
    p1, p2 = v1["sentences"][0]["triples"][0], v1["sentences"][0]["triples"][1]
    assert rev1["id"] not in (p1.get("grades_by_user") or {}) and p1.get("is_modified_in_version") is True
    assert p2["grades_by_user"][rev1["id"]]["grade"] == 6.0


def test_saves_keep_fields_the_client_does_not_send(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    before = client.get(f"/api/sessions/{sid}").json()["sentences"][0]["triples"][0]
    assert "polarity" in before and "modality" in before
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["triples"][0]["grade"] = 9
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200
    owner_view = _view(client, sid)
    assert _save(client, None, owner_view, owner_view["sentences"]).status_code == 200
    after = client.get(f"/api/sessions/{sid}").json()["sentences"][0]["triples"][0]
    assert after["polarity"] == before["polarity"] and after["modality"] == before["modality"]


def test_publish_rules(client, auth_context):
    rev1 = auth_context["reviewer1"]
    sid = _new_session(client)
    view = _view(client, sid, rev1["header"])
    view["sentences"][0]["completeness"] = 8
    view["sentences"][1]["completeness"] = 9
    assert _save(client, rev1["header"], view, view["sentences"]).status_code == 200

    def publish(sentences, name):
        return client.post("/api/save", json={"session_id": sid, "source_filename": "s.json",
                                              "uploaded_at": "2026-09-01T12:00:00Z", "sentences": sentences,
                                              "is_publish": True, "version_name": name})

    owner_view = _view(client, sid)
    sentences = copy.deepcopy(owner_view["sentences"])
    sentences[0]["triples"][0]["object"] = "changed"
    assert publish(sentences, "V1").status_code == 200
    v1 = next(v for v in client.get(f"/api/sessions/{sid}").json()["versions"] if v["name"] == "V1")
    assert v1["sentences"][0]["completeness_by_user"] == {}
    assert rev1["id"] in v1["sentences"][1]["completeness_by_user"]
    assert "polarity" in v1["sentences"][0]["triples"][0]
    assert publish(sentences, "V1").status_code == 409
