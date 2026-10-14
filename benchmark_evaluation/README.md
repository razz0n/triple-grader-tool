# Evaluation Suite

Scripts, frozen inputs, and results for the three evaluations reported in the paper. Every reported table can be regenerated with one command:

```bash
pip install -r benchmark_evaluation/requirements.txt
python benchmark_evaluation/run_all_evaluations.py            # EQ1, EQ2 analysis, EQ3
python benchmark_evaluation/run_all_evaluations.py --replay   # also re-run the EQ2 oracle replay
```

The suites drive the FastAPI backend in-process. `common/local_backend.py` forces a local JSON/SQLite store before the backend is imported and stops the run if a hosted database is configured, so the evaluation never touches a production database.

## Layout

```
benchmark_evaluation/
├── common/                       shared code
│   ├── local_backend.py          isolation of the backend store
│   ├── eq3_metrics.py            EQ3 definitions (both corpora use the same code)
│   └── canonicalize.py, matching.py, bootstrap.py
├── eq1_workflow_correctness/     T01-T18 workflow matrix, agreement-metric tests, security regression tests
├── eq2_controlled_recovery/      reference, corruption manifests, corrupted/recovered files, replay and analysis
├── eq3_software_ethics/          15 sentences, 4 candidate sessions, B0, B1, prompt and 21 demonstrations
├── eq3_biomedical_bel/           40 source-text units, 4 candidate sessions, B0, B1, prompt and 30 demonstrations
├── freeze_eq3.py                 verifies (or once creates) the EQ3 frozen-input manifests
├── run_eq3.py                    regenerates all EQ3 tables
├── run_all_evaluations.py        runs everything
└── results/                      CSV/JSON/LaTeX outputs
```

## EQ1: workflow correctness
`run_eq1_evaluation.py` runs the eighteen scenarios T01-T18 (14 valid transitions, 4 rejection scenarios) and writes `results/eq1_workflow_matrix.csv` and `results/eq1_summary.csv`. `pytest benchmark_evaluation/eq1_workflow_correctness` also runs `test_kappa_metrics.py` (two-rater values equal scikit-learn's quadratic-weighted Cohen's kappa; browser and server implementations agree) and `test_security_regressions.py` (token-derived identity, owner-only approval and export, no session overwrite, no grades written for other users, blind first round).

## EQ2: controlled recovery
The reference has 316 triple rows over 38 sentences (309 distinct SPO tuples). `build_corruptions.py` injects ten error types at 10% density with seed 42 (32 rows per condition). `replay_oracle_actions.py` issues the manifest-derived inverse actions through the REST API with the reviewers' and owner's tokens. `analyze_recovery.py` reports repair recall, untouched SPO preservation (denominator 277 for E1-E5 and E8-E10, 309 for E6-E7), SPO-set restoration, and row-level restoration (multiset of sentence, S, P, O, polarity, modality, scope, note).

## EQ3: candidates versus human-curated references
- **Frozen inputs.** `FROZEN_MANIFEST.json` in each corpus folder records the SHA-256 of the four candidate files, B0, B1, the prompt, and the demonstrations. `freeze_eq3.py` refuses to continue if any of them changed.
- **B0** is the union of the four models' initial candidates after normalized de-duplication: 128 triples for software ethics and 167 for biomedical, stored in `frozen_b0/b0_raw_candidates.json` in each corpus folder.
- **B1** is the final version shared by all four candidate sessions and equals `curated_b1/b1_curated_gold.json` (66 and 69 triples).
- **Matching.** Within a sentence, each slot is trimmed and lower-cased, and underscores, hyphens, and double quotes are removed. Exact = all three slots equal; near miss = two of three equal; unaligned otherwise. No reference triple is consumed, so the results do not depend on order.
- **Scores.** Micro precision, recall, and F1 against B0, against the union of the other three models (leave-one-out pool), and against B1, with a paired sentence-level bootstrap (2,000 resamples, seed 42) for F1(B1) - F1(B0). Precision against B0 is 100% by construction.

The `analyze_transformation.py` and `evaluate_downstream.py` files in each corpus folder now call `run_eq3.py`. The earlier greedy, order-dependent matcher was removed.

## Outputs (`results/`)
| File | Content |
|---|---|
| `eq1_workflow_matrix.csv`, `eq1_summary.csv` | EQ1 scenario results, VTA and IARR |
| `eq2_recovery_matrix.csv`, `eq2_summary.csv` | EQ2 per-condition recovery metrics |
| `eq3_transformation.csv`, `eq3_bio_transformation.csv` | EQ3 exact / near-miss / unaligned counts per source |
| `eq3_downstream.csv`, `eq3_bio_downstream.csv` | EQ3 scores against B0, the leave-one-out pool, and B1 |
| `eq3_summary.json`, `eq3_tables.tex` | all EQ3 numbers with the frozen manifests, and LaTeX table rows |
