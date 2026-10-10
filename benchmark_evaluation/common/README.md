# Shared Evaluation Utilities (`benchmark_evaluation/common`)

This directory provides centralized mathematical algorithms, token normalizations, schemas, and statistical resampling tools used across all evaluation experiments.

## Directory Structure
- `schemas/`: Canonical JSON Schemas defining data integrity constraints:
  - `triple_schema.json`: Schema for semantic (subject, predicate, object) triples.
  - `manifest_schema.json`: Schema for EQ2 synthetic corruption manifests.
  - `session_schema.json`: Schema for session exports and version snapshots.
- `canonicalize.py`: Exact character and normalized token transformations (case-folding, whitespace normalization, entity suffix handling).
- `adjudicated_gold.py`: Centralized membership rules for the authoritative adjudicated gold set (conforming to Section 2.1).
- `matching.py`: Strict triple set comparison computing Precision, Recall, and F1 under Exact and Normalized matching.
- `bootstrap.py`: Sentence-cluster bootstrap resampling engine (2,000 resamples by default) computing 95% confidence intervals while accounting for intra-sentence correlation structures.
