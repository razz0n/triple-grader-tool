"""
openie_eval.py — OpenIE evaluation module.

Extracts (subject, predicate, object) triples from text using Stanford's
stanza dependency parser (Manning et al., 2014; Angeli et al., 2015),
then computes Precision, Recall, and F1 against a human-graded golden dataset.

Method
------
Triple extraction follows the linguistic-structure approach of Angeli et al.
(2015): for each verb in a dependency tree, collect its nominal subjects
(nsubj / nsubjpass) as the subject, the verb (plus auxiliaries / particles)
as the predicate, and its dependents (obj, dobj, iobj, obl, xcomp, ccomp,
prep+pobj) as the object.  Spans are collected by gathering the subtree of
each head token, excluding clausal markers, punctuation, and auxiliary verbs
already merged into the predicate.

References
----------
[26] G. Angeli, M. J. J. Premkumar, and C. D. Manning, "Leveraging linguistic
     structure for open domain information extraction," ACL 2015.
[27] C. D. Manning et al., "The Stanford CoreNLP natural language processing
     toolkit," ACL 2014.
Stanza (post-2020 Python library wrapping CoreNLP): Qi et al., EMNLP 2020.

Public API
----------
run_openie(sentences)                    → dict[sentence_id, list[triple_dict]]
compute_metrics(tp, n_gold, n_pred)      → dict with precision/recall/f1
evaluate_session(session, match_mode)    → full evaluation result dict
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Lazy-load stanza pipeline (downloads models on first use, ~300 MB)
# ---------------------------------------------------------------------------

_NLP: Optional[Any] = None

_PROCESSORS = "tokenize,pos,lemma,depparse"


def _get_nlp():
    global _NLP
    if _NLP is None:
        import stanza
        stanza.download("en", processors=_PROCESSORS, verbose=False)
        _NLP = stanza.Pipeline("en", processors=_PROCESSORS, verbose=False)
    return _NLP


# ---------------------------------------------------------------------------
# Dependency-based SVO triple extraction
# (implements the Angeli 2015 linguistic-structure approach)
# ---------------------------------------------------------------------------

# Subject dependency relations
_SUBJ_RELS = {"nsubj", "nsubjpass", "csubj", "csubjpass"}
# Object dependency relations
_OBJ_RELS  = {"obj", "dobj", "iobj", "obl", "xcomp", "ccomp"}
# Auxiliary / particle relations merged into predicate
_AUX_RELS  = {"aux", "auxpass", "neg", "compound:prt", "prt"}
# Relations to skip when collecting a span (do not descend)
_SKIP_RELS = {"punct", "cc", "mark", "expl"} | _AUX_RELS


def _collect_span(token, sent_tokens: list, exclude_ids: Set[int]) -> str:
    """
    Collect the surface span for a head token by gathering its dependency
    subtree (excluding punctuation, auxiliaries, and already-used tokens).
    Returns tokens sorted by their position in the sentence.
    """
    included = []
    stack = [token]
    while stack:
        tok = stack.pop()
        if tok.id in exclude_ids:
            continue
        if tok.deprel in _SKIP_RELS and tok.id != token.id:
            continue
        included.append(tok)
        for child in sent_tokens:
            if child.head == tok.id and child.id not in exclude_ids:
                stack.append(child)
    included.sort(key=lambda t: t.id)
    return " ".join(t.text for t in included).strip()


def _extract_triples_from_sentence(sentence) -> List[Dict[str, str]]:
    """Extract (subject, predicate, object) triples from one stanza sentence."""
    tokens = sentence.words
    # Index tokens by id for fast lookup
    by_id: Dict[int, Any] = {t.id: t for t in tokens}

    triples: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str]] = set()

    for tok in tokens:
        # Each verb (VERB / AUX at root or with a subject) is a predicate candidate
        if tok.upos not in ("VERB", "AUX"):
            continue

        # Find subjects of this verb
        subjects = [t for t in tokens if t.head == tok.id and t.deprel in _SUBJ_RELS]
        if not subjects:
            continue

        # Build predicate span: the verb + its auxiliaries / particles
        aux_ids = {
            t.id for t in tokens
            if t.head == tok.id and t.deprel in _AUX_RELS
        }
        pred_tokens = sorted(
            [tok] + [by_id[i] for i in aux_ids if i in by_id],
            key=lambda t: t.id
        )
        predicate = " ".join(t.text for t in pred_tokens)

        # Find objects of this verb
        objects = [t for t in tokens if t.head == tok.id and t.deprel in _OBJ_RELS]

        # Also handle prepositional objects (prep → pobj pattern in UD)
        prep_tokens = [t for t in tokens if t.head == tok.id and t.deprel in ("obl", "prep")]
        for prep in prep_tokens:
            pobj = [t for t in tokens if t.head == prep.id and t.deprel in ("pobj", "obj")]
            objects.extend(pobj)

        if not objects:
            # Use the whole verb complement if no direct object found
            complement = [
                t for t in tokens
                if t.head == tok.id and t.deprel not in _SUBJ_RELS | _AUX_RELS | {"punct", "cc", "mark"}
            ]
            objects = complement[:1]  # Take the first complement only

        exclude = {tok.id} | aux_ids

        for subj in subjects:
            subj_span = _collect_span(subj, tokens, exclude_ids=set())
            for obj in objects:
                obj_span = _collect_span(obj, tokens, exclude_ids=exclude)
                if not subj_span or not obj_span:
                    continue
                key = (subj_span.lower(), predicate.lower(), obj_span.lower())
                if key in seen:
                    continue
                seen.add(key)
                triples.append({
                    "subject":   subj_span,
                    "predicate": predicate,
                    "object":    obj_span,
                })

    return triples


# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------

_STOP = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with",
    "by", "from", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "that", "which", "who",
    "this", "these", "those", "it", "its", "and", "or", "but", "not",
}

_ONTOLOGY_ID_RE = re.compile(r"^(?P<base>[a-z][a-z0-9]*(?:_[a-z0-9]+)*)_(?P<idx>\d+)$")

# Canonical forms used during matching to reduce representation mismatch
# between ontology labels and surface OpenIE text.
_RELATION_ALIASES = {
    "is in": "in",
    "located in": "in",
    "part of": "in",
    "belongs to": "in",
    "has": "have",
    "had": "have",
    "contains": "have",
    "include": "have",
    "includes": "have",
    "is": "be",
    "are": "be",
    "was": "be",
    "were": "be",
    "been": "be",
    "being": "be",
    "name is": "be",
    "contribute to": "contribute",
    "contributes to": "contribute",
    "contributed to": "contribute",
    "is has importance": "importance",
    "has importance": "importance",
    "is has trend": "trend",
    "has trend": "trend",
}


def _normalise_entity(v: str) -> str:
    raw = re.sub(r"\s+", " ", str(v or "").strip().lower())
    raw = raw.replace("-", "_")

    m = _ONTOLOGY_ID_RE.fullmatch(raw)
    if m:
        raw = m.group("base")

    raw = raw.replace("_", " ").replace("/", " ")
    return re.sub(r"\s+", " ", raw).strip()


def _normalise_relation(v: str) -> str:
    raw = re.sub(r"\s+", " ", str(v or "").strip().lower())
    raw = raw.replace("_", " ").replace("/", " ")
    raw = re.sub(r"\s+", " ", raw).strip()
    return _RELATION_ALIASES.get(raw, raw)


def _normalise_triple(t: dict) -> Dict[str, str]:
    return {
        "subject": _normalise_entity(str(t.get("subject", ""))),
        "predicate": _normalise_relation(str(t.get("predicate", ""))),
        "object": _normalise_entity(str(t.get("object", ""))),
    }


def _tokenise(text: str) -> Set[str]:
    """Lower-case, split on non-alphanumerics, remove stop words."""
    tokens = set(re.split(r"\W+", text.lower()))
    tokens.discard("")
    return tokens - _STOP


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenise(a), _tokenise(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _triple_jaccard(t1: dict, t2: dict) -> float:
    """Average Jaccard over subject, predicate, object."""
    nt1 = _normalise_triple(t1)
    nt2 = _normalise_triple(t2)
    return (
        _jaccard(nt1["subject"], nt2["subject"])
        + _jaccard(nt1["predicate"], nt2["predicate"])
        + _jaccard(nt1["object"], nt2["object"])
    ) / 3.0


def _normalise(v: str) -> str:
    return re.sub(r"\s+", " ", v.strip().lower())


def _triple_key(t: dict) -> Tuple[str, str, str]:
    nt = _normalise_triple(t)
    return (
        _normalise(nt["subject"]),
        _normalise(nt["predicate"]),
        _normalise(nt["object"]),
    )


# ---------------------------------------------------------------------------
# OpenIE extraction (wraps the sentence-level extractor above)
# ---------------------------------------------------------------------------

def run_openie(sentences: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, str]]]:
    """
    Run dependency-based OpenIE over each sentence.

    Parameters
    ----------
    sentences : list of dicts with at least {"id": int, "text": str}

    Returns
    -------
    dict mapping sentence_id → list of {"subject", "predicate", "object"} dicts
    """
    nlp = _get_nlp()
    result: Dict[int, List[Dict[str, str]]] = {}

    for s in sentences:
        sid = s["id"]
        text = (s.get("text") or "").strip()
        if not text:
            result[sid] = []
            continue

        doc = nlp(text)
        triples: List[Dict[str, str]] = []
        for sentence in doc.sentences:
            triples.extend(_extract_triples_from_sentence(sentence))

        result[sid] = triples

    return result


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

_SOFT_THRESHOLD = 0.5  # Jaccard ≥ 0.5 counts as a match


def _exact_match(gold: List[dict], pred: List[dict]) -> Tuple[int, int, int]:
    """Returns (true_positives, len_gold, len_pred)."""
    gold_keys = [_triple_key(t) for t in gold]
    pred_keys = [_triple_key(t) for t in pred]
    gold_set = set(gold_keys)
    pred_set = set(pred_keys)
    tp = len(gold_set & pred_set)
    return tp, len(gold_keys), len(pred_keys)


def _soft_match(gold: List[dict], pred: List[dict]) -> Tuple[int, int, int]:
    """
    Greedy soft matching using average Jaccard ≥ _SOFT_THRESHOLD.
    Each gold triple can be matched at most once.
    """
    matched_gold = [False] * len(gold)
    tp = 0
    for p in pred:
        best_score = 0.0
        best_idx = -1
        for i, g in enumerate(gold):
            if matched_gold[i]:
                continue
            score = _triple_jaccard(g, p)
            if score > best_score:
                best_score = score
                best_idx = i
        if best_score >= _SOFT_THRESHOLD and best_idx >= 0:
            matched_gold[best_idx] = True
            tp += 1
    return tp, len(gold), len(pred)


def compute_metrics(tp: int, n_gold: int, n_pred: int) -> Dict[str, float]:
    precision = tp / n_pred if n_pred else 0.0
    recall    = tp / n_gold if n_gold else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "true_positives": tp,
        "n_gold":         n_gold,
        "n_pred":         n_pred,
        "precision":      round(precision, 4),
        "recall":         round(recall, 4),
        "f1":             round(f1, 4),
    }


# ---------------------------------------------------------------------------
# Full session evaluation
# ---------------------------------------------------------------------------

def evaluate_session(
    session: Dict[str, Any],
    match_mode: str = "soft",
) -> Dict[str, Any]:
    """
    Evaluate a graded session against OpenIE predictions.

    Parameters
    ----------
    session    : full graded session dict (from grading tool JSON export)
    match_mode : "exact" or "soft"

    Returns
    -------
    dict with keys:
      session_id, source_filename, match_mode,
      per_sentence: list of per-sentence result dicts,
      macro: macro-averaged P/R/F1 over all sentences
      micro: micro-averaged P/R/F1 (aggregate TP/gold/pred counts)
    """
    if match_mode not in ("exact", "soft"):
        raise ValueError(f"match_mode must be 'exact' or 'soft', got '{match_mode}'")

    sentences = session.get("sentences", [])

    # ── Build gold triples (only graded triples count) ───────────────────
    gold_by_sid: Dict[int, List[dict]] = {}
    for s in sentences:
        sid = s["id"]
        gold_by_sid[sid] = [
            t for t in s.get("triples", [])
            if t.get("grade") is not None
        ]

    # ── Run OpenIE ────────────────────────────────────────────────────────
    pred_by_sid = run_openie(sentences)

    # ── Compute per-sentence metrics ──────────────────────────────────────
    per_sentence = []
    total_tp = total_gold = total_pred = 0

    for s in sentences:
        sid = s["id"]
        gold = gold_by_sid[sid]
        pred = pred_by_sid.get(sid, [])

        if match_mode == "exact":
            tp, n_gold, n_pred = _exact_match(gold, pred)
        else:
            tp, n_gold, n_pred = _soft_match(gold, pred)

        metrics = compute_metrics(tp, n_gold, n_pred)
        total_tp   += tp
        total_gold += n_gold
        total_pred += n_pred

        per_sentence.append({
            "sentence_id":   sid,
            "sentence_text": s.get("text", ""),
            "gold_triples":  gold,
            "pred_triples":  pred,
            **metrics,
        })

    # ── Macro average (mean of per-sentence scores) ───────────────────────
    if per_sentence:
        macro = {
            "precision": round(sum(r["precision"] for r in per_sentence) / len(per_sentence), 4),
            "recall":    round(sum(r["recall"]    for r in per_sentence) / len(per_sentence), 4),
            "f1":        round(sum(r["f1"]        for r in per_sentence) / len(per_sentence), 4),
        }
    else:
        macro = {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # ── Micro average (aggregate counts) ─────────────────────────────────
    micro = compute_metrics(total_tp, total_gold, total_pred)

    return {
        "session_id":      session.get("session_id", ""),
        "source_filename": session.get("source_filename", ""),
        "match_mode":      match_mode,
        "per_sentence":    per_sentence,
        "macro":           macro,
        "micro":           micro,
    }
