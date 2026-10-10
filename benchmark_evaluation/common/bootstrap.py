"""
bootstrap.py — Sentence-Cluster Bootstrap Resampling.

Implements cluster bootstrap resampling where resampling units are sentences
rather than individual triples to account for intra-sentence correlation.
"""

import random
from typing import Any, Callable, Dict, List, Tuple


def sentence_cluster_bootstrap(
    sentence_records: List[Dict[str, Any]],
    metric_fn: Callable[[List[Dict[str, Any]]], float],
    n_resamples: int = 2000,
    confidence_level: float = 0.95,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Performs sentence-cluster bootstrap resampling.
    
    Args:
        sentence_records: List of sentence-level dictionaries (each containing its triples).
        metric_fn: Function mapping resampled sentence records to a single float metric.
        n_resamples: Number of bootstrap samples.
        confidence_level: Desired coverage (default 0.95).
        random_seed: Seed for reproducibility.
        
    Returns:
        Dict with 'point_estimate', 'ci_lower', 'ci_upper', 'std_err', 'samples'.
    """
    if not sentence_records:
        return {"point_estimate": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "std_err": 0.0}

    rng = random.Random(random_seed)
    point_est = metric_fn(sentence_records)
    n = len(sentence_records)

    bootstrap_estimates: List[float] = []
    for _ in range(n_resamples):
        sample = [sentence_records[rng.randrange(n)] for _ in range(n)]
        score = metric_fn(sample)
        bootstrap_estimates.append(score)

    bootstrap_estimates.sort()
    alpha = (1.0 - confidence_level) / 2.0
    low_idx = int(alpha * n_resamples)
    high_idx = int((1.0 - alpha) * n_resamples)
    high_idx = min(high_idx, n_resamples - 1)

    mean_boot = sum(bootstrap_estimates) / n_resamples
    var_boot = sum((x - mean_boot) ** 2 for x in bootstrap_estimates) / (n_resamples - 1) if n_resamples > 1 else 0.0
    std_err = var_boot ** 0.5

    return {
        "point_estimate": round(point_est, 4),
        "ci_lower": round(bootstrap_estimates[low_idx], 4),
        "ci_upper": round(bootstrap_estimates[high_idx], 4),
        "std_err": round(std_err, 4),
    }
