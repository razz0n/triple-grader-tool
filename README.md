# TripleGrader: A Web-Based Platform Supporting Collaborative Triple Annotation with Quality Grading and Inter-Rater Agreement Assessment

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB.svg)](https://react.dev/)
[![Conference](https://img.shields.io/badge/IEEE-ICSC%202027-informational.svg)](https://www.ieee.org/)

TripleGrader is a web platform for grading subject-predicate-object (SPO) triples that have already been extracted from text. Graders score each triple on a 0 to 10 ordinal scale and discuss it in threaded comments. The session owner approves revisions and publishes versions, and the platform computes quadratic-weighted agreement and exports the final benchmark.

This repository contains the platform and the evaluation package for the paper submitted to IEEE ICSC 2027.

![TripleGrader workspace](docs/images/triplegrader_workspace_preview.png)

*The source sentence and its sentence-level ratings are at the top. The candidate triples follow, each with 0 to 10 grade buttons, discussion, and revision proposals.*

---

## Features

1. **Triple grading.** Graders score each triple from 0 to 10. Each grade is stored under the grader's user ID, and a save can change only the caller's own entries. The session owner does not grade.
2. **Sentence-level ratings.** Graders also rate each sentence from 0 to 10 for *completeness* (how fully its triples capture the meaning of the sentence) and *external relation* (whether the predicates match the schema properties and domain guidelines).
3. **Blind first round.** Until a grader has rated an item, the server withholds the other graders' scores and averages for it.
4. **Discussion and suggestions.** Users comment on sentences and triples in threaded discussions. Graders propose revised or new triples and vote on other graders' proposals; a vote on one's own proposal is rejected. Graders can also request the removal of a triple. The owner approves a proposal, which replaces the triple's wording, and can undo the approval.
5. **Versions and re-grading.** Every grade records the wording of the triple it was given for. When the owner publishes a named version, grades whose triple wording has changed are dropped and the triple is flagged with a description of the change, so graders score the new wording. Proposals the owner has not approved are cleared, and removal requests the owner has not decided stay open. Earlier versions are read-only.
6. **Agreement.** Quadratic-weighted Cohen's kappa when two graders rated the items, and a quadratic-weighted Fleiss-type kappa when three or more did. Kappa is reported as not available when all grades are identical or fewer than two items are co-rated.
7. **Export.** Sessions export to CSV, Excel, Word, PDF, and JSON. A separate gold export (JSON or CSV, owner only, through the REST API) contains the triples of the active version in their approved wording, except those awaiting a removal decision, plus approved additions.

Sessions are created by uploading a CSV, Excel, or JSON file (spreadsheets: subject, predicate, and object in the first three columns, grouped under their source sentences), or by typing sentences and triples in the manual builder.

---

## Building a benchmark

![Annotation and benchmark creation pipeline](docs/images/fig1_pipeline.png)

The paper recommends three stages:

1. **Independent grading.** Graders score the candidates in the blind first round.
2. **Discussion and revision.** The owner reviews the per-triple scores and means to find triples with low scores or a wide spread. These are discussed in the comment threads, where graders propose revisions and vote on them before the owner approves one. Publishing the next version drops the grades that no longer match the revised triples, so graders score the new wording.
3. **Finalization and export.** Graders request the removal of rejected triples, and each request the owner approves deletes its triple. The owner then publishes a final named version and exports the gold benchmark.

As a starting point, the paper suggests accepting triples with a mean of at least 8.0 and a spread of at most 2 points, removing triples that every grader scores below 5, and discussing the rest. The platform reports the scores and does not filter triples; acceptance is a human decision, and kappa is not used to decide membership.

---

## Architecture

* **Frontend:** a React single-page application built with Vite.
* **Backend:** a FastAPI service in Python with REST routes for authentication, file parsing, sessions, agreement, and reports. Passwords are hashed with PBKDF2-HMAC-SHA256 and a per-user salt. After login, clients receive a random bearer token that expires after six hours of inactivity, and the acting user is read from the token alone. A WebSocket channel notifies open clients when a session is saved or a version changes; other updates, such as new comments, arrive by polling every 15 seconds.
* **Storage:** each session is one JSON document holding its sentences, triples, ratings, comment threads, suggestions, and versions. By default, sessions are kept as JSON files under `backend/storage/` and users and tokens in SQLite. With `STORAGE_BACKEND=database` and a `DATABASE_URL`, everything is stored in PostgreSQL through SQLAlchemy (see `backend/.env.example`).

---

## Quick start

Requirements: Python 3.10 or later (3.12 was tested) and Node.js 18 or later.

```bash
python -m venv .venv
.venv\Scripts\activate               # Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

On Windows, `.\start.ps1` from the repository root then starts both parts:

* Backend: `http://localhost:8001` (API documentation at `/docs`)
* Frontend: `http://localhost:5173`

To start them by hand:

```bash
cd backend
uvicorn main:app --reload --port 8001
```

```bash
cd frontend
npm run dev
```

Without a `backend/.env` file, the backend uses local JSON and SQLite storage, which is enough for a local installation.

---

## Reproducing the evaluation

The evaluation package is in [`benchmark_evaluation/`](benchmark_evaluation/README.md). From the repository root:

```bash
pip install -r benchmark_evaluation/requirements.txt
python benchmark_evaluation/run_all_evaluations.py            # EQ1, EQ2 analysis, EQ3
python benchmark_evaluation/run_all_evaluations.py --replay   # also re-runs the EQ2 oracle replay
```

The suites run the backend in-process against local storage and stop if a hosted database is configured.

| Evaluation | What it checks | Result in the paper |
|---|---|---|
| **EQ1** Workflow correctness | 18 workflow scenarios (14 permitted, 4 rejected operations) and 54 further tests of saves, access control, blind review, versions, and the agreement computation | All 72 tests pass |
| **EQ2** Controlled error recovery | 10 injected error types at 10% density on a 316-row software ethics reference, repaired through the REST API by an oracle | 100% repair recall and preservation in every condition |
| **EQ3** Curation of LLM candidates | Four models' triples curated into an existing benchmark on two corpora (software ethics, 66 triples; biomedical BEL, 69 triples) | 10% to 32% of candidates kept unchanged, 53% to 71% corrected, 11 to 29 triples added per model (Table III) |

`pytest` collects 92 items in `benchmark_evaluation/eq1_workflow_correctness`, because 20 of them only re-run the 18 scenarios from other files. The data sources and their terms are listed in [`benchmark_evaluation/DATA_SOURCES.md`](benchmark_evaluation/DATA_SOURCES.md).

---

