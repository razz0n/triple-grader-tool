"""
analyze_recovery.py — Recovery metrics analysis and evaluation reporting.

Evaluates recovered triple sets against reference ground truth by computing:
  - Set Precision, Recall, and F1 (P_set, R_set, F1_set)
  - Corruption Repair Recall (proportion of injected errors successfully restored)
  - Untouched Preservation Rate (proportion of uncorrupted triples left unaltered)
  - SPO-Set Restoration (R == G: equality of the sets of distinct (subject, predicate, object) tuples)
  - Row-Level Restoration (equality of the multisets of (sentence, S, P, O, polarity, modality,
    scope, note) rows; this also detects duplicate rows and lost annotation attributes)

The reference and the recovered exports are different file formats, so no byte-level or hash
comparison is made.

Outputs run-level records to CSV and produces summary tables.
"""

import csv
import json
from collections import Counter
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from benchmark_evaluation.common.canonicalize import canonicalize_triple, exact_triple_tuple

RESULTS_DIR = ROOT_DIR / "benchmark_evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def extract_triple_set(dataset: Dict[str, Any], mode: str = "exact") -> Set[Tuple[str, str, str]]:
    """Extracts unique (subject, predicate, object) tuples from a session or export payload."""
    tuples = set()
    triples_list = []

    if "triples" in dataset and isinstance(dataset["triples"], list):
        triples_list = dataset["triples"]
    elif "sentences" in dataset and isinstance(dataset["sentences"], list):
        for s in dataset["sentences"]:
            triples_list.extend(s.get("triples", []))

    for t in triples_list:
        # Check active or approved status
        st = t.get("status", "active")
        if st in ["active", "approved"]:
            tup = exact_triple_tuple(t) if mode == "exact" else canonicalize_triple(t)
            if tup != ("", "", ""):
                tuples.add(tup)
    return tuples


ROW_ATTRIBUTES = ("polarity", "modality", "scope", "note")


def extract_row_multiset(dataset: Dict[str, Any]) -> Counter:
    """Multiset of active/approved rows keyed by sentence, SPO and annotation attributes."""
    rows: Counter = Counter()
    if "triples" in dataset and isinstance(dataset["triples"], list):
        pairs = [(str(t.get("sentence_id") or ""), t) for t in dataset["triples"]]
    else:
        pairs = [
            (str(s.get("sentence_id") or s.get("id") or ""), t)
            for s in dataset.get("sentences", [])
            for t in s.get("triples", [])
        ]
    for sid, t in pairs:
        if t.get("status", "active") not in ("active", "approved"):
            continue
        spo = exact_triple_tuple(t)
        if spo == ("", "", ""):
            continue
        rows[(sid,) + spo + tuple(str(t.get(a) or "") for a in ROW_ATTRIBUTES)] += 1
    return rows


def analyze_single_run(
    recovered_path: Path,
    manifest_path: Path,
    ref_path: Path,
    mode: str = "exact",
) -> Dict[str, Any]:
    """Computes exact empirical recovery metrics for a single recovered file."""
    with open(ref_path, "r", encoding="utf-8") as fh:
        ref_data = json.load(fh)
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    with open(recovered_path, "r", encoding="utf-8") as fh:
        rec_data = json.load(fh)

    G = extract_triple_set(ref_data, mode=mode)
    R = extract_triple_set(rec_data, mode=mode)

    # 1. Set Precision, Recall, and F1
    tp_set = len(R.intersection(G))
    p_set = tp_set / len(R) if len(R) > 0 else 0.0
    r_set = tp_set / len(G) if len(G) > 0 else 0.0
    f1_set = (2 * p_set * r_set) / (p_set + r_set) if (p_set + r_set) > 0 else 0.0

    # 2. Corruption Repair Recall
    injected_changes = manifest.get("changes", [])
    total_injected = len(injected_changes)
    repaired_count = 0

    for ch in injected_changes:
        c_type = ch.get("corruption_type")
        before = ch.get("before")

        t_id = ch.get("triple_id")

        if c_type == "duplicate_triple":
            # For duplicates, verify the injected duplicate ID is pruned from exported triples
            rec_ids = {t.get("id") or t.get("triple_id") for t in rec_data.get("triples", [])}
            if t_id not in rec_ids:
                repaired_count += 1
        elif c_type == "spurious_triple":
            # For spurious triples, verify the hallucinated tuple is omitted from R
            after = ch.get("after")
            if after:
                tup_after = (after[0], after[1], after[2])
                if tup_after not in R:
                    repaired_count += 1
        elif before:
            # For substitutions and omissions, verify ground-truth triple is restored in R
            tup_before = (before[0], before[1], before[2])
            if tup_before in R:
                repaired_count += 1

    repair_recall = repaired_count / total_injected if total_injected > 0 else 1.0

    # 3. Untouched Preservation Rate
    corrupted_original_tuples = set()
    for ch in injected_changes:
        before = ch.get("before")
        if before:
            corrupted_original_tuples.add((before[0], before[1], before[2]))

    untouched_G = G - corrupted_original_tuples
    untouched_preserved = len(untouched_G.intersection(R))
    preservation_rate = untouched_preserved / len(untouched_G) if len(untouched_G) > 0 else 1.0

    # 4. SPO-set restoration and the stricter row-level restoration
    exact_match = (R == G)
    ref_rows = extract_row_multiset(ref_data)
    rec_rows = extract_row_multiset(rec_data)
    row_match = (ref_rows == rec_rows)
    rows_missing = sum((ref_rows - rec_rows).values())
    rows_extra = sum((rec_rows - ref_rows).values())

    return {
        "experiment_id": manifest.get("experiment_id"),
        "error_type": manifest.get("error_type"),
        "corruption_name": manifest.get("corruption_name"),
        "density": manifest.get("density"),
        "seed": manifest.get("seed"),
        "total_gold_triples": len(G),
        "total_recovered_triples": len(R),
        "injected_count": total_injected,
        "repaired_count": repaired_count,
        "set_precision": round(p_set, 4),
        "set_recall": round(r_set, 4),
        "set_f1": round(f1_set, 4),
        "repair_recall": round(repair_recall, 4),
        "untouched_spo_count": len(untouched_G),
        "untouched_preserved": untouched_preserved,
        "preservation_rate": round(preservation_rate, 4),
        "exact_match": exact_match,
        "reference_rows": sum(ref_rows.values()),
        "recovered_rows": sum(rec_rows.values()),
        "row_level_match": row_match,
        "rows_missing": rows_missing,
        "rows_extra": rows_extra,
    }


def analyze_all_runs(base_dir: Path) -> List[Dict[str, Any]]:
    """Analyzes all recovered experimental runs and generates CSV and LaTeX outputs."""
    ref_file = base_dir / "reference" / "reference_gold.json"
    rec_dir = base_dir / "recovered"
    man_dir = base_dir / "manifests"

    rec_files = sorted(list(rec_dir.glob("*.json")))
    if not rec_files:
        print(f"No recovered datasets found in {rec_dir}")
        return []

    print(f"Analyzing {len(rec_files)} recovered conditions against reference ground truth: {ref_file.name}")
    detailed_results = []

    for rf in rec_files:
        man_name = rf.name.replace("recovered_", "manifest_")
        mf = man_dir / man_name
        assert mf.exists(), f"Missing manifest for {rf.name}"

        res = analyze_single_run(rf, mf, ref_file)
        detailed_results.append(res)
        status_str = "SPO SET RESTORED" if res["exact_match"] else "SPO SET MISMATCH"
        row_str = "rows restored" if res["row_level_match"] else f"rows differ (-{res['rows_missing']}/+{res['rows_extra']})"
        print(f"  [{res['error_type']}] d={int(res['density']*100)}% seed={res['seed']}: Repair Recall={res['repair_recall']*100:.1f}% "
              f"({res['repaired_count']}/{res['injected_count']}), Preservation={res['untouched_preserved']}/{res['untouched_spo_count']}, "
              f"Set F1={res['set_f1']*100:.1f}% -> {status_str}; {row_str}")

    # 1. Write run-level CSV
    matrix_csv = RESULTS_DIR / "eq2_recovery_matrix.csv"
    with open(matrix_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "experiment_id", "error_type", "corruption_name", "density", "seed",
            "total_gold_triples", "total_recovered_triples", "injected_count", "repaired_count",
            "set_precision", "set_recall", "set_f1", "repair_recall",
            "untouched_spo_count", "untouched_preserved", "preservation_rate", "exact_match",
            "reference_rows", "recovered_rows", "row_level_match", "rows_missing", "rows_extra",
        ])
        writer.writeheader()
        for r in detailed_results:
            writer.writerow(r)
    print(f"\n[Saved] Run-level matrix written to: {matrix_csv}")

    # 2. Write aggregated summary CSV
    # Group by error_type and density
    groups: Dict[Tuple[str, float], List[Dict[str, Any]]] = {}
    for r in detailed_results:
        key = (r["error_type"], r["density"])
        groups.setdefault(key, []).append(r)

    summary_rows = []
    for (e_type, dens), group_runs in sorted(groups.items()):
        n_runs = len(group_runs)
        mean_p = sum(r["set_precision"] for r in group_runs) / n_runs
        mean_r = sum(r["set_recall"] for r in group_runs) / n_runs
        mean_f1 = sum(r["set_f1"] for r in group_runs) / n_runs
        mean_rec_recall = sum(r["repair_recall"] for r in group_runs) / n_runs
        mean_pres = sum(r["preservation_rate"] for r in group_runs) / n_runs
        exact_rate = sum(1 for r in group_runs if r["exact_match"]) / n_runs

        summary_rows.append({
            "error_type": e_type,
            "corruption_name": group_runs[0]["corruption_name"],
            "density": f"{int(dens*100)}%",
            "runs": n_runs,
            "mean_precision": f"{mean_p * 100:.2f}%",
            "mean_recall": f"{mean_r * 100:.2f}%",
            "mean_f1": f"{mean_f1 * 100:.2f}%",
            "mean_repair_recall": f"{mean_rec_recall * 100:.2f}%",
            "mean_preservation": f"{mean_pres * 100:.2f}%",
            "exact_restoration_rate": f"{exact_rate * 100:.1f}%",
        })

    summary_csv = RESULTS_DIR / "eq2_summary.csv"
    with open(summary_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "error_type", "corruption_name", "density", "runs",
            "mean_precision", "mean_recall", "mean_f1", "mean_repair_recall",
            "mean_preservation", "exact_restoration_rate"
        ])
        writer.writeheader()
        for s in summary_rows:
            writer.writerow(s)
    print(f"[Saved] Aggregated summary written to: {summary_csv}")

    return detailed_results


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    analyze_all_runs(base)
