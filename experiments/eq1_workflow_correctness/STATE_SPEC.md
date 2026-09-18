# Triple Grader Formal State-Transition Specification (EQ1)

## 1. Lifecycle and State Model

The Triple Grader platform formalizes the progression of candidate triples into frozen benchmark artifacts through the following deterministic lifecycle:

```
                  +-------------------------+
                  |     Candidate Triple    |
                  +-------------------------+
                               |
              +----------------+----------------+
              |                                 |
              v                                 v
      +---------------+                 +---------------+
      | Graded/Scored |                 | Suggested Rev |
      +---------------+                 +---------------+
              |                                 |
              |                                 v
              |                         +---------------+
              |                         | Voted/Discuss |
              |                         +---------------+
              |                                 |
              v                                 v
    +-------------------+             +-------------------+
    | Marked for Removal|             | Approved / Super  |
    +-------------------+             +-------------------+
              |                                 |
              +----------------+----------------+
                               |
                               v
                  +-------------------------+
                  |   Frozen Adjudicated    |
                  |     Benchmark Gold      |
                  +-------------------------+
```

---

## 2. Participant Roles and Authorization Matrix

| Action | Session Owner | Collaborator / Reviewer |
| :--- | :--- | :--- |
| Create / Register Session | Allowed | Allowed |
| Save Triple Quality Grade | Allowed | Allowed |
| Save Sentence Completeness/Relation | Allowed | Allowed |
| Submit Triple Revision Suggestion | Allowed | Allowed |
| Vote on Suggestion | Allowed | Allowed (Self-Vote strictly Rejected) |
| Approve / Unapprove Revision | Allowed (Exclusive) | Rejected (HTTP 403) |
| Mark Triple for Removal | Allowed | Allowed |
| Publish Version Snapshot | Allowed | Rejected (HTTP 403) |
| Delete Version Snapshot | Allowed | Rejected (HTTP 403) |
| Export Adjudicated Benchmark | Allowed | Allowed |

---

## 3. Test Matrix Specification (T01 – T18)

| ID | Scenario | Pre-conditions | Invocation / API Call | Expected Post-condition | Error Code if Unauthorized |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **T01** | Import Valid File | Normalized JSON / CSV with sentences and triples | `POST /api/sessions` or `POST /api/upload` | Stable sentence IDs, triple IDs, and source text preserved verbatim | 422 if malformed |
| **T02** | Owner Saves Grade | Active session with owner session token | `POST /api/save` (grade payload) | Grade recorded under owner ID; survives session reload | — |
| **T03** | Reviewer Saves Grade | Active session with reviewer session token | `POST /api/save` (reviewer grade) | Only reviewer entry mutates; shared text is unmodified | — |
| **T04** | Clear Grade | Triple graded by reviewer | `POST /api/save` (null grade) | Reviewer's score is removed; other reviewers' scores persist | — |
| **T05** | Sentence Metrics | Active session | `POST /api/save` (completeness & relation) | Per-user sentence completeness/relation persist independently | — |
| **T06** | Create Suggestion | Active triple in session | `POST /api/sessions/{id}/suggestions` | Pending suggestion stored with author, triple link, and timestamp | 404 if invalid ID |
| **T07** | Suggestion Voting | Suggestion in pending status | `POST /api/sessions/{id}/vote` | Vote recorded; self-voting by author is rejected | 400 Bad Request on self-vote |
| **T08** | Edit/Delete Suggestion | Pending suggestion | `POST /api/suggestions/edit` or `DELETE` | Allowed for author; rejected for non-author | 403 Forbidden |
| **T09** | Owner Approves | Pending suggestion | `POST /api/sessions/{id}/approve` | Suggestion approved, original superseded, corrected active | 403 if non-owner |
| **T10** | Owner Unapproves | Approved suggestion | `POST /api/suggestions/unapprove` | State returns to pending without data loss | 403 if non-owner |
| **T11** | Mark for Removal | Active triple | `POST /api/triples/mark-removal` | Triple marked for removal; excluded from gold export | — |
| **T12** | Missing Triple Addition | Sentence in session | `POST /api/save` (new suggestion) | Pending new triple excluded from gold until approved | — |
| **T13** | Comments & Replies | Active triple or comment | `POST /api/triples/comments/add` | Thread structure, author identity, and timestamps survive save | — |
| **T14** | Publish Version | Draft with modifications | `POST /api/save` (`is_publish=True`) | Immutable snapshot created; draft updates do not mutate snapshot | — |
| **T15** | Delete Version | Published version exists | `DELETE /api/session/{id}/version/{v}` | Only owner can delete; last version protected | 400 / 403 |
| **T16** | Multi-Format Export | Adjudicated session | `GET .../export/json` & `GET .../export/csv` | Identical set membership across JSON and CSV exports | — |
| **T17** | Concurrent Save Simulation | Two clients editing concurrently | `POST /api/save` with concurrent payloads | Merging policy preserves non-conflicting reviewer data | — |
| **T18** | Malformed Identifiers | Request with malformed IDs | `POST /api/sessions/{id}/suggestions` | Request cleanly rejected with structured 400/404, no mutation | 400 / 404 |
