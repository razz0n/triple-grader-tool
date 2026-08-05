"""
metrics_service.py — Inter-Rater Reliability Engine
Calculates Quadratic Weighted Cohen's Kappa (for 2 raters) and
Quadratic Weighted Fleiss' Kappa (for 3+ raters) across ordinal grades (0-10).
"""

from typing import Dict, Any, List, Tuple, Optional

K_MIN_GRADE = 0
K_MAX_GRADE = 10
NUM_CATEGORIES = K_MAX_GRADE - K_MIN_GRADE + 1  # 11 categories: 0..10


def get_quadratic_weight(grade1: int, grade2: int) -> float:
    """
    Computes the quadratic weight for two ordinal grades in range [0..10].
    w_ij = 1 - ((i - j)^2 / (10 - 0)^2)
    - If grade1 == grade2: w = 1.0 (perfect agreement)
    - If diff = 1 (e.g., 7 vs 8): w = 0.99
    - If diff = 6 (e.g., 2 vs 8): w = 0.64
    """
    diff_sq = (float(grade1) - float(grade2)) ** 2
    max_diff_sq = float(K_MAX_GRADE - K_MIN_GRADE) ** 2  # 100.0
    return 1.0 - (diff_sq / max_diff_sq)


def compute_weighted_kappa_from_items(
    items_ratings: List[Dict[str, int]]
) -> Dict[str, Any]:
    """
    Computes quadratic weighted inter-rater agreement across items.
    Each item in items_ratings is a dict mapping user_id -> grade (int 0..10).

    Automatically selects:
    - Quadratic Weighted Cohen's Kappa if total unique raters across items == 2
    - Quadratic Weighted Fleiss' Kappa if total unique raters across items > 2
    - Returns N/A if fewer than 2 items or raters exist.
    """
    # Filter items that have at least 2 raters
    valid_items = [
        item for item in items_ratings
        if len(item) >= 2
    ]

    if not valid_items:
        return {
            "kappa": None,
            "metric_type": "N/A",
            "num_raters": 0,
            "num_items": 0,
            "formatted_str": "N/A (Requires >= 2 raters)",
        }

    # Find total unique raters across all valid items
    all_raters = set()
    for item in valid_items:
        all_raters.update(item.keys())

    num_unique_raters = len(all_raters)

    if num_unique_raters < 2:
        return {
            "kappa": None,
            "metric_type": "N/A",
            "num_raters": num_unique_raters,
            "num_items": len(valid_items),
            "formatted_str": "N/A (Requires >= 2 raters)",
        }

    # Calculate observed weighted agreement P_o across all items
    total_observed_weight = 0.0
    total_pairs = 0

    category_counts = {c: 0 for c in range(NUM_CATEGORIES)}
    total_individual_ratings = 0

    for item in valid_items:
        ratings = list(item.values())
        m = len(ratings)
        if m < 2:
            continue

        # Pairwise observed weights within this item
        item_weight_sum = 0.0
        item_pair_count = 0
        for i in range(m):
            category_counts[int(ratings[i])] += 1
            total_individual_ratings += 1
            for j in range(i + 1, m):
                w = get_quadratic_weight(int(ratings[i]), int(ratings[j]))
                item_weight_sum += w
                item_pair_count += 1

        if item_pair_count > 0:
            total_observed_weight += (item_weight_sum / item_pair_count)
            total_pairs += 1

    if total_pairs == 0 or total_individual_ratings == 0:
        return {
            "kappa": None,
            "metric_type": "N/A",
            "num_raters": num_unique_raters,
            "num_items": len(valid_items),
            "formatted_str": "N/A",
        }

    p_o = total_observed_weight / float(total_pairs)

    # Calculate chance expected weighted agreement P_e from overall category distribution
    cat_probs = {
        c: category_counts[c] / float(total_individual_ratings)
        for c in range(NUM_CATEGORIES)
    }

    p_e = 0.0
    for c1 in range(NUM_CATEGORIES):
        for c2 in range(NUM_CATEGORIES):
            w = get_quadratic_weight(c1, c2)
            p_e += w * cat_probs[c1] * cat_probs[c2]

    # Compute Kappa
    if abs(1.0 - p_e) < 1e-9:
        kappa_val = 1.0 if abs(p_o - 1.0) < 1e-9 else 0.0
    else:
        kappa_val = (p_o - p_e) / (1.0 - p_e)

    # Bound kappa between -1.0 and 1.0 for numerical safety
    kappa_val = max(-1.0, min(1.0, kappa_val))

    metric_name = (
        "Quadratic Weighted Cohen's Kappa"
        if num_unique_raters == 2
        else "Quadratic Weighted Fleiss' Kappa"
    )

    rater_label = "Cohen's" if num_unique_raters == 2 else "Fleiss'"
    formatted = f"{kappa_val:.2f} ({rater_label}, k={num_unique_raters})"

    return {
        "kappa": round(kappa_val, 4),
        "metric_type": metric_name,
        "num_raters": num_unique_raters,
        "num_items": len(valid_items),
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
                        comp_dict[str(u_id)] = int(float(v))
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
                        rel_dict[str(u_id)] = int(float(v))
                    except (ValueError, TypeError):
                        pass

        if len(rel_dict) >= 2:
            relation_items.append(rel_dict)
            all_items.append(rel_dict)

        # Triples
        for t in s.get("triples", []):
            if t.get("marked_for_removal"):
                continue

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
                            t_dict[str(u_id)] = int(float(g))
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
