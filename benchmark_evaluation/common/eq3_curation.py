"""
eq3_curation.py: EQ3 inputs and curation counts, shared by both corpora.

Each model's candidates were uploaded to TripleGrader as one session. A grader scored every
candidate, then corrected it with an approved revision, removed it with an approved removal
request, or left it unchanged, and added the reference triples the model had missed. The owner
published the result, which equals the existing benchmark B1.

`curation_outcomes` compares every original candidate with the published version of its session
through the candidate's identifier (`<sentence number>_<position>`):

  exact     still present with the same subject, predicate and object
  modified  still present, but an approved revision changed at least one slot
  deleted   taken out by an approved removal request
  new       a triple in the published version that is not an original candidate

exact + modified + new is the size of the published version, which equals |B1|.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

Key = Tuple[str, str, str]

# (display name, file stem) for the four models, in table order.
MODELS = [
    ("ChatGPT-5.6-High", "chatgpt_5_6_high"),
    ("Gemini-3.1-Pro", "gemini_3_1_pro"),
    ("GPT-OSS 120B", "gpt_oss_120b"),
    ("Qwen 3.8 27B", "qwen_38b"),
]
B1_FILE = "curated_b1/b1_curated_gold.json"


def candidates_file(stem: str) -> str:
    return f"candidates/candidates_{stem}_sentences.json"


def session_file(stem: str) -> str:
    return f"curation_sessions/curated_{stem}.json"


def norm_slot(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "").replace("-", "").replace('"', "")


def triple_key(t: Dict[str, Any]) -> Key:
    """Normalized (subject, predicate, object), used to compare reruns of the same model."""
    return (norm_slot(t.get("subject")), norm_slot(t.get("predicate")), norm_slot(t.get("object")))


def spo(t: Dict[str, Any]) -> Key:
    """The triple exactly as written, apart from surrounding spaces."""
    return (str(t.get("subject") or "").strip(), str(t.get("predicate") or "").strip(),
            str(t.get("object") or "").strip())


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    """SHA-256 of a text input with CRLF read as LF, so a Windows checkout hashes like the repository."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def original_candidates(candidate_session: Dict[str, Any]) -> List[List[Key]]:
    """The model's output per sentence: the first version of the frozen candidate file.

    Triples with an empty slot were not uploaded, so they are skipped here as well; the
    remaining triples keep the order they were uploaded in.
    """
    out = []
    for s in candidate_session["versions"][0]["sentences"]:
        out.append([spo(t) for t in s.get("triples", []) if all(spo(t))])
    return out


def published_sentences(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Sentences of the version that is active in the exported session (the published benchmark)."""
    name = session.get("current_version_name")
    version = next((v for v in session["versions"] if v.get("name") == name), session["versions"][-1])
    return version["sentences"]


def is_benchmark_triple(t: Dict[str, Any]) -> bool:
    """Placeholder rows and grader proposals the owner never approved are not part of the benchmark."""
    if str(t.get("subject") or "").startswith("[No Triples"):
        return False
    return not t.get("is_new_suggestion") or t.get("status") == "approved"


def curation_outcomes(candidates: List[List[Key]], published: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"candidates": 0, "exact": 0, "modified": 0, "deleted": 0, "new": 0, "published": 0}
    if len(candidates) != len(published):
        raise ValueError("candidate file and session have a different number of sentences")
    for number, (originals, sentence) in enumerate(zip(candidates, published), start=1):
        kept = {str(t.get("id")): t for t in sentence.get("triples", []) if is_benchmark_triple(t)}
        original_ids = {f"{number}_{k}": key for k, key in enumerate(originals, start=1)}
        for tid, key in original_ids.items():
            counts["candidates"] += 1
            if tid not in kept:
                counts["deleted"] += 1
            elif spo(kept[tid]) == key:
                counts["exact"] += 1
            else:
                counts["modified"] += 1
        counts["new"] += sum(1 for tid in kept if tid not in original_ids)
        counts["published"] += len(kept)
    return counts


def matches_benchmark(published: List[Dict[str, Any]], b1: Dict[str, Any], order: List[str]) -> List[int]:
    """Sentence numbers whose published triples differ from B1 (an empty list means they all match)."""
    gold = {s["sentence_id"]: sorted(spo(t) for t in s["triples"]) for s in b1["sentences"]}
    differ = []
    for number, (sid, sentence) in enumerate(zip(order, published), start=1):
        mine = sorted(spo(t) for t in sentence.get("triples", []) if is_benchmark_triple(t))
        if mine != gold.get(sid):
            differ.append(number)
    return differ
