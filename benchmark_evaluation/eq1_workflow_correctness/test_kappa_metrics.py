"""
test_kappa_metrics.py: agreement metric checks for the backend and the frontend.

1. Two raters: the backend value equals quadratic-weighted Cohen's kappa
   (sklearn.metrics.cohen_kappa_score, weights="quadratic", labels 0..10).
2. Fixed cases: known values, and undefined cases reported as N/A.
3. Parity: the frontend calcWeightedKappa (GradingForm.jsx), run unchanged with Node.js, prints
   the same value as the backend's formatted string.

Run: python -m pytest benchmark_evaluation/eq1_workflow_correctness/test_kappa_metrics.py
"""

import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from services.metrics_service import compute_weighted_kappa_from_items  # noqa: E402

GRADING_FORM = ROOT_DIR / "frontend" / "src" / "components" / "GradingForm.jsx"


def _random_items(rng: random.Random, n_raters: int, n_items: int):
    items = []
    for _ in range(n_items):
        base = rng.randint(0, 10)
        items.append({f"r{j}": min(10, max(0, base + rng.randint(-3, 3))) for j in range(n_raters)})
    return items


def test_two_rater_matches_cohen_quadratic():
    sklearn = pytest.importorskip("sklearn.metrics")
    rng = random.Random(11)
    for _ in range(300):
        items = _random_items(rng, 2, rng.randint(2, 25))
        a = [it["r0"] for it in items]
        b = [it["r1"] for it in items]
        result = compute_weighted_kappa_from_items(items)
        if len(set(a + b)) == 1:
            assert result["kappa"] is None
            continue
        expected = sklearn.cohen_kappa_score(a, b, weights="quadratic", labels=list(range(11)))
        assert result["metric_type"] == "Quadratic Weighted Cohen's Kappa"
        assert abs(result["kappa"] - expected) < 1e-4


@pytest.mark.parametrize("items, expected", [
    ([{"A": 0, "B": 0}, {"A": 0, "B": 10}], 0.0),
    ([dict(zip("ABC", r)) for r in [[9, 8, 9], [9, 9, 8], [7, 8, 7], [8, 7, 8]]], 0.4217),
    ([dict(zip("ABC", r)) for r in [[9, 8, 9], [9, 9, 8], [10, 9, 3], [8, 7, 8]]], -0.3174),
])
def test_known_values(items, expected):
    assert abs(compute_weighted_kappa_from_items(items)["kappa"] - expected) < 1e-4


@pytest.mark.parametrize("items", [
    [{"A": 8, "B": 8}, {"A": 8, "B": 8}],          # no rating variation
    [{"A": 5, "B": 6}],                            # a single co-rated item
    [{"A": 5}, {"B": 6}],                          # no co-rated items
])
def test_undefined_cases_are_not_available(items):
    result = compute_weighted_kappa_from_items(items)
    assert result["kappa"] is None
    assert result["formatted_str"].startswith("N/A")


def test_invalid_grades_are_excluded():
    items = [{"A": 11, "B": 3}, {"A": float("nan"), "B": 2}, {"A": 4, "B": 5}, {"A": 9, "B": 9}, {"A": 1, "B": 2}]
    result = compute_weighted_kappa_from_items(items)
    assert result["num_items"] == 3


def _extract_frontend_function() -> str:
    source = GRADING_FORM.read_text(encoding="utf-8")
    match = re.search(r"const calcWeightedKappa = \(itemsList\) => \{.*?\n    \};", source, re.S)
    assert match, "calcWeightedKappa not found in GradingForm.jsx"
    return match.group(0)


def test_frontend_matches_backend(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    rng = random.Random(5)
    cases = [_random_items(rng, rng.choice([2, 2, 3, 4]), rng.randint(2, 12)) for _ in range(200)]
    cases.append([{"A": 8.5, "B": 8}, {"A": 8.5, "B": 8}, {"A": 2, "B": 9}])
    cases.append([{"A": 8, "B": 8}, {"A": 8, "B": 8}])
    script = tmp_path / "kappa.js"
    script.write_text(
        _extract_frontend_function()
        + "\nconst cases = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));"
        + "\nconsole.log(JSON.stringify(cases.map(calcWeightedKappa)));\n",
        encoding="utf-8",
    )
    data = tmp_path / "cases.json"
    data.write_text(json.dumps(cases), encoding="utf-8")
    out = subprocess.run([node, str(script), str(data)], capture_output=True, text=True, check=True)
    frontend = json.loads(out.stdout)
    backend = [compute_weighted_kappa_from_items(c)["formatted_str"] for c in cases]
    assert frontend == backend
