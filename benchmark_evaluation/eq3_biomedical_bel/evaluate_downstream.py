"""
Downstream extraction performance and generator leakage evaluator for Biomedical Native-BEL.

Evaluates extraction models against the raw pre-curation union (B0) versus
the human-adjudicated gold benchmark (B1) across 40 target sentences.
Computes score shifts (Delta F1) with 2,000-sample bootstrap 95% confidence intervals.
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
EXP_DIR = Path(__file__).resolve().parent
CAND_DIR = EXP_DIR / "candidates"
RESULTS_DIR = ROOT_DIR / "benchmark_evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def norm_str(s: str) -> str:
    return str(s or "").strip().lower().replace("_", "").replace("-", "").replace('"', "")


def triple_tuple(t: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        norm_str(t.get("subject", "")),
        norm_str(t.get("predicate", "")),
        norm_str(t.get("object", "")),
    )


def extract_triple_set(sentence_dict: Dict[str, Any]) -> Set[Tuple[str, str, str]]:
    res = set()
    for t in sentence_dict.get("triples", []):
        tup = triple_tuple(t)
        if tup != ("", "", ""):
            res.add(tup)
    return res


def compute_corpus_scores(pred_sentences: List[Dict[str, Any]], gold_sentences: List[Dict[str, Any]]) -> Dict[str, Any]:
    pred_by_sid = {s["sentence_id"]: extract_triple_set(s) for s in pred_sentences}
    gold_by_sid = {s["sentence_id"]: extract_triple_set(s) for s in gold_sentences}

    all_sids = sorted(list(gold_by_sid.keys()))

    total_tp = 0
    total_pred = 0
    total_gold = 0
    sentence_records = []

    for sid in all_sids:
        p_set = pred_by_sid.get(sid, set())
        g_set = gold_by_sid.get(sid, set())

        tp = len(p_set.intersection(g_set))
        total_tp += tp
        total_pred += len(p_set)
        total_gold += len(g_set)

        p = tp / len(p_set) if len(p_set) > 0 else 0.0
        r = tp / len(g_set) if len(g_set) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0

        sentence_records.append({
            "sid": sid,
            "tp": tp,
            "n_pred": len(p_set),
            "n_gold": len(g_set),
            "f1": f1
        })

    micro_p = total_tp / total_pred if total_pred > 0 else 0.0
    micro_r = total_tp / total_gold if total_gold > 0 else 0.0
    micro_f1 = (2 * micro_p * micro_r) / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    return {
        "micro_p": micro_p,
        "micro_r": micro_r,
        "micro_f1": micro_f1,
        "sentence_records": sentence_records
    }


def bootstrap_ci_delta(records_b0: List[Dict[str, Any]], records_b1: List[Dict[str, Any]], n_resamples: int = 2000, seed: int = 42) -> Tuple[float, float]:
    rng = np.random.RandomState(seed)
    n = len(records_b0)
    deltas = []

    for _ in range(n_resamples):
        indices = rng.choice(n, size=n, replace=True)

        tp0 = sum(records_b0[i]["tp"] for i in indices)
        p0 = sum(records_b0[i]["n_pred"] for i in indices)
        g0 = sum(records_b0[i]["n_gold"] for i in indices)
        f1_0 = (2 * tp0) / (p0 + g0) if (p0 + g0) > 0 else 0.0

        tp1 = sum(records_b1[i]["tp"] for i in indices)
        p1 = sum(records_b1[i]["n_pred"] for i in indices)
        g1 = sum(records_b1[i]["n_gold"] for i in indices)
        f1_1 = (2 * tp1) / (p1 + g1) if (p1 + g1) > 0 else 0.0

        deltas.append(f1_1 - f1_0)

    ci_lower = float(np.percentile(deltas, 2.5))
    ci_upper = float(np.percentile(deltas, 97.5))
    return ci_lower, ci_upper


def main():
    models = [
        ("M1_ChatGPT_5_6_High", CAND_DIR / "candidates_chatgpt_5_6_high_sentences.json"),
        ("M2_Gemini_3_1_Pro", CAND_DIR / "candidates_gemini_3_1_pro_sentences.json"),
        ("M3_GPT_OSS_120B", CAND_DIR / "candidates_gpt_oss_120b_sentences.json"),
        ("M4_Qwen_38B", CAND_DIR / "candidates_qwen_38b_sentences.json")
    ]

    loaded_sessions = {}
    for name, p in models:
        with open(p, "r", encoding="utf-8") as f:
            loaded_sessions[name] = json.load(f)

    sample_sess = list(loaded_sessions.values())[0]
    b1_sentences = sample_sess["versions"][-1]["sentences"]

    # Build uncurated candidate union (B0)
    b0_sentences = []
    first_sess_initial = sample_sess["versions"][0]["sentences"]
    for idx, s in enumerate(first_sess_initial):
        sid = s["sentence_id"]
        union_triples = []
        seen = set()
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

    downstream_results = []
    for name, sess in loaded_sessions.items():
        pred_sentences = sess["versions"][0]["sentences"]

        res_b0 = compute_corpus_scores(pred_sentences, b0_sentences)
        res_b1 = compute_corpus_scores(pred_sentences, b1_sentences)

        delta_f1 = res_b1["micro_f1"] - res_b0["micro_f1"]
        ci_lower, ci_upper = bootstrap_ci_delta(res_b0["sentence_records"], res_b1["sentence_records"])

        downstream_results.append({
            "system_name": name,
            "b0_micro_p": round(res_b0["micro_p"], 4),
            "b0_micro_r": round(res_b0["micro_r"], 4),
            "b0_micro_f1": round(res_b0["micro_f1"], 4),
            "b1_micro_p": round(res_b1["micro_p"], 4),
            "b1_micro_r": round(res_b1["micro_r"], 4),
            "b1_micro_f1": round(res_b1["micro_f1"], 4),
            "delta_f1": round(delta_f1, 4),
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
        })

    # Add rankings
    downstream_results.sort(key=lambda x: x["b0_micro_f1"], reverse=True)
    for rank, item in enumerate(downstream_results, start=1):
        item["rank_b0"] = rank

    downstream_results.sort(key=lambda x: x["b1_micro_f1"], reverse=True)
    for rank, item in enumerate(downstream_results, start=1):
        item["rank_b1"] = rank

    out_csv = RESULTS_DIR / "eq3_bio_downstream.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        fields = [
            "system_name", "b0_micro_p", "b0_micro_r", "b0_micro_f1",
            "b1_micro_p", "b1_micro_r", "b1_micro_f1", "delta_f1",
            "ci_lower", "ci_upper", "rank_b0", "rank_b1"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(downstream_results)

    print(f"Saved downstream evaluation metrics to {out_csv}")


if __name__ == "__main__":
    main()
