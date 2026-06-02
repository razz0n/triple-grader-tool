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
evaluate_session(session, match_mode, gold_source) → full evaluation result dict
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Import the new evaluation logic
from evaluate_openie_new_set import Triple, MatchResult, parse_new_set_csv, run_corenlp_openie, run_stanza_dependency_baseline, evaluate

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


def _collect_span(
    token,
    sent_tokens: list,
    exclude_ids: Set[int],
    exclude_conj: bool = False,
) -> str:
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
        if exclude_conj and tok.deprel == "conj" and tok.id != token.id:
            continue
        included.append(tok)
        for child in sent_tokens:
            if child.head == tok.id and child.id not in exclude_ids:
                stack.append(child)
    included.sort(key=lambda t: t.id)
    return " ".join(t.text for t in included).strip()


def _collect_subtree_ids(token, sent_tokens: list, exclude_ids: Set[int]) -> Set[int]:
    """Collect token ids in a dependency subtree using the same skip rules as _collect_span."""
    ids: Set[int] = set()
    stack = [token]
    while stack:
        tok = stack.pop()
        if tok.id in ids or tok.id in exclude_ids:
            continue
        if tok.deprel in _SKIP_RELS and tok.id != token.id:
            continue
        ids.add(tok.id)
        for child in sent_tokens:
            if child.head == tok.id and child.id not in ids and child.id not in exclude_ids:
                stack.append(child)
    return ids


def _expand_coordinated_object_spans(token, sent_tokens: list, exclude_ids: Set[int]) -> List[str]:
    """
    Expand coordinated object lists into separate spans.

    Example:
      "... role in commerce, industry, government ..."
    becomes separate object spans:
      "commerce", "industry", "government", ...
    """
    base_span = _collect_span(token, sent_tokens, exclude_ids=exclude_ids)
    subtree_ids = _collect_subtree_ids(token, sent_tokens, exclude_ids=exclude_ids)

    best_cluster: List[Any] = []
    for head in sent_tokens:
        if head.id not in subtree_ids:
            continue
        conjs = [
            child for child in sent_tokens
            if child.id in subtree_ids and child.head == head.id and child.deprel == "conj"
        ]
        if len(conjs) + 1 > len(best_cluster):
            best_cluster = [head] + conjs

    if len(best_cluster) < 2:
        return [base_span] if base_span else []

    spans: List[str] = []
    for item in sorted(best_cluster, key=lambda t: t.id):
        span = _collect_span(
            item,
            sent_tokens,
            exclude_ids=exclude_ids,
            exclude_conj=True,
        )
        if span and span not in spans:
            spans.append(span)
    return spans or ([base_span] if base_span else [])


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
                obj_spans = _expand_coordinated_object_spans(obj, tokens, exclude_ids=exclude)
                for obj_span in obj_spans:
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

    # Ensure that the triples meet the required standards
    # Filter out triples with empty subject, predicate, or object
    filtered_triples = [
        triple for triple in triples
        if triple["subject"] and triple["predicate"] and triple["object"]
    ]

    return filtered_triples


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

# Common misspellings and spelling variants observed in ontology datasets.
_WORD_ALIASES = {
    "algoirthm": "algorithm",
    "algorithim": "algorithm",
    "comission": "commission",
    "judgement": "judgment",
    "judgements": "judgments",
    "organisation": "organization",
    "organisations": "organizations",
}

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
    "requires": "require",
    "should influence": "influence",
    "shall maintain": "maintain",
}

# Ontology predicates where the object often carries the semantic action/relation.
_PREDICATE_OBJECT_RELATIONS = {
    "has action",
    "has impact",
    "impact",
    "has trend",
    "trend",
    "has importance",
    "importance",
}


def _apply_word_aliases(text: str) -> str:
    parts = text.split()
    return " ".join(_WORD_ALIASES.get(p, p) for p in parts)


def _singularize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        return token[:-1]
    return token


def _normalise_entity(v: str) -> str:
    raw = re.sub(r"\s+", " ", str(v or "").strip().lower())
    raw = raw.replace("-", "_")

    m = _ONTOLOGY_ID_RE.fullmatch(raw)
    if m:
        raw = m.group("base")

    raw = re.sub(r"[^a-z0-9_/\s]", " ", raw)
    raw = raw.replace("_", " ").replace("/", " ")
    raw = _apply_word_aliases(raw)
    return re.sub(r"\s+", " ", raw).strip()


def _normalise_relation(v: str) -> str:
    raw = re.sub(r"\s+", " ", str(v or "").strip().lower())
    raw = re.sub(r"[^a-z0-9_/\s]", " ", raw)
    raw = raw.replace("_", " ").replace("/", " ")
    raw = _apply_word_aliases(raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return _RELATION_ALIASES.get(raw, raw)


def _normalise_triple(t: dict) -> Dict[str, str]:
    return {
        "subject": _normalise_entity(str(t.get("subject", ""))),
        "predicate": _normalise_relation(str(t.get("predicate", ""))),
        "object": _normalise_entity(str(t.get("object", ""))),
    }


def _tokenise_projection(text: str) -> Set[str]:
    cleaned = _apply_word_aliases(re.sub(r"[^a-z0-9\s]", " ", text.lower()))
    tokens = set()
    for raw in re.split(r"\s+", cleaned):
        if not raw:
            continue
        tok = _singularize_token(raw)
        if tok and tok not in _STOP:
            tokens.add(tok)
    return tokens


def _project_triple_tokens(t: dict) -> Dict[str, Set[str]]:
    nt = _normalise_triple(t)
    subj = _tokenise_projection(nt["subject"])
    pred = _tokenise_projection(nt["predicate"])
    obj = _tokenise_projection(nt["object"])

    edge = set(pred)
    tail = set(obj)

    if nt["predicate"] in _PREDICATE_OBJECT_RELATIONS and obj:
        edge = set(obj)
        tail = set()

    return {"subj": subj, "edge": edge, "tail": tail}


def _set_jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _projected_triple_score(t1: dict, t2: dict) -> float:
    p1 = _project_triple_tokens(t1)
    p2 = _project_triple_tokens(t2)

    parts = [
        _set_jaccard(p1["subj"], p2["subj"]),
        _set_jaccard(p1["edge"], p2["edge"]),
    ]
    if p1["tail"] and p2["tail"]:
        parts.append(_set_jaccard(p1["tail"], p2["tail"]))

    return sum(parts) / len(parts)


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
    base = (
        _jaccard(nt1["subject"], nt2["subject"])
        + _jaccard(nt1["predicate"], nt2["predicate"])
        + _jaccard(nt1["object"], nt2["object"])
    ) / 3.0
    projected = _projected_triple_score(nt1, nt2)
    return max(base, projected)


def _normalise(v: str) -> str:
    return re.sub(r"\s+", " ", v.strip().lower())


def _triple_key(t: dict) -> Tuple[str, str, str]:
    nt = _normalise_triple(t)
    return (
        _normalise(nt["subject"]),
        _normalise(nt["predicate"]),
        _normalise(nt["object"]),
    )


def _triple_key_variants(t: dict) -> Set[Tuple[str, str, str]]:
    base = _triple_key(t)
    proj = _project_triple_tokens(t)
    projected = (
        " ".join(sorted(proj["subj"])),
        " ".join(sorted(proj["edge"])),
        " ".join(sorted(proj["tail"])),
    )
    if projected == base:
        return {base}
    return {base, projected}


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
    gold_variants = [_triple_key_variants(t) for t in gold]
    matched_gold = [False] * len(gold)
    tp = 0

    # Skip duplicate predicted triples to avoid inflating matching attempts.
    seen_pred = set()
    unique_pred_variants: List[Set[Tuple[str, str, str]]] = []
    for p in pred:
        variants = _triple_key_variants(p)
        key = tuple(sorted(variants))
        if key in seen_pred:
            continue
        seen_pred.add(key)
        unique_pred_variants.append(variants)

    for p_vars in unique_pred_variants:
        for idx, g_vars in enumerate(gold_variants):
            if matched_gold[idx]:
                continue
            if p_vars & g_vars:
                matched_gold[idx] = True
                tp += 1
                break

    return tp, len(gold), len(pred)


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
    gold_source: str = "graded_only",
) -> Dict[str, Any]:
    """
    Evaluate a graded session against OpenIE predictions.

    Produces two evaluation sections:
      1. openie_evaluation — stanza-extracted triples vs gold (the OpenIE benchmark)
      2. standard_evaluation — normal F1/Precision/Recall using exact/soft match

    Parameters
    ----------
    session    : full graded session dict (from grading tool JSON export)
    match_mode : "exact" or "soft"
    gold_source: "graded_only" (default) or "all"

    Returns
    -------
    dict with keys:
      session_id, source_filename, match_mode, gold_source,
      per_sentence, macro, micro  (primary OpenIE results),
      openie_evaluation, standard_evaluation  (structured dual results)
    """
    if match_mode not in ("exact", "soft"):
        raise ValueError(f"match_mode must be 'exact' or 'soft', got '{match_mode}'")
    if gold_source not in ("graded_only", "all"):
        raise ValueError(f"gold_source must be 'graded_only' or 'all', got '{gold_source}'")

    sentences = session.get("sentences", [])
    print(f"[evaluate_session] Total sentences in session: {len(sentences)}")

    # ── Build gold triples and sentence text map ──────────────────────────
    gold_triples: List[Triple] = []
    gold_triples_all: List[Triple] = []  # always includes all triples (for standard eval)
    sentence_by_id: Dict[str, str] = {}
    all_sentence_ids: List[str] = []

    for s in sentences:
        sid = str(s["id"])
        text = (s.get("text") or "").strip()
        sentence_by_id[sid] = text
        all_sentence_ids.append(sid)

        all_triples = s.get("triples", [])
        graded_triples = [t for t in all_triples if t.get("grade") is not None]

        # Select gold triples based on gold_source
        if gold_source == "graded_only":
            selected = graded_triples
        else:
            selected = all_triples

        for t in selected:
            gold_triples.append(
                Triple(
                    sentence_id=sid,
                    subject=t.get("subject", ""),
                    predicate=t.get("predicate", ""),
                    object=t.get("object", ""),
                    sentence=text,
                    confidence=1.0,
                    source="gold_session",
                    row_id=str(t.get("id", "")),
                )
            )

        # Always build full gold set for standard evaluation
        for t in all_triples:
            gold_triples_all.append(
                Triple(
                    sentence_id=sid,
                    subject=t.get("subject", ""),
                    predicate=t.get("predicate", ""),
                    object=t.get("object", ""),
                    sentence=text,
                    confidence=1.0,
                    source="gold_session_all",
                    row_id=str(t.get("id", "")),
                )
            )

    print(f"[evaluate_session] Gold triples ({gold_source}): {len(gold_triples)}")
    print(f"[evaluate_session] Sentences with text: {sum(1 for t in sentence_by_id.values() if t)}")

    # ── Run OpenIE extraction ─────────────────────────────────────────────
    pred_triples = run_stanza_dependency_baseline(sentence_by_id)
    print(f"[evaluate_session] Predicted triples from stanza: {len(pred_triples)}")
    pred_sids = set(t.sentence_id for t in pred_triples)
    print(f"[evaluate_session] Sentences with predictions: {len(pred_sids)} / {len(all_sentence_ids)}")

    # ── OpenIE evaluation (primary) ───────────────────────────────────────
    openie_summary, openie_per_sentence, openie_matches = evaluate(
        gold_triples, pred_triples, threshold=0.55, all_sentence_ids=all_sentence_ids
    )

    # ── Standard evaluation (exact + soft matching of gold vs gold) ───────
    # Standard evaluation: compare all session triples against themselves
    # using the exact/soft matching logic from the original _exact_match/_soft_match
    threshold_standard = 0.50 if match_mode == "soft" else 1.0
    std_summary, std_per_sentence, std_matches = evaluate(
        gold_triples, pred_triples, threshold=threshold_standard, all_sentence_ids=all_sentence_ids
    )

    # ── Build per-sentence result dicts with full detail ──────────────────
    def _build_per_sentence_results(eval_per_sentence, gold_list, pred_list):
        results = []
        for result in eval_per_sentence:
            sid_str = str(result["sentence_id"])

            # Parse sentence_id back to int for frontend display
            try:
                sid_int = int(sid_str)
            except ValueError:
                # Handle 's0001' format from CSV parser
                if sid_str.startswith("s"):
                    try:
                        sid_int = int(sid_str[1:])
                    except ValueError:
                        sid_int = 0
                else:
                    sid_int = 0

            results.append({
                "sentence_id": sid_int,
                "sentence_text": sentence_by_id.get(sid_str, ""),
                "gold_triples": [
                    {"subject": t.subject, "predicate": t.predicate, "object": t.object}
                    for t in gold_list if t.sentence_id == sid_str
                ],
                "pred_triples": [
                    {"subject": t.subject, "predicate": t.predicate, "object": t.object}
                    for t in pred_list if t.sentence_id == sid_str
                ],
                **result,
            })
        return results

    openie_results = _build_per_sentence_results(openie_per_sentence, gold_triples, pred_triples)
    standard_results = _build_per_sentence_results(std_per_sentence, gold_triples, pred_triples)

    # ── Sentence review metadata (for the review page) ────────────────────
    sentence_review = []
    for s in sentences:
        sid = str(s["id"])
        all_triples = s.get("triples", [])
        graded_count = sum(1 for t in all_triples if t.get("grade") is not None)
        pred_count = sum(1 for t in pred_triples if t.sentence_id == sid)
        sentence_review.append({
            "sentence_id": s["id"],
            "text": (s.get("text") or "").strip(),
            "total_triples": len(all_triples),
            "graded_triples": graded_count,
            "gold_triples_used": sum(1 for t in gold_triples if t.sentence_id == sid),
            "predicted_triples": pred_count,
            "has_text": bool((s.get("text") or "").strip()),
        })

    return {
        "session_id": session.get("session_id", ""),
        "source_filename": session.get("source_filename", ""),
        "match_mode": match_mode,
        "gold_source": gold_source,
        # Primary results (backward compatible — same as openie_evaluation)
        "per_sentence": openie_results,
        "macro": openie_summary["macro"],
        "micro": openie_summary["micro"],
        # Dual evaluation sections
        "openie_evaluation": {
            "per_sentence": openie_results,
            "macro": openie_summary["macro"],
            "micro": openie_summary["micro"],
            "threshold": 0.55,
            "description": "OpenIE Evaluation: Stanza-extracted triples vs gold standard",
        },
        "standard_evaluation": {
            "per_sentence": standard_results,
            "macro": std_summary["macro"],
            "micro": std_summary["micro"],
            "threshold": threshold_standard,
            "description": f"Standard F1/Precision/Recall ({match_mode} match)",
        },
        # Review metadata
        "sentence_review": sentence_review,
        "total_sentences": len(sentences),
        "sentences_with_predictions": len(pred_sids),
        "total_gold_triples": len(gold_triples),
        "total_pred_triples": len(pred_triples),
    }
