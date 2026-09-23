"""
adjudicated_gold.py — Authoritative Adjudicated Gold Set Definition.
Conforms strictly to Section 2.1 of the Triple Grader Evaluation Plan Specification.
"""

from typing import Any, Dict, List


def include_in_adjudicated_gold(triple: Dict[str, Any]) -> bool:
    """
    Centralized policy for membership in the adjudicated gold set:
    - For new suggestions: must be explicitly approved (status == "approved")
    - For original triples: must not be marked for removal and not superseded
    """
    if triple.get("is_new_suggestion") or triple.get("is_suggested"):
        return str(triple.get("status", "")).lower() == "approved"

    if triple.get("marked_for_removal", False):
        return False

    if str(triple.get("status", "")).lower() in ("superseded", "removed", "rejected"):
        return False

    return True


def build_adjudicated_gold_set(session_or_sentences: Any) -> List[Dict[str, Any]]:
    """
    Constructs the canonical adjudicated gold triple set from a session dictionary
    or list of sentences. Ensures only intended final triples appear in exports.
    """
    if isinstance(session_or_sentences, dict):
        if session_or_sentences.get("sentences"):
            sentences = session_or_sentences.get("sentences", [])
        else:
            versions = session_or_sentences.get("versions") or []
            curr_ver = session_or_sentences.get("current_version_name")
            active_ver = next((v for v in versions if v.get("name") == curr_ver), None) if curr_ver else (versions[-1] if versions else None)
            if active_ver and active_ver.get("sentences"):
                sentences = active_ver.get("sentences", [])
            else:
                sentences = session_or_sentences.get("sentences", [])
    elif isinstance(session_or_sentences, list):
        sentences = session_or_sentences
    else:
        return []

    gold_triples: List[Dict[str, Any]] = []
    for sentence in sentences:
        sentence_id = sentence.get("id") or sentence.get("sentence_id") or ""
        source_sentence = sentence.get("sentence") or sentence.get("source_sentence") or ""

        for triple in sentence.get("triples", []):
            if include_in_adjudicated_gold(triple):
                item = dict(triple)
                item["sentence_id"] = sentence_id
                item["source_sentence"] = source_sentence
                gold_triples.append(item)

    return gold_triples
