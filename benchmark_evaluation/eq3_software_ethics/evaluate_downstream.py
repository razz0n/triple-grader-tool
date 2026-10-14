"""
Entry point kept for compatibility. EQ3 metrics for both domains are computed by
benchmark_evaluation/run_eq3.py from the frozen inputs, using the shared, order-invariant
definitions in benchmark_evaluation/common/eq3_metrics.py.

The earlier implementation in this file (greedy, order-dependent candidate-to-gold matching
and a hand-maintained provenance ledger) was replaced because its results depended on
triple order and on stale files.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from benchmark_evaluation.run_eq3 import main  # noqa: E402

# Names used by benchmark_evaluation/run_all_evaluations.py in earlier versions.
analyze_transformations = main
run_downstream_evaluations = main

if __name__ == "__main__":
    main()
