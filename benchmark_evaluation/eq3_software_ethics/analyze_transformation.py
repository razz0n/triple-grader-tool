"""
analyze_transformation.py — Source transformation analysis engine for candidate curation evaluation.

Computes empirical transformation statistics quantifying how raw candidate triples evolve during human curation:
- Unchanged Retention Rate: N_accepted_unchanged / |Ci|
- Modification Rate: N_modified / |Ci|
- Removal Rate: N_removed / |Ci|
- Candidate Precision against Gold Benchmark: |Ci ∩ B1| / |Ci|
- Candidate Recall against Gold Benchmark: |Ci ∩ B1| / |B1|
- Curation Edit Intensity: (N_modified + N_removed + N_added_due_to_gaps) / |Ci|

Evaluates metrics under both Exact Matching and Normalized Matching,
outputting results to experiments/results/eq3_transformation.csv.
"""

import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
EQ3_DIR = Path(__file__).resolve().parent
RESULTS_DIR = ROOT_DIR / "benchmark_evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def analyze_transformations():
    ledger_file = EQ3_DIR / "provenance_ledger" / "transformation_ledger.json"
    assert ledger_file.exists(), f"Ledger file not found: {ledger_file}"

    with open(ledger_file, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    b1_file = EQ3_DIR / "curated_b1" / "b1_curated_gold.json"
    with open(b1_file, "r", encoding="utf-8") as f:
        b1_data = json.load(f)
    b1_gold_total = b1_data.get("total_triples", 66)
    sources = ledger.get("sources", {})

    print(f"Computing Source Transformation Metrics (Eqs. 10–15) against B1 ({b1_gold_total} triples)...")
    results = []

    for src_name, src_data in sources.items():
        total_ci = src_data.get("total_candidates", 0)
        outcomes = src_data.get("outcomes", {})

        n_unchanged = outcomes.get("accepted_unchanged", 0)
        n_modified = outcomes.get("accepted_modified", 0)
        n_removed = outcomes.get("removed_rejected", 0)
        n_duplicate = outcomes.get("merged_duplicate", 0)
        n_added_gaps = src_data.get("added_due_to_gaps", 0)
        covered_gold = src_data.get("covered_gold_triples", 0)

        # Equations 10–15
        retention = n_unchanged / total_ci if total_ci > 0 else 0.0
        mod_rate = n_modified / total_ci if total_ci > 0 else 0.0
        removal_rate = n_removed / total_ci if total_ci > 0 else 0.0

        # Precision & Recall under exact matching
        precision_exact = n_unchanged / total_ci if total_ci > 0 else 0.0
        recall_exact = n_unchanged / b1_gold_total if b1_gold_total > 0 else 0.0
        f1_exact = (2 * precision_exact * recall_exact) / (precision_exact + recall_exact) if (precision_exact + recall_exact) > 0 else 0.0

        # Precision & Recall under normalized matching (exact + modified)
        precision_norm = (n_unchanged + n_modified) / total_ci if total_ci > 0 else 0.0
        recall_norm = covered_gold / b1_gold_total if b1_gold_total > 0 else 0.0
        f1_norm = (2 * precision_norm * recall_norm) / (precision_norm + recall_norm) if (precision_norm + recall_norm) > 0 else 0.0

        # Curation Intensity (Eq. 15)
        curation_intensity = (n_modified + n_removed + n_added_gaps) / total_ci if total_ci > 0 else 0.0

        row = {
            "source_system": src_name,
            "total_candidates": total_ci,
            "accepted_unchanged": n_unchanged,
            "accepted_modified": n_modified,
            "removed_rejected": n_removed,
            "merged_duplicate": n_duplicate,
            "added_due_to_gaps": n_added_gaps,
            "retention_rate": round(retention, 4),
            "modification_rate": round(mod_rate, 4),
            "removal_rate": round(removal_rate, 4),
            "precision_exact": round(precision_exact, 4),
            "recall_exact": round(recall_exact, 4),
            "f1_exact": round(f1_exact, 4),
            "precision_normalized": round(precision_norm, 4),
            "recall_normalized": round(recall_norm, 4),
            "f1_normalized": round(f1_norm, 4),
            "curation_intensity": round(curation_intensity, 4),
        }
        results.append(row)

        print(f"  [{src_name:30s}] Retention={retention*100:5.1f}% | ModRate={mod_rate*100:5.1f}% | "
              f"Removal={removal_rate*100:5.1f}% | P(exact)={precision_exact*100:5.1f}% | "
              f"R(exact)={recall_exact*100:5.1f}% | Intensity={curation_intensity:.2f}")

    # Write CSV output
    out_csv = RESULTS_DIR / "eq3_transformation.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\n[Saved] Source transformation metrics written to: {out_csv}")
    return results


if __name__ == "__main__":
    analyze_transformations()
