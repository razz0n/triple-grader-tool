# Shared code (`benchmark_evaluation/common`)

Code used by more than one evaluation.

- `schemas/`: JSON Schemas for a triple (`triple_schema.json`), an EQ2 corruption manifest (`manifest_schema.json`), and a session export or version snapshot (`session_schema.json`).
- `canonicalize.py`: exact and normalized forms of triple text (case folding, whitespace, entity suffixes).
- `adjudicated_gold.py`: the backend's rule for which triples enter the exported gold set.
- `matching.py`: set precision, recall and F1 of a triple set against a reference, under exact and normalized matching.
- `local_backend.py`: makes the suites use an isolated local store instead of a hosted database.
- `eq3_curation.py`: EQ3 inputs and the curation counts of Table III.
