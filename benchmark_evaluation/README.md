# Evaluation suite

Scripts, frozen inputs and results for the three evaluations in the paper. Every table can be regenerated with one command, from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r benchmark_evaluation/requirements.txt
python benchmark_evaluation/run_all_evaluations.py            # EQ1, EQ2 analysis, EQ3
python benchmark_evaluation/run_all_evaluations.py --replay   # also re-run the EQ2 oracle replay
```

On Windows, clone into a short folder such as `C:\tg` or run `git config --global core.longpaths true` first, because some file paths are longer than the default 260-character limit.

Tested with Python 3.12 on Windows 11. A full run takes about a minute on a laptop and needs no GPU, network access or database. Node.js (version 20 was used) is needed only for one test that runs the frontend's kappa code; that test is skipped when Node.js is not installed. The results are written to `results/`.

The model outputs are frozen and are not regenerated: ChatGPT and Gemini were used through their web interfaces, and the two Groq models did not return identical output at temperature 0. `eq3_*/groq_rerun.py` repeats the Groq requests for the repeatability check and needs your own `GROQ_API_KEY`. The sources of the data and their terms are listed in [DATA_SOURCES.md](DATA_SOURCES.md).

The suites drive the FastAPI backend in-process. `common/local_backend.py` forces a local JSON/SQLite store before the backend is imported and stops the run if a hosted database is configured, so the evaluation never touches a production database.

## Layout

```
benchmark_evaluation/
├── common/                       shared code
│   ├── local_backend.py          isolation of the backend store
│   ├── eq3_curation.py           EQ3 inputs and curation counts (both corpora use the same code)
│   └── canonicalize.py, matching.py
├── eq1_workflow_correctness/     T01-T18 workflow matrix, agreement-metric tests, security regression tests
├── eq2_controlled_recovery/      reference, corruption manifests, corrupted/recovered files, replay and analysis
├── eq3_software_ethics/          15 sentences, 4 candidate files, 4 curated sessions, B1, prompt and 21 demonstrations
├── eq3_biomedical_bel/           40 source-text units, 4 candidate files, 4 curated sessions, B1, prompt and 30 demonstrations
├── freeze_eq3.py                 verifies (or once creates) the EQ3 frozen-input manifests
├── run_eq3.py                    regenerates the EQ3 table (Table III)
├── run_all_evaluations.py        runs everything
└── results/                      CSV/JSON/LaTeX outputs
```

## EQ1: workflow correctness
`run_eq1_evaluation.py` runs the eighteen scenarios T01-T18 (14 valid transitions, 4 rejection scenarios) and writes `results/eq1_workflow_matrix.csv` and `results/eq1_summary.csv`. `pytest benchmark_evaluation/eq1_workflow_correctness` also runs `test_kappa_metrics.py` (two-rater values equal scikit-learn's quadratic-weighted Cohen's kappa; browser and server implementations agree) and `test_security_regressions.py` (token-derived identity, owner-only approval and export, no session overwrite, no grades written for other users, blind first round).

## EQ2: controlled recovery
The reference has 316 triple rows over 38 sentences (309 distinct SPO tuples). `build_corruptions.py` injects ten error types at 10% density with seed 42 (32 rows per condition). `replay_oracle_actions.py` issues the manifest-derived inverse actions through the REST API with the reviewers' and owner's tokens. `analyze_recovery.py` reports repair recall, untouched SPO preservation (denominator 277 for E1-E5 and E8-E10, 309 for E6-E7), SPO-set restoration, and row-level restoration (multiset of sentence, S, P, O, polarity, modality, scope, note).

## EQ3: curating model candidates into an existing benchmark
Both corpora had a gold benchmark, B1 (`curated_b1/b1_curated_gold.json`, 66 and 69 triples), before the candidates were extracted. Each model's candidates were uploaded to TripleGrader as a separate session. The first author graded and curated the biomedical sessions and the second author the software ethics sessions: low-graded candidates were discussed, then corrected with an approved revision, removed with an approved removal request, or kept, and the reference triples a model had missed were added. The owner published the result, which equals B1 in every session.

- **Inputs.** `candidates/` holds each model's output; only the first version of each file (the raw model output that was uploaded) is read. Later versions in these files come from an earlier automatic alignment that the paper no longer reports. `curation_sessions/` holds the eight curated sessions exported from TripleGrader, with every grade, suggestion, approval, and published version.
- **Frozen inputs.** `FROZEN_MANIFEST.json` in each corpus folder records the SHA-256 of the candidate files, B1, the prompt, the demonstrations, and the curated sessions (line endings are read as LF, so Windows and Linux checkouts hash alike). `freeze_eq3.py` stops if any of them changed.
- **Counts.** `run_eq3.py` matches every original candidate to the published version of its session by identifier (`<sentence number>_<position>`). A candidate is *exact* if it is still there with the same subject, predicate and object, *modified* if it is still there but at least one slot changed, and *deleted* if it is no longer there. *Newly suggested* triples are those added during curation. The script checks that each published version equals B1 and that exact + modified + newly suggested = |B1|.
- **Reruns.** `groq_rerun.py` and `reproducibility_rerun/` record a second run of the two Groq models, used for the repeatability figures (34% to 97% of candidates reproduced).

## Outputs (`results/`)
| File | Content |
|---|---|
| `eq1_workflow_matrix.csv`, `eq1_summary.csv` | EQ1 scenario results, VTA and IARR |
| `eq2_recovery_matrix.csv`, `eq2_summary.csv` | EQ2 per-condition recovery metrics |
| `eq3_curation.csv` | EQ3 exact, modified, deleted and newly suggested counts per corpus and model |
| `eq3_summary.json`, `eq3_tables.tex` | the same counts with the frozen-input manifests, and the LaTeX rows of Table III |
