"""
run_all_evaluations.py: regenerates every evaluation table with one command.

    python benchmark_evaluation/run_all_evaluations.py            # EQ1, EQ2 analysis, EQ3
    python benchmark_evaluation/run_all_evaluations.py --replay   # also re-run the EQ2 oracle replay

All suites run against an isolated local JSON/SQLite store (common/local_backend.py), never a
hosted database.

  1. EQ1: workflow matrix T01-T18 plus agreement-metric and security regression tests
  2. EQ2: controlled corruption recovery (E1-E10); --replay re-issues the oracle actions
  3. EQ3: frozen-input check, then the curation counts of Table III
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from benchmark_evaluation.common.local_backend import use_isolated_local_storage  # noqa: E402

use_isolated_local_storage()

from benchmark_evaluation.eq1_workflow_correctness.run_eq1_evaluation import run_evaluation as run_eq1  # noqa: E402
from benchmark_evaluation.eq2_controlled_recovery.analyze_recovery import analyze_all_runs as run_eq2  # noqa: E402
from benchmark_evaluation.run_eq3 import main as run_eq3  # noqa: E402

BENCH_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BENCH_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_OUTPUTS = [
    "eq1_workflow_matrix.csv",
    "eq1_summary.csv",
    "eq2_recovery_matrix.csv",
    "eq2_summary.csv",
    "eq3_curation.csv",
    "eq3_summary.json",
    "eq3_tables.tex",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", action="store_true", help="re-run the EQ2 oracle replay before analysis")
    args = ap.parse_args()

    t_start = time.perf_counter()

    print("\n[1/3] EQ1 workflow matrix")
    eq1 = run_eq1()
    print(f"  -> {eq1['passed']}/{eq1['total']} scenarios passed")
    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-W", "ignore",
         str(BENCH_DIR / "eq1_workflow_correctness")],
        cwd=ROOT_DIR,
    )
    if tests.returncode != 0:
        sys.exit("EQ1 regression tests failed")

    print("\n[2/3] EQ2 controlled recovery")
    eq2_dir = BENCH_DIR / "eq2_controlled_recovery"
    if args.replay:
        from benchmark_evaluation.eq2_controlled_recovery.replay_oracle_actions import replay_all_conditions
        replay_all_conditions(eq2_dir)
    eq2 = run_eq2(eq2_dir)
    restored = sum(1 for r in eq2 if r["exact_match"] and r["row_level_match"])
    print(f"  -> {restored}/{len(eq2)} conditions restored at SPO-set and row level")

    print("\n[3/3] EQ3 frozen inputs and curation counts")
    freeze = subprocess.run([sys.executable, str(BENCH_DIR / "freeze_eq3.py")], cwd=ROOT_DIR)
    if freeze.returncode != 0:
        sys.exit("EQ3 frozen inputs changed; see freeze_eq3.py output")
    run_eq3()

    missing = [f for f in EXPECTED_OUTPUTS if not (RESULTS_DIR / f).exists()]
    print(f"\nFinished in {time.perf_counter() - t_start:.1f}s")
    if missing:
        sys.exit(f"Missing outputs: {missing}")


if __name__ == "__main__":
    main()
