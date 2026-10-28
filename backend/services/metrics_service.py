"""
metrics_service.py — Inter-Rater Reliability Engine
Calculates quadratic-weighted agreement on the 0-10 ordinal grading scale:

- exactly two raters: quadratic-weighted Cohen's kappa (Cohen, 1968), with chance
  agreement computed from each rater's own score distribution;
- three or more raters: quadratic-weighted Fleiss-type kappa, with chance agreement
  computed from the pooled score distribution of all raters.

Both use the disagreement form kappa = 1 - D_o / D_e with squared score differences,
which is equivalent to the agreement-weight form with w_ij = 1 - (i - j)^2 / 10^2.
Kappa is reported as undefined (N/A) when fewer than two items are co-rated or when
the ratings show no variation (D_e = 0).
"""

import math
from typing import Dict, Any, List, Tuple, Optional

K_MIN_GRADE = 0
K_MAX_GRADE = 10
NUM_CATEGORIES = K_MAX_GRADE - K_MIN_GRADE + 1  # 11 categories: 0..10


def get_quadratic_weight(grade1: float, grade2: float) -> float:
    """
    Quadratic agreement weight for two grades on the 0..10 scale:
    w_ij = 1 - ((i - j)^2 / (10 - 0)^2)
    """
    diff_sq = (float(grade1) - float(grade2)) ** 2
    max_diff_sq = float(K_MAX_GRADE - K_MIN_GRADE) ** 2  # 100.0
    return 1.0 - (diff_sq / max_diff_sq)


def _clean_items(items_ratings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, float]], int]:
    """Keeps finite grades within [0, 10]; returns the cleaned items and the number dropped."""
    cleaned: List[Dict[str, float]] = []
    dropped = 0
    for item in items_ratings:
        row: Dict[str, float] = {}
        for rater, grade in item.items():
            try:
                value = float(grade)
            except (TypeError, ValueError):
                dropped += 1
                continue
            if not math.isfinite(value) or value < K_MIN_GRADE or value > K_MAX_GRADE:
                dropped += 1
                continue
            row[str(rater)] = value
        cleaned.append(row)
    return cleaned, dropped


def _not_available(reason: str, num_raters: int, num_items: int) -> Dict[str, Any]:
    return {
        "kappa": None,
        "metric_type": "N/A",
        "num_raters": num_raters,
        "num_items": num_items,
        "formatted_str": f"N/A ({reason})",
    }


def compute_weighted_kappa_from_items(
    items_ratings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Computes quadratic weighted inter-rater agreement across items.
    Each item in items_ratings is a dict mapping user_id -> grade (0..10).

    Selects Cohen's kappa when exactly two distinct raters appear on co-rated items and the
    Fleiss-type kappa otherwise. Returns N/A when fewer than two items are co-rated or when
    there is no rating variation.
    """
    cleaned, _dropped = _clean_items(items_ratings)
    valid_items = [item for item in cleaned if len(item) >= 2]

    all_raters = set()
    for item in valid_items:
        all_raters.update(item.keys())
    num_unique_raters = len(all_raters)

    if num_unique_raters < 2 or len(valid_items) < 2:
        return _not_available("Requires >= 2 raters on >= 2 items", num_unique_raters, len(valid_items))

    if num_unique_raters == 2:
        rater_a, rater_b = sorted(all_raters)
        pairs = [(item[rater_a], item[rater_b]) for item in valid_items]
        n = len(pairs)
        observed = sum((a - b) ** 2 for a, b in pairs) / n
        # Chance disagreement from the two raters' separate marginal distributions.
        expected = sum((a - b) ** 2 for a, _ in pairs for _, b in pairs) / (n * n)
        metric_name = "Quadratic Weighted Cohen's Kappa"
        rater_label = "Cohen's"
    else:
        n = len(valid_items)
        observed_sum = 0.0
        pooled: List[float] = []
        for item in valid_items:
            ratings = list(item.values())
            m = len(ratings)
            pair_sum = sum((ratings[i] - ratings[j]) ** 2 for i in range(m) for j in range(i + 1, m))
            observed_sum += pair_sum / (m * (m - 1) / 2)
            pooled.extend(ratings)
        observed = observed_sum / n
        # Chance disagreement from the pooled distribution of all ratings.
        total = len(pooled)
        mean = sum(pooled) / total
        expected = 2.0 * sum((g - mean) ** 2 for g in pooled) / total
        metric_name = "Quadratic Weighted Fleiss' Kappa"
        rater_label = "Fleiss'"

    if expected <= 1e-12:
        return _not_available("no rating variation; kappa undefined", num_unique_raters, n)

    kappa_val = 1.0 - observed / expected
    if abs(kappa_val) < 5e-5:
        kappa_val = 0.0
    formatted = f"{kappa_val:.2f} ({rater_label}, k={num_unique_raters}, n={n})"

    return {
        "kappa": round(kappa_val, 4),
        "metric_type": metric_name,
        "num_raters": num_unique_raters,
        "num_items": n,
        "formatted_str": formatted,
    }


def compute_session_kappa_metrics(session: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts ratings from a session and computes separate Kappa metrics for:
    1. Triple Quality Grades (kappa_triple)
    2. Sentence Completeness Scores (kappa_completeness)
    3. Sentence External Relation Scores (kappa_relation)
    4. Combined Overall Reliability (kappa_overall)
    """
    sentences = session.get("sentences", [])

    triple_items: List[Dict[str, int]] = []
    completeness_items: List[Dict[str, int]] = []
    relation_items: List[Dict[str, int]] = []
    all_items: List[Dict[str, int]] = []

    for s in sentences:
        # Completeness by user
        comp_by_user = s.get("completeness_by_user", {})
        comp_dict = {}
        if isinstance(comp_by_user, dict):
            for u_id, entry in comp_by_user.items():
                if isinstance(entry, dict):
                    v = entry.get("value")
                else:
                    v = entry
                if v is not None and v != "":
                    try:
                        comp_dict[str(u_id)] = float(v)
                    except (ValueError, TypeError):
                        pass

        if len(comp_dict) >= 2:
            completeness_items.append(comp_dict)
            all_items.append(comp_dict)

        # External Relation by user
        rel_by_user = s.get("external_relation_by_user", {})
        rel_dict = {}
        if isinstance(rel_by_user, dict):
            for u_id, entry in rel_by_user.items():
                if isinstance(entry, dict):
                    v = entry.get("value")
                else:
                    v = entry
                if v is not None and v != "":
                    try:
                        rel_dict[str(u_id)] = float(v)
                    except (ValueError, TypeError):
                        pass

        if len(rel_dict) >= 2:
            relation_items.append(rel_dict)
            all_items.append(rel_dict)

        # Triples
        for t in s.get("triples", []):
            grades_by_user = t.get("grades_by_user", {})
            t_dict = {}
            if isinstance(grades_by_user, dict):
                for u_id, entry in grades_by_user.items():
                    if isinstance(entry, dict):
                        g = entry.get("grade")
                    else:
                        g = entry
                    if g is not None and g != "":
                        try:
                            t_dict[str(u_id)] = float(g)
                        except (ValueError, TypeError):
                            pass

            if len(t_dict) >= 2:
                triple_items.append(t_dict)
                all_items.append(t_dict)

    res_triple = compute_weighted_kappa_from_items(triple_items)
    res_completeness = compute_weighted_kappa_from_items(completeness_items)
    res_relation = compute_weighted_kappa_from_items(relation_items)
    res_overall = compute_weighted_kappa_from_items(all_items)

    return {
        "triple_kappa": res_triple,
        "completeness_kappa": res_completeness,
        "relation_kappa": res_relation,
        "overall_kappa": res_overall,
    }
