"""
Downstream extraction performance and rank shift evaluation.

Evaluates extraction models against the raw pre-curation union (B0) versus
the human-adjudicated gold benchmark (B1) across 15 normative ethics sentences.
Computes score shifts (Delta F1) with 2,000-sample bootstrap 95% confidence intervals.
"""

import copy
import csv
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Tuple
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
EQ3_DIR = Path(__file__).resolve().parent
CANDIDATES_DIR = EQ3_DIR / "candidates"
RESULTS_DIR = ROOT_DIR / "benchmark_evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT_DIR))
from benchmark_evaluation.common.canonicalize import canonicalize_triple, exact_triple_tuple
from benchmark_evaluation.common.bootstrap import sentence_cluster_bootstrap


def load_benchmark_sentences(file_path: Path) -> List[Dict[str, Any]]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "sentences" in data:
        return data["sentences"]
    elif "versions" in data:
        return data["versions"][0]["sentences"]
    return []


def norm_str(s: str) -> str:
    return str(s or "").strip().lower().replace("_", "").replace("-", "").replace('"', "")


def triple_tuple(t: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        norm_str(t.get("subject", "")),
        norm_str(t.get("predicate", "")),
        norm_str(t.get("object", "")),
    )


def extract_sentence_triple_set(sentence_dict: Dict[str, Any], mode: str = "exact") -> Set[Tuple[str, str, str]]:
    t_set = set()
    for t in sentence_dict.get("triples", []):
        tup = triple_tuple(t)
        if tup != ("", "", ""):
            t_set.add(tup)
    return t_set


def compute_model_scores_on_corpus(
    model_predictions: List[Dict[str, Any]],
    gold_sentences: List[Dict[str, Any]],
    mode: str = "exact",
) -> Dict[str, Any]:
    """Computes micro and macro P, R, F1 across sentences."""
    pred_by_sent = {s["sentence_id"]: extract_sentence_triple_set(s, mode=mode) for s in model_predictions}
    gold_by_sent = {s["sentence_id"]: extract_sentence_triple_set(s, mode=mode) for s in gold_sentences}

    all_s_ids = sorted(list(gold_by_sent.keys()))

    total_tp = 0
    total_pred = 0
    total_gold = 0

    sentence_metrics = []
    sentence_records_for_boot = []

    for s_id in all_s_ids:
        p_set = pred_by_sent.get(s_id, set())
        g_set = gold_by_sent.get(s_id, set())

        tp = len(p_set.intersection(g_set))
        total_tp += tp
        total_pred += len(p_set)
        total_gold += len(g_set)

        p_s = tp / len(p_set) if len(p_set) > 0 else 0.0
        r_s = tp / len(g_set) if len(g_set) > 0 else 0.0
        f1_s = (2 * p_s * r_s) / (p_s + r_s) if (p_s + r_s) > 0 else 0.0

        sentence_metrics.append({"s_id": s_id, "p": p_s, "r": r_s, "f1": f1_s})
        sentence_records_for_boot.append({
            "s_id": s_id,
            "tp": tp,
            "n_pred": len(p_set),
            "n_gold": len(g_set),
            "p": p_s,
            "r": r_s,
            "f1": f1_s
        })

    # Micro scores
    micro_p = total_tp / total_pred if total_pred > 0 else 0.0
    micro_r = total_tp / total_gold if total_gold > 0 else 0.0
    micro_f1 = (2 * micro_p * micro_r) / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    # Macro scores
    macro_p = sum(m["p"] for m in sentence_metrics) / len(sentence_metrics) if sentence_metrics else 0.0
    macro_r = sum(m["r"] for m in sentence_metrics) / len(sentence_metrics) if sentence_metrics else 0.0
    macro_f1 = sum(m["f1"] for m in sentence_metrics) / len(sentence_metrics) if sentence_metrics else 0.0

    return {
        "micro_p": micro_p,
        "micro_r": micro_r,
        "micro_f1": micro_f1,
        "macro_p": macro_p,
        "macro_r": macro_r,
        "macro_f1": macro_f1,
        "total_pred": total_pred,
        "total_gold": total_gold,
        "total_tp": total_tp,
        "sentence_records": sentence_records_for_boot
    }


def compute_kendall_tau(rank_x: List[int], rank_y: List[int]) -> float:
    """Computes Kendall's tau rank correlation."""
    n = len(rank_x)
    if n <= 1:
        return 1.0
    concordant = 0
    discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            sign_x = (rank_x[i] > rank_x[j]) - (rank_x[i] < rank_x[j])
            sign_y = (rank_y[i] > rank_y[j]) - (rank_y[i] < rank_y[j])
            prod = sign_x * sign_y
            if prod > 0:
                concordant += 1
            elif prod < 0:
                discordant += 1
    total_pairs = n * (n - 1) / 2
    return (concordant - discordant) / total_pairs if total_pairs > 0 else 1.0


def compute_spearman_rho(rank_x: List[int], rank_y: List[int]) -> float:
    """Computes Spearman's rank correlation coefficient."""
    n = len(rank_x)
    if n <= 1:
        return 1.0
    d_sq = sum((rx - ry) ** 2 for rx, ry in zip(rank_x, rank_y))
    return 1.0 - (6 * d_sq) / (n * (n ** 2 - 1))


def bootstrap_ci_delta(records_b0: List[Dict[str, Any]], records_b1: List[Dict[str, Any]], n_resamples: int = 2000, seed: int = 42) -> Tuple[float, float]:
    rng = np.random.RandomState(seed)
    n = len(records_b0)
    deltas = []
    for _ in range(n_resamples):
        idx = rng.choice(n, size=n, replace=True)
        tp0 = sum(records_b0[i]["tp"] for i in idx)
        p0 = sum(records_b0[i]["n_pred"] for i in idx)
        g0 = sum(records_b0[i]["n_gold"] for i in idx)
        f0 = (2 * tp0) / (p0 + g0) if (p0 + g0) > 0 else 0.0

        tp1 = sum(records_b1[i]["tp"] for i in idx)
        p1 = sum(records_b1[i]["n_pred"] for i in idx)
        g1 = sum(records_b1[i]["n_gold"] for i in idx)
        f1 = (2 * tp1) / (p1 + g1) if (p1 + g1) > 0 else 0.0

        deltas.append(f1 - f0)
    return float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))


def run_downstream_evaluations():
    # 4 Evaluated extraction systems
    candidate_configs = [
        ("M1_ChatGPT_5_6_High", CANDIDATES_DIR / "candidates_chatgpt_5_6_high_sentences.json"),
        ("M2_Gemini_3_1_Pro", CANDIDATES_DIR / "candidates_gemini_3_1_pro_sentences.json"),
        ("M3_GPT_OSS_120B_FewShot", CANDIDATES_DIR / "candidates_gpt_oss_120b_sentences.json"),
        ("M4_Qwen_38B_FewShot", CANDIDATES_DIR / "candidates_qwen_38b_sentences.json"),
    ]

    loaded_sessions = {}
    for name, p in candidate_configs:
        with open(p, "r", encoding="utf-8") as f:
            loaded_sessions[name] = json.load(f)

    # Adjudicated gold benchmark B1 from final version
    sample_sess = list(loaded_sessions.values())[0]
    b1_sentences = sample_sess["versions"][-1]["sentences"]

    # Pre-curation union B0 across all 4 initial model outputs
    sample_initial = sample_sess["versions"][0]["sentences"]
    b0_sentences = []
    for idx, s in enumerate(sample_initial):
        sid = s["sentence_id"]
        seen = set()
        union_triples = []
        for sess in loaded_sessions.values():
            m_s = sess["versions"][0]["sentences"][idx]
            for t in m_s.get("triples", []):
                tup = triple_tuple(t)
                if tup not in seen and tup != ("", "", ""):
                    seen.add(tup)
                    union_triples.append(t)
        b0_sentences.append({
            "sentence_id": sid,
            "sentence_text": s["sentence_text"],
            "triples": union_triples
        })

    print("Evaluating LLM extraction systems against Raw B0 and Curated B1...")
    downstream_results = []

    for name, sess in loaded_sessions.items():
        pred_sents = sess["versions"][0]["sentences"]
        # Evaluate against B0 (raw pre-curation)
        score_b0 = compute_model_scores_on_corpus(pred_sents, b0_sentences, mode="exact")
        # Evaluate against B1 (curated gold)
        score_b1 = compute_model_scores_on_corpus(pred_sents, b1_sentences, mode="exact")

        # Delta F1 (Eq. 16)
        delta_f1 = score_b1["micro_f1"] - score_b0["micro_f1"]
        ci_lower, ci_upper = bootstrap_ci_delta(score_b0["sentence_records"], score_b1["sentence_records"])

        res_entry = {
            "system_name": name,
            "b0_micro_p": round(score_b0["micro_p"], 4),
            "b0_micro_r": round(score_b0["micro_r"], 4),
            "b0_micro_f1": round(score_b0["micro_f1"], 4),
            "b1_micro_p": round(score_b1["micro_p"], 4),
            "b1_micro_r": round(score_b1["micro_r"], 4),
            "b1_micro_f1": round(score_b1["micro_f1"], 4),
            "delta_f1": round(delta_f1, 4),
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
        }
        downstream_results.append(res_entry)

        print(f"  [{name:25s}] B0 F1: {res_entry['b0_micro_f1']*100:5.2f}% -> "
              f"B1 F1: {res_entry['b1_micro_f1']*100:5.2f}% | "
              f"Delta F1: {delta_f1*100:+5.2f}% (95% CI: [{ci_lower*100:.1f}%, {ci_upper*100:.1f}%])")

    # Compute Rank Shifts and Pairwise Reversals
    # Sort systems by B0 F1
    sorted_by_b0 = sorted(downstream_results, key=lambda x: x["b0_micro_f1"], reverse=True)
    for r_idx, s in enumerate(sorted_by_b0, start=1):
        s["rank_b0"] = r_idx

    # Sort systems by B1 F1
    sorted_by_b1 = sorted(downstream_results, key=lambda x: x["b1_micro_f1"], reverse=True)
    for r_idx, s in enumerate(sorted_by_b1, start=1):
        s["rank_b1"] = r_idx

    rank_b0 = [s["rank_b0"] for s in downstream_results]
    rank_b1 = [s["rank_b1"] for s in downstream_results]

    tau = compute_kendall_tau(rank_b0, rank_b1)
    rho = compute_spearman_rho(rank_b0, rank_b1)

    print(f"\n[Rank Correlation Analysis] Kendall's tau = {tau:.3f}, Spearman rho = {rho:.3f}")

    # Identify Pairwise Reversals
    reversals = []
    n_sys = len(downstream_results)
    for i in range(n_sys):
        for j in range(i + 1, n_sys):
            s_a = downstream_results[i]
            s_b = downstream_results[j]
            # Check if order flipped
            if (s_a["rank_b0"] < s_b["rank_b0"] and s_a["rank_b1"] > s_b["rank_b1"]) or \
               (s_a["rank_b0"] > s_b["rank_b0"] and s_a["rank_b1"] < s_b["rank_b1"]):
                reversals.append((s_a["system_name"], s_b["system_name"]))
                print(f"  [RANK REVERSAL DETECTED] Pair ({s_a['system_name']} vs {s_b['system_name']}) reversed order under B1!")

    # Save downstream evaluation CSV
    out_csv = RESULTS_DIR / "eq3_downstream.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "system_name", "b0_micro_p", "b0_micro_r", "b0_micro_f1",
            "b1_micro_p", "b1_micro_r", "b1_micro_f1", "delta_f1",
            "ci_lower", "ci_upper", "rank_b0", "rank_b1"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in downstream_results:
            writer.writerow(r)

    print(f"\n[Saved] Downstream evaluation results written to: {out_csv}")

    return {
        "downstream_results": downstream_results,
        "kendall_tau": tau,
        "spearman_rho": rho,
        "reversals": reversals
    }


if __name__ == "__main__":
    run_downstream_evaluations()
