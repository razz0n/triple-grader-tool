# TripleGrader: A Web-Based Platform Supporting Collaborative Triple Annotation with Quality Grading and Inter-Rater Agreement Assessment

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB.svg)](https://react.dev/)
[![Conference](https://img.shields.io/badge/IEEE-ICSC%202027-informational.svg)](https://www.ieee.org/)

TripleGrader is a web platform for grading subject-predicate-object (SPO) triples that have already been extracted from text. Graders score each triple on a 0 to 10 scale and discuss it, the session owner approves revisions and publishes versions, and the platform computes quadratic-weighted agreement and exports the final benchmark.

![TripleGrader workspace](docs/images/triplegrader_workspace_preview.png)

---

## Features

- **Triple grading** on a 0 to 10 scale, stored per grader.
- **Sentence-level ratings** for completeness and external relation.
- **Blind first round:** peer scores stay hidden until a grader has rated the item.
- **Discussion and suggestions:** threaded comments, proposed revisions and new triples, votes, and removal requests. The owner approves or rejects them.
- **Versions and re-grading:** publishing a version drops grades of triples whose wording changed, so they are graded again. Earlier versions are read-only.
- **Agreement:** quadratic-weighted Cohen's kappa for two graders, quadratic-weighted Fleiss-type kappa for three or more.
- **Export:** CSV, Excel, Word, PDF, and JSON, plus a gold benchmark export.

Sessions are created by uploading a CSV, Excel, or JSON file, or with the manual builder.

---

## Building a benchmark

![Annotation and benchmark creation pipeline](docs/images/fig1_pipeline.png)

1. **Extraction:** candidate triples (S, P, O) are extracted from the raw text with an extraction pipeline or an LLM, outside the platform.
2. **Upload:** the candidates are uploaded to TripleGrader as a session.
3. **Grading:** several graders score each triple from 0 to 10, blind to each other's scores.
   - **3.1 Agreement check:** quadratic-weighted kappa, computed from the grades, shows how consistently the graders grade. It does not decide which triples are kept.
4. **Discussion and revision:** triples with low scores or a wide spread are discussed and revised, rejected triples are removed, and revised triples are graded again in the next version.
5. **Export:** the owner publishes the final version and exports the gold benchmark.

---

## Architecture

- **Frontend:** React with Vite.
- **Backend:** FastAPI (Python), token-based login, WebSocket notifications.
- **Storage:** JSON files and SQLite by default, or PostgreSQL with `STORAGE_BACKEND=database` and `DATABASE_URL` (see `backend/.env.example`).

---

## Quick start

Requirements: Python 3.10+ and Node.js 18+.

```bash
python -m venv .venv
.venv\Scripts\activate               # Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

On Windows, run `.\start.ps1` from the repository root. Or start each part:

```bash
cd backend
uvicorn main:app --reload --port 8001
```

```bash
cd frontend
npm run dev
```

- Backend: `http://localhost:8001` (API docs at `/docs`)
- Frontend: `http://localhost:5173`

---

## Reproducing the evaluation

See [`benchmark_evaluation/`](benchmark_evaluation/README.md). From the repository root:

```bash
pip install -r benchmark_evaluation/requirements.txt
python benchmark_evaluation/run_all_evaluations.py
```

| Evaluation | Result |
|---|---|
| **EQ1** Workflow correctness | All 72 tests pass, including 18 workflow scenarios |
| **EQ2** Controlled error recovery | 100% repair recall and preservation for 10 error types |
| **EQ3** Curation of LLM candidates | 10% to 32% of candidates kept unchanged, 53% to 71% corrected, 11 to 29 triples added per model |

Data sources and terms: [`benchmark_evaluation/DATA_SOURCES.md`](benchmark_evaluation/DATA_SOURCES.md).
