"""
eq3_metrics.py — Shared, order-invariant EQ3 metrics for both curation domains.

Every EQ3 number reported in the paper is computed here, so the Software Ethics
and Biomedical Native-BEL experiments use identical definitions.

Inputs are endpoint snapshots only: the model candidates (initial session
version) and the curated reference B1 (final session version). The snapshots
do not contain a log of reviewer actions, so the candidate/reference
alignment below is an estimate of the curation outcome, not a record of it.

Matching rule (used everywhere): a triple is reduced to a per-sentence key of
three slots, each trimmed, lower-cased, with underscores, hyphens and double
quotes removed (`norm_slot`). Two triples match exactly when all three
normalized slots are equal within the same sentence.

Candidate outcomes (a partition of the candidates of one source):
  exact      – the normalized triple is in B1 for that sentence
  near_miss  – not exact, but some B1 triple of the same sentence agrees on at
               least two of the three normalized slots
  unaligned  – neither of the above

Reference outcomes (a partition of B1):
  exact_covered – some candidate matches it exactly
  near_covered  – no exact candidate, but some candidate is a near miss to it
  uncovered     – no candidate is exact or a near miss

None of these rules consume reference triples, so results do not depend on the
order of candidates or reference triples.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

import numpy as np

Key = Tuple[str, str, str]

MODEL_FILES = [
    ("ChatGPT-5.6-High", "candidates_chatgpt_5_6_high_sentences.json"),
    ("Gemini-3.1-Pro", "candidates_gemini_3_1_pro_sentences.json"),
    ("GPT-OSS 120B", "candidates_gpt_oss_120b_sentences.json"),
    ("Qwen 3.8 27B", "candidates_qwen_38b_sentences.json"),
]

BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42


# ---------------------------------------------------------------------------
# Normalization and loading
# ---------------------------------------------------------------------------

def norm_slot(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "").replace("-", "").replace('"', "")


def triple_key(t: Dict[str, Any]) -> Key:
    return (norm_slot(t.get("subject")), norm_slot(t.get("predicate")), norm_slot(t.get("object")))


def sentence_sets(sentences: List[Dict[str, Any]]) -> Dict[str, Set[Key]]:
    """Per-sentence set of normalized triples; empty placeholder triples are dropped."""
    out: Dict[str, Set[Key]] = {}
    for s in sentences:
        keys = {triple_key(t) for t in s.get("triples", [])}
        keys.discard(("", "", ""))
        out[s["sentence_id"]] = keys
    return out


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_candidate_sessions(cand_dir: Path) -> Dict[str, Dict[str, Any]]:
    return {name: load_json(cand_dir / fname) for name, fname in MODEL_FILES}


def build_union(sessions: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalized union of the initial (uncurated) candidates of all sources, per sentence."""
    first = next(iter(sessions.values()))["versions"][0]["sentences"]
    by_sid: Dict[str, Dict[str, Any]] = {}
    for s in first:
        by_sid[s["sentence_id"]] = {
            "sentence_id": s["sentence_id"],
            "sentence_text": s.get("sentence_text") or s.get("text", ""),
            "triples": [],
            "_seen": set(),
        }
    for name, sess in sessions.items():
        for s in sess["versions"][0]["sentences"]:
            entry = by_sid[s["sentence_id"]]
            for t in s.get("triples", []):
                k = triple_key(t)
                if k == ("", "", ""):
                    continue
                if k in entry["_seen"]:
                    for existing in entry["triples"]:
                        if triple_key(existing) == k and name not in existing["source_candidates"]:
                            existing["source_candidates"].append(name)
                    continue
                entry["_seen"].add(k)
                entry["triples"].append({
                    "subject": t.get("subject"),
                    "predicate": t.get("predicate"),
                    "object": t.get("object"),
                    "source_candidates": [name],
                })
    out = []
    for s in first:
        e = by_sid[s["sentence_id"]]
        e.pop("_seen")
        out.append(e)
    return out


def verify_frozen(exp_dir: Path) -> Dict[str, Any]:
    """Checks every file listed in FROZEN_MANIFEST.json against its recorded SHA-256."""
    manifest_path = exp_dir / "FROZEN_MANIFEST.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"{manifest_path} missing; run freeze_eq3.py once to create it")
    manifest = load_json(manifest_path)
    for rel, digest in manifest["sha256"].items():
        actual = sha256_file(exp_dir / rel)
        if actual != digest:
            raise RuntimeError(f"Frozen artifact changed: {rel} (expected {digest[:12]}, found {actual[:12]})")
    return manifest


# ---------------------------------------------------------------------------
# Candidate-to-reference alignment (order-invariant)
# ---------------------------------------------------------------------------

def _near(a: Key, b: Key) -> bool:
    return sum(x == y for x, y in zip(a, b)) >= 2


def alignment(cand: Dict[str, Set[Key]], gold: Dict[str, Set[Key]]) -> Dict[str, int]:
    exact = near = unaligned = 0
    g_exact = g_near = g_uncovered = 0
    n_cand = 0
    for sid in gold:
        c_set = cand.get(sid, set())
        g_set = gold[sid]
        n_cand += len(c_set)
        for c in c_set:
            if c in g_set:
                exact += 1
            elif any(_near(c, g) for g in g_set):
                near += 1
            else:
                unaligned += 1
        for g in g_set:
            if g in c_set:
                g_exact += 1
            elif any(_near(c, g) for c in c_set):
                g_near += 1
            else:
                g_uncovered += 1
    extra = set(cand) - set(gold)
    if extra:
        raise ValueError(f"Candidate sentences missing from reference: {sorted(extra)[:5]}")
    return {
        "n_candidates": n_cand,
        "exact": exact,
        "near_miss": near,
        "unaligned": unaligned,
        "n_reference": sum(len(v) for v in gold.values()),
        "ref_exact_covered": g_exact,
        "ref_near_covered": g_near,
        "ref_uncovered": g_uncovered,
    }


# ---------------------------------------------------------------------------
# Downstream scoring
# ---------------------------------------------------------------------------

def sentence_counts(pred: Dict[str, Set[Key]], gold: Dict[str, Set[Key]]) -> List[Tuple[int, int, int]]:
    """(tp, |pred|, |gold|) per reference sentence, in sorted sentence order."""
    return [(len(pred.get(sid, set()) & gold[sid]), len(pred.get(sid, set())), len(gold[sid])) for sid in sorted(gold)]


def micro_prf(counts: Iterable[Tuple[int, int, int]]) -> Tuple[float, float, float]:
    tp = n_pred = n_gold = 0
    for a, b, c in counts:
        tp += a
        n_pred += b
        n_gold += c
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    f = 2 * tp / (n_pred + n_gold) if (n_pred + n_gold) else 0.0
    return p, r, f


def paired_bootstrap_delta_f1(c0: List[Tuple[int, int, int]], c1: List[Tuple[int, int, int]],
                              n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> Tuple[float, float]:
    """Sentence-level paired bootstrap of micro-F1(c1) - micro-F1(c0); returns the 95% percentile interval."""
    a0 = np.array(c0, dtype=float)
    a1 = np.array(c1, dtype=float)
    rng = np.random.RandomState(seed)
    n = len(a0)
    deltas = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.choice(n, size=n, replace=True)
        s0 = a0[idx].sum(axis=0)
        s1 = a1[idx].sum(axis=0)
        f0 = 2 * s0[0] / (s0[1] + s0[2]) if (s0[1] + s0[2]) else 0.0
        f1 = 2 * s1[0] / (s1[1] + s1[2]) if (s1[1] + s1[2]) else 0.0
        deltas[i] = f1 - f0
    return float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))


def split_insensitive_overlap(cand_sentences: List[Dict[str, Any]], gold_sentences: List[Dict[str, Any]]) -> int:
    """Exact overlap after joining S, P and O and dropping spaces and parentheses.

    A robustness check for BEL statements, whose split into subject, predicate and object
    is not unique for nested statements.
    """
    def keys(sentences):
        return {
            s["sentence_id"]: {"".join(triple_key(t)).replace(" ", "").replace("(", "").replace(")", "")
                               for t in s.get("triples", []) if triple_key(t) != ("", "", "")}
            for s in sentences
        }
    c, g = keys(cand_sentences), keys(gold_sentences)
    return sum(len(c.get(sid, set()) & g[sid]) for sid in g)


# ---------------------------------------------------------------------------
# Experiment driver
# ---------------------------------------------------------------------------

def run_domain(exp_dir: Path) -> Dict[str, Any]:
    """Computes transformation and downstream rows for one domain from its frozen artifacts."""
    manifest = verify_frozen(exp_dir)
    sessions = load_candidate_sessions(exp_dir / "candidates")
    b0 = load_json(exp_dir / manifest["b0_file"])
    b1 = load_json(exp_dir / manifest["b1_file"])
    gold = sentence_sets(b1["sentences"])
    b0_sets = sentence_sets(b0["sentences"])

    # Consistency guards: every session must hold the same reference, and B0 must equal the union.
    for name, sess in sessions.items():
        if sentence_sets(sess["versions"][-1]["sentences"]) != gold:
            raise RuntimeError(f"Final version of {name} differs from frozen B1")
    if sentence_sets(build_union(sessions)) != b0_sets:
        raise RuntimeError("Frozen B0 is not the normalized union of the current candidate files")

    gold_sentences = b1["sentences"]
    cand_by_model = {name: sentence_sets(sess["versions"][0]["sentences"]) for name, sess in sessions.items()}

    transformation = []
    downstream = []
    for name, sess in sessions.items():
        cand = cand_by_model[name]
        transformation.append({
            "source": name,
            **alignment(cand, gold),
            "split_insensitive_exact": split_insensitive_overlap(sess["versions"][0]["sentences"], gold_sentences),
        })
        # B0 contains every candidate of every model, so P(B0) = 1 and F1(B0) depends only on |Ci|/|B0|.
        c0 = sentence_counts(cand, b0_sets)
        c1 = sentence_counts(cand, gold)
        # Leave-one-out pool: the union of the OTHER three models, a pooled reference the system did not contribute to.
        loo = {sid: set().union(*(cand_by_model[o].get(sid, set()) for o in cand_by_model if o != name)) for sid in gold}
        cl = sentence_counts(cand, loo)
        p0, r0, f0 = micro_prf(c0)
        p1, r1, f1 = micro_prf(c1)
        pl, rl, fl = micro_prf(cl)
        lo, hi = paired_bootstrap_delta_f1(c0, c1)
        lo_l, hi_l = paired_bootstrap_delta_f1(cl, c1)
        downstream.append({
            "system": name,
            "n_candidates": sum(len(v) for v in cand.values()),
            "b0_p": p0, "b0_r": r0, "b0_f1": f0,
            "loo_p": pl, "loo_r": rl, "loo_f1": fl,
            "b1_p": p1, "b1_r": r1, "b1_f1": f1,
            "b1_tp": sum(c[0] for c in c1),
            "delta_f1": f1 - f0, "ci_lower": lo, "ci_upper": hi,
            "delta_f1_loo": f1 - fl, "ci_loo_lower": lo_l, "ci_loo_upper": hi_l,
        })
    transformation.append({
        "source": "B0 (four-model union)",
        **alignment(b0_sets, gold),
        "split_insensitive_exact": split_insensitive_overlap(b0["sentences"], gold_sentences),
    })

    return {
        "domain": manifest["domain"],
        "n_sentences": len(gold),
        "transformation": transformation,
        "downstream": downstream,
        "frozen_manifest": manifest,
    }
