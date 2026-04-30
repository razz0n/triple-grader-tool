"""Starter script for local knowledge-graph generation workflow.

This script intentionally stays lightweight so the team can wire graphifyy APIs
without impacting the main FastAPI runtime.
"""

from pathlib import Path

import pandas as pd


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    csv_path = project_root / "long_coe_tuples(Golden_dataset).csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"Loaded rows: {len(df)}")
    print("Next: map CSV columns to graphifyy entities/relations and write KG output.")


if __name__ == "__main__":
    main()
