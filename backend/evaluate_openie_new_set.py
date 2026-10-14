#!/usr/bin/env python3
"""
evaluate_openie_new_set.py

Purpose
-------
Evaluate OpenIE extracted triples against your `new_set.csv` gold triples.

This script handles the important mismatch in your project:
  1. OpenIE usually outputs surface triples: (subject text, relation text, object text)
  2. Your new_set.csv contains ontology/reified triples: (Code_001, has_action, usage_constraint_001)

So the script parses your block-style CSV, normalizes ontology IDs, optionally runs
Stanford CoreNLP OpenIE, and computes one-to-one Precision, Recall, and F1.

Recommended use
---------------
1) If you already have predictions:
   python evaluate_openie_new_set.py --gold_csv "new set.csv" --pred_csv predictions.csv --out_dir results

2) If you want to run Stanford CoreNLP OpenIE directly:
   python evaluate_openie_new_set.py --gold_csv "new set.csv" --extractor corenlp --out_dir results

Prediction CSV format, if using --pred_csv
------------------------------------------
Required columns:
  sentence_id, subject, predicate, object
Optional columns:
  sentence, confidence

Outputs
-------
  results/gold_parsed.csv
  results/predictions.csv
  results/per_sentence_results.csv
  results/matched_triples.csv
  results/evaluation_summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Triple:
    sentence_id: str
    subject: str
    predicate: str
    object: str
    sentence: str = ""
    confidence: float = 1.0
    source: str = ""
    row_id: str = ""


@dataclass
class MatchResult:
    sentence_id: str
    pred_subject: str
    pred_predicate: str
    pred_object: str
    gold_subject: str
    gold_predicate: str
    gold_object: str
    score: float
    match_type: str


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

# Keep negation words. Do NOT remove "not", because your domain depends on it.
STOP_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with",
    "by", "from", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "that", "which", "who",
    "this", "these", "those", "it", "its", "and", "or", "but"
}

WORD_ALIASES = {
    "comission": "commission",
    "algoirthm": "algorithm",
    "algorithim": "algorithm",
    "judgement": "judgment",
    "judgements": "judgments",
    "organisation": "organization",
    "organisations": "organizations",
    "seperate": "separate",
}

RELATION_ALIASES = {
    "has": "have",
    "have": "have",
    "contains": "have",
    "include": "have",
    "includes": "have",
    "is": "be",
    "are": "be",
    "was": "be",
    "were": "be",
    "is not": "not be",
    "are not": "not be",
    "was not": "not be",
    "were not": "not be",
    "is_not": "not be",
    "should_not_be": "should not be",
    "not_intended_for": "not intended for",
    "used_for": "used for",
    "can_be": "can be",
    "has_action": "action",
    "has action": "action",
    "has_constraint_type": "constraint type",
    "has constraint type": "constraint type",
    "targets": "target",
    "requires": "require",
    "prohibits": "prohibit",
    "domain": "domain",
    "range": "range",
}

# If gold predicate is one of these, the semantic relation often lives in the object.
# Example: (interpretation_001, has_action, separate_001) => relation/action is "separate".
OBJECT_AS_RELATION = {
    "action", "has action", "has_action", "impact", "has impact",
    "trend", "has trend", "importance", "has importance"
}

ID_SUFFIX_RE = re.compile(r"^(?P<base>[a-z][a-z0-9]*(?:_[a-z0-9]+)*?)_\d+$", re.I)
SEP_RE = re.compile(r"^=+$")


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def normalize_text(text: str) -> str:
    text = clean_cell(text).lower()
    text = text.replace("-", "_")

    # Remove ontology numeric suffix: Code_001 -> Code, usage_constraint_001 -> usage_constraint
    m = ID_SUFFIX_RE.match(text)
    if m:
        text = m.group("base")

    text = re.sub(r"[^a-z0-9_\s]", " ", text)
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()

    tokens = []
    for tok in text.split():
        tok = WORD_ALIASES.get(tok, tok)
        if tok.endswith("ies") and len(tok) > 4:
            tok = tok[:-3] + "y"
        elif tok.endswith("s") and len(tok) > 3 and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(tok)
    return " ".join(tokens)


def normalize_relation(text: str) -> str:
    raw = normalize_text(text)
    return RELATION_ALIASES.get(raw, raw)


def token_set(text: str) -> Set[str]:
    norm = normalize_text(text)
    return {t for t in norm.split() if t and t not in STOP_WORDS}


def canonical_parts(t: Triple) -> Tuple[str, str, str]:
    return (
        normalize_text(t.subject),
        normalize_relation(t.predicate),
        normalize_text(t.object),
    )


def projection(t: Triple) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Turn both OpenIE surface triples and ontology-style triples into comparable tokens.
    This is not a perfect semantic evaluator, but it is much fairer than raw string equality.
    """
    s, p, o = canonical_parts(t)
    subj = token_set(s)
    pred = token_set(p)
    obj = token_set(o)

    if p in OBJECT_AS_RELATION and obj:
        # ontology reification pattern: subject --has_action--> separate_001
        # Treat object label as the action/relation.
        pred = set(obj)
        obj = set()

    return subj, pred, obj


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def triple_similarity(gold: Triple, pred: Triple) -> float:
    """Average field similarity after normalization/projection."""
    gs, gp, go = projection(gold)
    ps, pp, po = projection(pred)

    scores = [jaccard(gs, ps), jaccard(gp, pp)]
    # Only score object if both sides have a real object after projection.
    if go or po:
        scores.append(jaccard(go, po))
    return sum(scores) / len(scores)


def canonical_key(t: Triple) -> Tuple[str, str, str]:
    s, p, o = canonical_parts(t)
    return (s, p, o)


# ---------------------------------------------------------------------------
# Parse your block-style new_set CSV
# ---------------------------------------------------------------------------

def looks_like_sentence(text: str) -> bool:
    text = clean_cell(text)
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith(("v2 -", "since ", "here,", "we can", "this ")):
        return False
    return len(text.split()) >= 5 and any(p in text for p in ".?!")


def valid_triple_cells(s: str, p: str, o: str) -> bool:
    if not (s and p and o):
        return False
    if SEP_RE.match(s):
        return False
    if looks_like_sentence(s):
        return False
    return True


def parse_new_set_csv(path: str, sentence_col: int = 7) -> Tuple[List[Triple], Dict[str, str]]:
    """
    Reads your CSV as raw rows, because the file is not a standard table.
    Columns 0,1,2 are interpreted as subject,predicate,object.
    Column 7 is usually the sentence or a note.
    Separator rows made of ===== start a new block.
    """
    rows: List[List[str]] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append([clean_cell(x) for x in row])

    triples: List[Triple] = []
    sentence_by_id: Dict[str, str] = {}
    current_sid = 1
    current_sentence = ""
    last_real_sentence = ""
    row_in_block = 0

    def sid() -> str:
        return f"s{current_sid:04d}"

    for ridx, row in enumerate(rows):
        while len(row) <= max(2, sentence_col):
            row.append("")

        c0, c1, c2 = row[0], row[1], row[2]
        sentence_candidate = row[sentence_col]

        # Separator row starts a new sentence/block.
        if SEP_RE.match(c0):
            if current_sentence:
                sentence_by_id[sid()] = current_sentence
            current_sid += 1
            current_sentence = ""
            row_in_block = 0
            continue

        # Blank row does not necessarily start a new block because your CSV has extra blanks.
        if not any(row):
            continue

        if looks_like_sentence(sentence_candidate):
            current_sentence = sentence_candidate
            last_real_sentence = sentence_candidate

        # Some v2 blocks have a note instead of repeating the sentence. Reuse previous sentence.
        if not current_sentence and last_real_sentence:
            current_sentence = last_real_sentence

        if valid_triple_cells(c0, c1, c2):
            triples.append(
                Triple(
                    sentence_id=sid(),
                    subject=c0,
                    predicate=c1,
                    object=c2,
                    sentence=current_sentence,
                    confidence=1.0,
                    source="gold_new_set",
                    row_id=str(ridx + 1),
                )
            )
            if current_sentence:
                sentence_by_id[sid()] = current_sentence
            row_in_block += 1

    # final sentence
    if current_sentence:
        sentence_by_id[sid()] = current_sentence

    return dedupe_triples(triples), sentence_by_id


# ---------------------------------------------------------------------------
# Load prediction CSV or run Stanford CoreNLP OpenIE
# ---------------------------------------------------------------------------

def load_prediction_csv(path: str) -> List[Triple]:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"sentence_id", "subject", "predicate", "object"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Prediction CSV is missing columns: {sorted(missing)}")

    triples: List[Triple] = []
    for i, row in df.iterrows():
        triples.append(
            Triple(
                sentence_id=clean_cell(row.get("sentence_id")),
                subject=clean_cell(row.get("subject")),
                predicate=clean_cell(row.get("predicate")),
                object=clean_cell(row.get("object")),
                sentence=clean_cell(row.get("sentence", "")),
                confidence=float(row.get("confidence", 1.0) or 1.0),
                source="prediction_csv",
                row_id=str(i + 1),
            )
        )
    return dedupe_triples([t for t in triples if t.subject and t.predicate and t.object])


def run_corenlp_openie(sentence_by_id: Dict[str, str]) -> List[Triple]:
    """
    Runs actual Stanford CoreNLP OpenIE through stanza's CoreNLPClient.

    Requirements:
      pip install stanza
      Java installed
      Stanford CoreNLP installed or downloadable by stanza

    Important: this is the real OpenIE annotator path, unlike a plain dependency parser.
    """
    from stanza.server import CoreNLPClient

    props = {
        "annotators": "tokenize,ssplit,pos,lemma,depparse,natlog,openie",
        "openie.format": "default",
        "openie.triple.strict": "true",
        "openie.resolve_coref": "false",
    }

    predictions: List[Triple] = []
    with CoreNLPClient(
        annotators=["tokenize", "ssplit", "pos", "lemma", "depparse", "natlog", "openie"],
        timeout=120000,
        memory="6G",
        be_quiet=True,
    ) as client:
        for sid, sent in sentence_by_id.items():
            if not sent:
                continue
            ann = client.annotate(sent, properties=props, output_format="json")
            for s in ann.get("sentences", []):
                for ext in s.get("openie", []):
                    predictions.append(
                        Triple(
                            sentence_id=sid,
                            subject=clean_cell(ext.get("subject", "")),
                            predicate=clean_cell(ext.get("relation", "")),
                            object=clean_cell(ext.get("object", "")),
                            sentence=sent,
                            confidence=float(ext.get("confidence", 1.0) or 1.0),
                            source="stanford_corenlp_openie",
                        )
                    )
    return dedupe_triples([t for t in predictions if t.subject and t.predicate and t.object])


_STANZA_NLP = None


def _get_stanza_nlp():
    global _STANZA_NLP
    if _STANZA_NLP is None:
        import stanza
        stanza.download("en", processors="tokenize,pos,lemma,depparse", verbose=False)
        _STANZA_NLP = stanza.Pipeline("en", processors="tokenize,pos,lemma,depparse", verbose=False)
    return _STANZA_NLP


def run_stanza_dependency_baseline(sentence_by_id: Dict[str, str]) -> List[Triple]:
    """
    Dependency-based triple extraction baseline using stanza.
    Handles standard SVO, copular constructions, passive voice,
    and complement/adverbial fallbacks to maximise recall.
    """
    nlp = _get_stanza_nlp()

    subj_rels = {"nsubj", "nsubj:pass", "csubj", "csubj:pass", "nsubjpass", "csubjpass"}
    obj_rels = {"obj", "iobj", "obl", "xcomp", "ccomp", "dobj", "attr"}
    aux_rels = {"aux", "aux:pass", "auxpass", "neg", "compound:prt", "prt"}
    # Fallback complement/modifier relations for when no standard object exists
    complement_rels = {"acomp", "advmod", "obl", "obl:npmod", "obl:tmod", "advcl", "xcomp", "ccomp", "nmod"}
    skip_rels = {"punct", "cc", "mark", "det"}

    def span(head, words, exclude: Set[int]) -> str:
        stack = [head]
        got = []
        while stack:
            tok = stack.pop()
            if tok.id in exclude:
                continue
            got.append(tok)
            for child in words:
                if child.head == tok.id and child.id not in exclude and child.deprel not in {"punct", "cc"}:
                    stack.append(child)
        got.sort(key=lambda x: x.id)
        return " ".join(x.text for x in got).strip()

    def _extract_triples_from_stanza_sentence(words, by_id, sid, sent):
        """Extract triples from a single stanza sentence using multiple strategies."""
        triples: List[Triple] = []
        seen: Set[Tuple[str, str, str]] = set()

        def _add(sub_span, pred_text, obj_span):
            if not sub_span or not pred_text or not obj_span:
                return
            key = (sub_span.lower().strip(), pred_text.lower().strip(), obj_span.lower().strip())
            if key in seen:
                return
            seen.add(key)
            triples.append(Triple(sid, sub_span, pred_text, obj_span, sent, 1.0, "stanza_dependency_baseline"))

        for tok in words:
            # --- Strategy 1: Standard SVO (verb with subject + object) ---
            if tok.upos in {"VERB", "AUX"}:
                subjects = [w for w in words if w.head == tok.id and w.deprel in subj_rels]
                objects = [w for w in words if w.head == tok.id and w.deprel in obj_rels]
                aux_ids = {w.id for w in words if w.head == tok.id and w.deprel in aux_rels}
                pred_words = sorted([tok] + [by_id[i] for i in aux_ids if i in by_id], key=lambda x: x.id)
                pred_text = " ".join(w.text for w in pred_words)

                if subjects and objects:
                    for sub in subjects:
                        sub_span = span(sub, words, set())
                        for obj in objects:
                            obj_span = span(obj, words, {tok.id} | aux_ids)
                            _add(sub_span, pred_text, obj_span)

                # --- Strategy 2: Subject + fallback complement (no direct object) ---
                elif subjects and not objects:
                    fallback_objs = [w for w in words if w.head == tok.id and w.deprel in complement_rels]
                    if fallback_objs:
                        for sub in subjects:
                            sub_span = span(sub, words, set())
                            for obj in fallback_objs:
                                obj_span = span(obj, words, {tok.id} | aux_ids)
                                _add(sub_span, pred_text, obj_span)
                    else:
                        # Last resort: use any remaining non-skip dependent as object
                        remaining = [w for w in words
                                     if w.head == tok.id
                                     and w.deprel not in subj_rels
                                     and w.deprel not in aux_rels
                                     and w.deprel not in skip_rels
                                     and w.deprel != "cop"]
                        if subjects and remaining:
                            for sub in subjects:
                                sub_span = span(sub, words, set())
                                for obj in remaining[:2]:  # limit explosion
                                    obj_span = span(obj, words, {tok.id} | aux_ids)
                                    _add(sub_span, pred_text, obj_span)

            # --- Strategy 3: Copular constructions ---
            # In UD, copular "X is Y" parses as: Y <-nsubj- X, Y <-cop- is
            # The head is the predicate complement (ADJ/NOUN), not the verb
            if tok.upos in {"ADJ", "NOUN", "PROPN", "PRON", "NUM"}:
                cop_words = [w for w in words if w.head == tok.id and w.deprel == "cop"]
                cop_subjects = [w for w in words if w.head == tok.id and w.deprel in subj_rels]
                if cop_words and cop_subjects:
                    cop_aux = [w for w in words if w.head == tok.id and w.deprel in aux_rels]
                    cop_all = sorted(cop_words + cop_aux, key=lambda w: w.id)
                    pred_text = " ".join(w.text for w in cop_all)
                    cop_ids = {w.id for w in cop_all}
                    obj_span = span(tok, words, cop_ids | {w.id for w in cop_subjects})
                    for sub in cop_subjects:
                        sub_span = span(sub, words, set())
                        _add(sub_span, pred_text, obj_span)

        return triples

    preds: List[Triple] = []
    for sid, sent in sentence_by_id.items():
        if not sent or not sent.strip():
            continue
        doc = nlp(sent)
        for sentence in doc.sentences:
            words = sentence.words
            by_id = {w.id: w for w in words}
            triples = _extract_triples_from_stanza_sentence(words, by_id, sid, sent)
            preds.extend(triples)
    return dedupe_triples(preds)


# ---------------------------------------------------------------------------
# Matching and metrics
# ---------------------------------------------------------------------------

def dedupe_triples(triples: Sequence[Triple]) -> List[Triple]:
    seen = set()
    out = []
    for t in triples:
        key = (t.sentence_id, canonical_key(t))
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def group_by_sentence(triples: Sequence[Triple]) -> Dict[str, List[Triple]]:
    grouped: Dict[str, List[Triple]] = {}
    for t in triples:
        grouped.setdefault(t.sentence_id, []).append(t)
    return grouped


def greedy_match(gold: List[Triple], pred: List[Triple], threshold: float) -> Tuple[int, List[MatchResult]]:
    """
    One-to-one greedy matching.
    Each predicted triple can match at most one gold triple.
    Each gold triple can be matched at most once.
    """
    candidates: List[Tuple[float, int, int]] = []
    for pi, p in enumerate(pred):
        for gi, g in enumerate(gold):
            score = triple_similarity(g, p)
            if score >= threshold:
                candidates.append((score, pi, gi))

    candidates.sort(reverse=True, key=lambda x: x[0])
    used_pred: Set[int] = set()
    used_gold: Set[int] = set()
    matches: List[MatchResult] = []

    for score, pi, gi in candidates:
        if pi in used_pred or gi in used_gold:
            continue
        used_pred.add(pi)
        used_gold.add(gi)
        p = pred[pi]
        g = gold[gi]
        matches.append(
            MatchResult(
                sentence_id=p.sentence_id,
                pred_subject=p.subject,
                pred_predicate=p.predicate,
                pred_object=p.object,
                gold_subject=g.subject,
                gold_predicate=g.predicate,
                gold_object=g.object,
                score=round(score, 4),
                match_type="soft" if score < 1 else "exact_or_normalized_exact",
            )
        )

    return len(matches), matches


def compute_metrics(tp: int, n_gold: int, n_pred: int) -> Dict[str, Any]:
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gold if n_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positives": tp,
        "n_gold": n_gold,
        "n_pred": n_pred,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate(gold: List[Triple], pred: List[Triple], threshold: float, all_sentence_ids: Optional[List[str]] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[MatchResult]]:
    gold_by_sid = group_by_sentence(dedupe_triples(gold))
    pred_by_sid = group_by_sentence(dedupe_triples(pred))
    # Use explicit sentence list if provided so every session sentence appears in results
    if all_sentence_ids is not None:
        all_sids = list(dict.fromkeys(all_sentence_ids))  # preserve order, dedupe
        # Also include any IDs that are only in gold/pred (shouldn't happen, but safety)
        extra = sorted((set(gold_by_sid) | set(pred_by_sid)) - set(all_sids))
        all_sids.extend(extra)
    else:
        all_sids = sorted(set(gold_by_sid) | set(pred_by_sid))

    per_sentence: List[Dict[str, Any]] = []
    all_matches: List[MatchResult] = []
    total_tp = total_gold = total_pred = 0

    for sid in all_sids:
        g = gold_by_sid.get(sid, [])
        p = pred_by_sid.get(sid, [])
        tp, matches = greedy_match(g, p, threshold)
        m = compute_metrics(tp, len(g), len(p))
        per_sentence.append({"sentence_id": sid, **m})
        all_matches.extend(matches)
        total_tp += tp
        total_gold += len(g)
        total_pred += len(p)

    micro = compute_metrics(total_tp, total_gold, total_pred)
    # For macro, only average over sentences that have at least one gold or pred triple
    active_sentences = [x for x in per_sentence if x["n_gold"] > 0 or x["n_pred"] > 0]
    if active_sentences:
        macro = {
            "precision": round(sum(x["precision"] for x in active_sentences) / len(active_sentences), 4),
            "recall": round(sum(x["recall"] for x in active_sentences) / len(active_sentences), 4),
            "f1": round(sum(x["f1"] for x in active_sentences) / len(active_sentences), 4),
        }
    else:
        macro = {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    summary = {
        "match_threshold": threshold,
        "micro": micro,
        "macro": macro,
        "note": "Micro is the main score. Macro is the average of per-sentence scores.",
    }
    return summary, per_sentence, all_matches


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def triples_to_frame(triples: Sequence[Triple]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in triples])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold_csv", required=True, help="Path to your new_set.csv file")
    parser.add_argument("--pred_csv", default="", help="Optional prediction CSV with sentence_id,subject,predicate,object")
    parser.add_argument("--extractor", choices=["none", "corenlp", "stanza_baseline"], default="none")
    parser.add_argument("--out_dir", default="openie_eval_results")
    parser.add_argument("--sentence_col", type=int, default=7)
    parser.add_argument("--threshold", type=float, default=0.55, help="Soft match threshold, usually 0.50-0.70")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gold, sentence_by_id = parse_new_set_csv(args.gold_csv, sentence_col=args.sentence_col)

    if args.pred_csv:
        pred = load_prediction_csv(args.pred_csv)
    elif args.extractor == "corenlp":
        pred = run_corenlp_openie(sentence_by_id)
    elif args.extractor == "stanza_baseline":
        pred = run_stanza_dependency_baseline(sentence_by_id)
    else:
        raise ValueError("Provide --pred_csv or choose --extractor corenlp/stanza_baseline")

    summary, per_sentence, matches = evaluate(gold, pred, args.threshold)

    triples_to_frame(gold).to_csv(out_dir / "gold_parsed.csv", index=False)
    triples_to_frame(pred).to_csv(out_dir / "predictions.csv", index=False)
    pd.DataFrame(per_sentence).to_csv(out_dir / "per_sentence_results.csv", index=False)
    pd.DataFrame([asdict(m) for m in matches]).to_csv(out_dir / "matched_triples.csv", index=False)

    with open(out_dir / "evaluation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nSaved files in: {out_dir.resolve()}")


if __name__ == "__main__":
    main()