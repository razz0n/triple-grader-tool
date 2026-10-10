# Empirical Benchmark Evaluation Suite

This directory contains the self-contained empirical evaluation suite, evaluation datasets, and execution scripts for verifying the collaborative ontology curation platform and assessing downstream extraction quality across two domains: Software Engineering Ethics and Biomedical Native-BEL relations.

All scripts in this directory focus strictly on running evaluation experiments and generating raw empirical metrics. Report, figure, and paper compilation scripts are maintained separately outside this evaluation directory.

---

## Directory Structure

```
benchmark_evaluation/
├── common/                     # Shared canonicalization, matching, and bootstrap resampling routines
├── eq1_workflow_correctness/   # EQ1: Lifecycle state transitions, role invariants, schema fidelity
│   ├── fixtures/               # Input session payloads used for transition verification
│   ├── run_eq1_evaluation.py   # EQ1 test runner generating workflow metrics
│   └── test_*.py               # Component and matrix transition test suites
├── eq2_controlled_recovery/    # EQ2: Controlled corruption injection and oracle action replay
│   ├── corrupted/              # Injected synthetic corruption datasets (E1–E10)
│   ├── manifests/              # Formal audit manifests specifying error injections and inverse actions
│   ├── recovered/              # Restored dataset snapshots exported via HTTP REST endpoints
│   ├── reference/              # Reference ground-truth benchmark
│   ├── analyze_recovery.py     # EQ2 metric evaluation runner
│   ├── build_corruptions.py    # Deterministic corruption injector
│   └── replay_oracle_actions.py# HTTP action replay engine executing inverse curation sequences
├── eq3_software_ethics/        # EQ3: Software Engineering Ethics normative relations
│   ├── candidates/             # Uncurated candidate extractions from 4 foundation models
│   ├── curated_b1/             # Human-adjudicated gold standard (B1, 66 relations)
│   ├── frozen_b0/              # Raw pre-curation candidate union (B0, 79 relations)
│   ├── provenance_ledger/      # Transaction ledger tracking triple-level curation edits
│   ├── analyze_transformation.py # Source transformation metrics runner (Eqs. 10–15)
│   └── evaluate_downstream.py  # Downstream performance evaluator and bootstrap CI runner (Eq. 16)
├── eq3_biomedical_bel/         # EQ3: Biomedical Native-BEL biological relations
│   ├── candidates/             # Candidate extractions from 4 foundation models (40 sentences)
│   ├── curated_b1/             # Human-adjudicated gold standard (B1, 69 relations)
│   ├── frozen_b0/              # Raw pre-curation candidate union (B0, 167 relations)
│   ├── analyze_transformation.py # Source transformation metrics runner (Eqs. 10–15)
│   └── evaluate_downstream.py  # Downstream performance evaluator and bootstrap CI runner (Eq. 16)
├── results/                    # Standardized empirical CSV result files
├── requirements.txt            # Minimal Python dependencies for executing the benchmark
├── run_all_evaluations.py      # Master runner executing all evaluation suites
└── README.md                   # This specification and execution guide
```

---

## Evaluation Scenarios

### EQ1: Lifecycle Workflow Correctness
- **Objective:** Verify collaborative state transitions, role-based permissions, and data fidelity across 18 lifecycle transitions (T01–T18) executed against HTTP REST endpoints.
- **Key Metrics:** Valid Transition Accuracy (VTA), Invalid-Action Rejection Rate (IARR), and Deep Field Fidelity (FF).

### EQ2: Controlled Corruption Recovery
- **Objective:** Evaluate the system's ability to systematically reverse controlled structural and semantic faults (E1–E10) across varying densities via public HTTP curation actions.
- **Key Metrics:** Corruption Repair Recall, Untouched Preservation Rate, Set Precision/Recall/F1, and Exact Restoration Rate.

### EQ3: Source Transformation and Downstream Impact
Evaluated across two distinct corpora:
1. **Software Engineering Ethics:** 15 normative ethics sentences evaluated across 4 large language models (ChatGPT-5.6-High, Gemini-3.1-Pro, GPT-OSS 120B, and Qwen 3.8 27B).
2. **Biomedical Native-BEL:** 40 biomedical causal sentences from biological statement corpora evaluated across the same 4 models.
- **Key Metrics:**
  - *Transformation Dynamics:* Retention rate, modification rate, removal rate, exact/normalized precision and recall against $B_1$, curation intensity.
  - *Downstream Impact:* Micro Precision, Recall, and F1 evaluated against raw uncurated union ($B_0$) versus curated gold ($B_1$), score shift ($\Delta F_1$), 2,000-sample bootstrap 95% confidence intervals, and rank correlation (Kendall's $\tau$, Spearman's $\rho$).

---

## Installation & Setup

Ensure Python 3.10 or higher is installed with active database services configured in `backend/config.py`.

```bash
# Install required dependencies
pip install -r benchmark_evaluation/requirements.txt
```

---

## Running the Benchmark

### 1. Run Complete Benchmark Suite
To execute all evaluation suites sequentially and produce all CSV outputs:

```bash
python benchmark_evaluation/run_all_evaluations.py
```

### 2. Run Individual Evaluation Suites

#### EQ1 Lifecycle Workflow Verification:
```bash
python benchmark_evaluation/eq1_workflow_correctness/run_eq1_evaluation.py
```

#### EQ2 Controlled Recovery Analysis:
```bash
python benchmark_evaluation/eq2_controlled_recovery/analyze_recovery.py
```

#### EQ3 Software Ethics Evaluation:
```bash
# Transformation dynamics
python benchmark_evaluation/eq3_software_ethics/analyze_transformation.py

# Downstream model evaluation and bootstrap CIs
python benchmark_evaluation/eq3_software_ethics/evaluate_downstream.py
```

#### EQ3 Biomedical Native-BEL Evaluation:
```bash
# Transformation dynamics
python benchmark_evaluation/eq3_biomedical_bel/analyze_transformation.py

# Downstream model evaluation and bootstrap CIs
python benchmark_evaluation/eq3_biomedical_bel/evaluate_downstream.py
```

---

## Output Metrics & Artifacts

All evaluation scripts record results directly into `benchmark_evaluation/results/`:

| Output File | Evaluation Scope | Key Columns |
|---|---|---|
| `eq1_workflow_matrix.csv` | EQ1 Lifecycle | `test_id`, `category`, `expected_outcome`, `actual_outcome`, `field_fidelity`, `latency_ms`, `passed` |
| `eq1_summary.csv` | EQ1 Lifecycle | `Metric`, `Observed_Value`, `Benchmark_Target`, `Status` |
| `eq2_recovery_matrix.csv` | EQ2 Recovery | `error_type`, `corruption_name`, `density`, `seed`, `repair_recall`, `preservation_rate`, `set_f1`, `exact_match` |
| `eq2_summary.csv` | EQ2 Recovery | `error_type`, `mean_precision`, `mean_recall`, `mean_f1`, `mean_repair_recall`, `mean_preservation`, `exact_restoration_rate` |
| `eq3_transformation.csv` | EQ3 Software Ethics | `source_system`, `retention_rate`, `modification_rate`, `removal_rate`, `precision_exact`, `recall_exact`, `f1_exact`, `curation_intensity` |
| `eq3_downstream.csv` | EQ3 Software Ethics | `system_name`, `b0_micro_f1`, `b1_micro_f1`, `delta_f1`, `ci_lower`, `ci_upper`, `rank_b0`, `rank_b1` |
| `eq3_bio_transformation.csv` | EQ3 Biomedical BEL | `source_system`, `retention_rate`, `modification_rate`, `removal_rate`, `precision_exact`, `recall_exact`, `curation_intensity` |
| `eq3_bio_downstream.csv` | EQ3 Biomedical BEL | `system_name`, `b0_micro_f1`, `b1_micro_f1`, `delta_f1`, `ci_lower`, `ci_upper`, `rank_b0`, `rank_b1` |
