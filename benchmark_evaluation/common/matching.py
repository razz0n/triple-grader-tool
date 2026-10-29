"""
Set precision, recall and F1 of a triple set against a reference set, used by the EQ1 export
checks.
"""

from typing import Any, Dict, List, Set, Tuple
from .canonicalize import canonicalize_triple, exact_triple_tuple


def compute_set_metrics(
    evaluated_triples: List[Dict[str, Any]],
    gold_triples: List[Dict[str, Any]],
    mode: str = "exact",
) -> Dict[str, float]:
    """
    Computes Set Precision, Recall, and F1 against reference gold.
    Modes:
      - 'exact': exact character match on (subject, predicate, object)
      - 'normalized': normalized match (case-folded, whitespace-collapsed)
    """
    extractor = exact_triple_tuple if mode == "exact" else canonicalize_triple

    eval_set: Set[Tuple[str, str, str]] = set(extractor(t) for t in evaluated_triples if extractor(t) != ("", "", ""))
    gold_set: Set[Tuple[str, str, str]] = set(extractor(t) for t in gold_triples if extractor(t) != ("", "", ""))

    if not eval_set and not gold_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "true_positives": 0, "eval_count": 0, "gold_count": 0}

    intersection = eval_set.intersection(gold_set)
    tp = len(intersection)
    prec = tp / len(eval_set) if len(eval_set) > 0 else 0.0
    rec = tp / len(gold_set) if len(gold_set) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "true_positives": tp,
        "eval_count": len(eval_set),
        "gold_count": len(gold_set),
    }
