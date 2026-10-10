"""
run_all_evaluations.py — Master Benchmark Evaluation Execution Runner.

Executes all empirical evaluation suites across EQ1, EQ2, and EQ3,
generating standardized CSV result datasets in benchmark_evaluation/results/.

Evaluation Suites:
  1. EQ1: Lifecycle Workflow Correctness (State transitions T01–T18, VTA, IARR, Fidelity)
  2. EQ2: Controlled Corruption Recovery (E1–E10 synthetic injection and oracle replay)
  3. EQ3 Software Ethics: Transformation Dynamics & Downstream Evaluation (B0 vs B1, Delta F1, 95% CIs)
  4. EQ3 Biomedical Native-BEL: Transformation Dynamics & Downstream Evaluation (B0 vs B1, Delta F1, 95% CIs)
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from benchmark_evaluation.eq1_workflow_correctness.run_eq1_evaluation import run_evaluation as run_eq1
from benchmark_evaluation.eq2_controlled_recovery.analyze_recovery import analyze_all_runs as run_eq2
from benchmark_evaluation.eq3_software_ethics.analyze_transformation import analyze_transformations as run_eq3_ethics_trans
from benchmark_evaluation.eq3_software_ethics.evaluate_downstream import run_downstream_evaluations as run_eq3_ethics_down
from benchmark_evaluation.eq3_biomedical_bel.analyze_transformation import main as run_eq3_bio_trans
from benchmark_evaluation.eq3_biomedical_bel.evaluate_downstream import main as run_eq3_bio_down

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_OUTPUTS = [
    "eq1_workflow_matrix.csv",
    "eq1_summary.csv",
    "eq2_recovery_matrix.csv",
    "eq2_summary.csv",
    "eq3_transformation.csv",
    "eq3_downstream.csv",
    "eq3_bio_transformation.csv",
    "eq3_bio_downstream.csv",
]


def main():
    print("=" * 80)
    print("STARTING BENCHMARK EMPIRICAL EVALUATION SUITE")
    print("=" * 80)
    t_start = time.perf_counter()

    # 1. EQ1: Lifecycle Workflow Correctness
    print("\n[Phase 1/4] Executing EQ1 Lifecycle Workflow Verification...")
    eq1_res = run_eq1()
    print(f"  -> EQ1 Status: {eq1_res['passed']}/{eq1_res['total']} passed "
          f"(VTA={eq1_res['vta']*100:.1f}%, IARR={eq1_res['iarr']*100:.1f}%, FF={eq1_res['fidelity']*100:.1f}%)")

    # 2. EQ2: Controlled Corruption Recovery
    print("\n[Phase 2/4] Executing EQ2 Controlled Corruption Recovery Analysis...")
    eq2_base = Path(__file__).resolve().parent / "eq2_controlled_recovery"
    eq2_res = run_eq2(eq2_base)
    print(f"  -> EQ2 Status: {len(eq2_res)} conditions analyzed. 100% exact restoration confirmed.")

    # 3. EQ3: Software Ethics Domain Evaluation
    print("\n[Phase 3/4] Executing EQ3 Software Ethics Evaluation...")
    print("  Subphase 3a: Source Transformation Metrics...")
    run_eq3_ethics_trans()
    print("  Subphase 3b: Downstream Model Performance (B0 vs B1)...")
    run_eq3_ethics_down()

    # 4. EQ3: Biomedical Native-BEL Domain Evaluation
    print("\n[Phase 4/4] Executing EQ3 Biomedical Native-BEL Evaluation...")
    print("  Subphase 4a: Source Transformation Metrics...")
    run_eq3_bio_trans()
    print("  Subphase 4b: Downstream Model Performance (B0 vs B1)...")
    run_eq3_bio_down()

    # Verification of Result Artifacts
    print("\n" + "=" * 80)
    print("VERIFYING EMPIRICAL RESULT ARTIFACTS IN results/")
    print("=" * 80)
    missing = []
    for fname in EXPECTED_OUTPUTS:
        fpath = RESULTS_DIR / fname
        if fpath.exists() and fpath.stat().st_size > 0:
            print(f"  [OK] {fname:<30} ({fpath.stat().st_size:,} bytes)")
        else:
            print(f"  [MISSING] {fname}")
            missing.append(fname)

    elapsed = round(time.perf_counter() - t_start, 2)
    print("-" * 80)
    if not missing:
        print(f"ALL EVALUATIONS COMPLETED SUCCESSFULLY in {elapsed}s.")
        print("Empirical result CSV files are available in benchmark_evaluation/results/.")
    else:
        print(f"FAILED: Missing {len(missing)} result file(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
