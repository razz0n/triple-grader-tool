"""
build_corruptions.py: injects the ten EQ2 error types into the reference benchmark at a given
density and seed.

  E1 to E3  replace the subject, predicate or object; E4 swaps subject and object
  E5        removes a triple; E6 adds a spurious one; E7 adds a duplicate
  E8        malformed tokens; E9 representation variants
  E10       conflicting revision candidates

It writes the corrupted session to corrupted/ and a manifest with the inverse curation actions
to manifests/. The same seed gives the same corruptions.
"""

import copy
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Domain distractors curated from IEEE/ACM software engineering ethics and computing domains
SUBJECT_DISTRACTORS = [
    "autonomous_agent", "hardware_platform", "regulatory_agency", "third_party_contractor",
    "automated_pipeline", "system_operator", "cloud_provider", "security_auditor",
    "end_user", "executive_board", "data_broker", "external_adversary"
]

PREDICATE_DISTRACTORS = [
    "violates", "compromises", "disregards", "neglects", "opposes",
    "conflicts_with", "overrides", "undermines", "invalidates", "supersedes_without_notice"
]

OBJECT_DISTRACTORS = [
    "private_profit", "commercial_interest", "proprietary_advantage", "system_vulnerability",
    "confidential_leakage", "arbitrary_mandate", "expediency", "operational_risk",
    "unauthorized_access", "unverified_assumption", "exclusive_privilege"
]

ERROR_TYPE_NAMES = {
    "E1": "subject_replacement",
    "E2": "predicate_replacement",
    "E3": "object_replacement",
    "E4": "subject_object_swap",
    "E5": "missing_triple",
    "E6": "spurious_triple",
    "E7": "duplicate_triple",
    "E8": "malformed_triple",
    "E9": "representation_variant",
    "E10": "compound_conflict_case",
}


def load_reference_gold(ref_path: Path) -> Tuple[Dict[str, Any], str]:
    """Loads reference gold session and calculates its SHA-256 hash."""
    with open(ref_path, "rb") as fh:
        raw = fh.read()
    sha256 = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw.decode("utf-8"))
    return data, sha256


def get_all_triples(session_data: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Extracts all (sentence_id, triple_dict) pairs from the session."""
    pairs = []
    for sent in session_data.get("sentences", []):
        s_id = sent.get("id") or sent.get("sentence_id")
        for t in sent.get("triples", []):
            pairs.append((s_id, t))
    return pairs


def generate_corruption(
    ref_path: Path,
    error_type: str,
    density: float,
    seed: int,
    output_dir: Path,
) -> Tuple[Path, Path]:
    """
    Generates corrupted dataset C_e,d,r and manifest M_e,d,r for a given condition.
    """
    assert error_type in ERROR_TYPE_NAMES, f"Unknown error type: {error_type}"
    assert 0.0 < density <= 1.0, f"Invalid density: {density}"

    rng = random.Random(seed)
    base_data, ref_hash = load_reference_gold(ref_path)
    corrupted_data = copy.deepcopy(base_data)

    all_triples_idx = []
    for s_idx, sent in enumerate(corrupted_data.get("sentences", [])):
        s_id = sent.get("id") or sent.get("sentence_id")
        for t_idx, t in enumerate(sent.get("triples", [])):
            all_triples_idx.append((s_idx, t_idx, s_id, t))

    total_eligible = len(all_triples_idx)
    target_count = max(1, int(round(total_eligible * density)))

    # Deterministically select targets
    selected_indices = rng.sample(range(total_eligible), min(target_count, total_eligible))
    selected_indices.sort(reverse=True)  # Sort descending for safe removal operations

    changes = []
    experiment_id = f"EQ2_{error_type}_d{int(density*100):02d}_seed{seed:02d}"
    corrupted_data["id"] = experiment_id
    corrupted_data["session_id"] = experiment_id

    if error_type == "E1":  # Subject Replacement
        for idx in selected_indices:
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            target_triple = corrupted_data["sentences"][s_idx]["triples"][t_idx]
            orig_s = target_triple["subject"]
            candidates = [d for d in SUBJECT_DISTRACTORS if d.lower() != orig_s.lower()]
            new_s = rng.choice(candidates)
            target_triple["subject"] = new_s

            changes.append({
                "sentence_id": s_id,
                "triple_id": target_triple["id"],
                "corruption_type": "subject_replacement",
                "before": [orig_s, target_triple["predicate"], target_triple["object"]],
                "after": [new_s, target_triple["predicate"], target_triple["object"]],
                "inverse_actions": [
                    {
                        "action": "create_suggestion",
                        "sentence_id": s_id,
                        "triple_id": target_triple["id"],
                        "subject": orig_s,
                        "predicate": target_triple["predicate"],
                        "object": target_triple["object"],
                        "comment": "Oracle repair: restore ground-truth subject"
                    },
                    {
                        "action": "approve_suggestion",
                        "triple_id": target_triple["id"]
                    }
                ]
            })

    elif error_type == "E2":  # Predicate Replacement
        for idx in selected_indices:
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            target_triple = corrupted_data["sentences"][s_idx]["triples"][t_idx]
            orig_p = target_triple["predicate"]
            candidates = [d for d in PREDICATE_DISTRACTORS if d.lower() != orig_p.lower()]
            new_p = rng.choice(candidates)
            target_triple["predicate"] = new_p

            changes.append({
                "sentence_id": s_id,
                "triple_id": target_triple["id"],
                "corruption_type": "predicate_replacement",
                "before": [target_triple["subject"], orig_p, target_triple["object"]],
                "after": [target_triple["subject"], new_p, target_triple["object"]],
                "inverse_actions": [
                    {
                        "action": "create_suggestion",
                        "sentence_id": s_id,
                        "triple_id": target_triple["id"],
                        "subject": target_triple["subject"],
                        "predicate": orig_p,
                        "object": target_triple["object"],
                        "comment": "Oracle repair: restore ground-truth predicate"
                    },
                    {
                        "action": "approve_suggestion",
                        "triple_id": target_triple["id"]
                    }
                ]
            })

    elif error_type == "E3":  # Object Replacement
        for idx in selected_indices:
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            target_triple = corrupted_data["sentences"][s_idx]["triples"][t_idx]
            orig_o = target_triple["object"]
            candidates = [d for d in OBJECT_DISTRACTORS if d.lower() != orig_o.lower()]
            new_o = rng.choice(candidates)
            target_triple["object"] = new_o

            changes.append({
                "sentence_id": s_id,
                "triple_id": target_triple["id"],
                "corruption_type": "object_replacement",
                "before": [target_triple["subject"], target_triple["predicate"], orig_o],
                "after": [target_triple["subject"], target_triple["predicate"], new_o],
                "inverse_actions": [
                    {
                        "action": "create_suggestion",
                        "sentence_id": s_id,
                        "triple_id": target_triple["id"],
                        "subject": target_triple["subject"],
                        "predicate": target_triple["predicate"],
                        "object": orig_o,
                        "comment": "Oracle repair: restore ground-truth object"
                    },
                    {
                        "action": "approve_suggestion",
                        "triple_id": target_triple["id"]
                    }
                ]
            })

    elif error_type == "E4":  # Subject/Object Swap
        for idx in selected_indices:
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            target_triple = corrupted_data["sentences"][s_idx]["triples"][t_idx]
            orig_s, orig_p, orig_o = target_triple["subject"], target_triple["predicate"], target_triple["object"]
            target_triple["subject"] = orig_o
            target_triple["object"] = orig_s

            changes.append({
                "sentence_id": s_id,
                "triple_id": target_triple["id"],
                "corruption_type": "subject_object_swap",
                "before": [orig_s, orig_p, orig_o],
                "after": [orig_o, orig_p, orig_s],
                "inverse_actions": [
                    {
                        "action": "create_suggestion",
                        "sentence_id": s_id,
                        "triple_id": target_triple["id"],
                        "subject": orig_s,
                        "predicate": orig_p,
                        "object": orig_o,
                        "comment": "Oracle repair: reverse swapped subject and object"
                    },
                    {
                        "action": "approve_suggestion",
                        "triple_id": target_triple["id"]
                    }
                ]
            })

    elif error_type == "E5":  # Missing Triple (Deletion)
        for idx in selected_indices:
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            deleted_triple = corrupted_data["sentences"][s_idx]["triples"].pop(t_idx)

            changes.append({
                "sentence_id": s_id,
                "triple_id": deleted_triple["id"],
                "corruption_type": "missing_triple",
                "before": [deleted_triple["subject"], deleted_triple["predicate"], deleted_triple["object"]],
                "after": None,
                "inverse_actions": [
                    {
                        "action": "add_missing_triple",
                        "sentence_id": s_id,
                        "triple": deleted_triple,
                        "comment": "Oracle repair: reinsert omitted ground-truth triple"
                    }
                ]
            })

    elif error_type == "E6":  # Spurious Triple (Insertion)
        for i, idx in enumerate(selected_indices):
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            spurious_id = f"t_spurious_{i+1:04d}"
            spurious_t = {
                "id": spurious_id,
                "triple_id": spurious_id,
                "subject": f"unsupported_entity_{i+1}",
                "predicate": "hallucinates_relation",
                "object": f"extraneous_fact_{i+1}",
                "status": "active",
                "polarity": "affirmative",
                "modality": "none",
                "suggestions": []
            }
            corrupted_data["sentences"][s_idx]["triples"].append(spurious_t)

            changes.append({
                "sentence_id": s_id,
                "triple_id": spurious_id,
                "corruption_type": "spurious_triple",
                "before": None,
                "after": [spurious_t["subject"], spurious_t["predicate"], spurious_t["object"]],
                "inverse_actions": [
                    {
                        "action": "mark_for_removal",
                        "sentence_id": s_id,
                        "triple_id": spurious_id,
                        "reason": "Oracle repair: prune hallucinated spurious triple"
                    }
                ]
            })

    elif error_type == "E7":  # Duplicate Triple
        for i, idx in enumerate(selected_indices):
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            dup_id = f"{orig_t['id']}_dup"
            dup_triple = copy.deepcopy(orig_t)
            dup_triple["id"] = dup_id
            dup_triple["triple_id"] = dup_id
            corrupted_data["sentences"][s_idx]["triples"].append(dup_triple)

            changes.append({
                "sentence_id": s_id,
                "triple_id": dup_id,
                "original_triple_id": orig_t["id"],
                "corruption_type": "duplicate_triple",
                "before": None,
                "after": [dup_triple["subject"], dup_triple["predicate"], dup_triple["object"]],
                "inverse_actions": [
                    {
                        "action": "mark_for_removal",
                        "sentence_id": s_id,
                        "triple_id": dup_id,
                        "reason": "Oracle repair: remove redundant duplicate copy"
                    }
                ]
            })

    elif error_type == "E8":  # Malformed Triple (Empty/Invalid field)
        for idx in selected_indices:
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            target_triple = corrupted_data["sentences"][s_idx]["triples"][t_idx]
            orig_p = target_triple["predicate"]
            target_triple["predicate"] = ""  # Malformed empty predicate

            changes.append({
                "sentence_id": s_id,
                "triple_id": target_triple["id"],
                "corruption_type": "malformed_triple",
                "before": [target_triple["subject"], orig_p, target_triple["object"]],
                "after": [target_triple["subject"], "", target_triple["object"]],
                "inverse_actions": [
                    {
                        "action": "create_suggestion",
                        "sentence_id": s_id,
                        "triple_id": target_triple["id"],
                        "subject": target_triple["subject"],
                        "predicate": orig_p,
                        "object": target_triple["object"],
                        "comment": "Oracle repair: fix empty/malformed predicate"
                    },
                    {
                        "action": "approve_suggestion",
                        "triple_id": target_triple["id"]
                    }
                ]
            })

    elif error_type == "E9":  # Representation Variant (Formatting/Alias)
        for idx in selected_indices:
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            target_triple = corrupted_data["sentences"][s_idx]["triples"][t_idx]
            orig_s = target_triple["subject"]
            variant_s = orig_s.lower().replace("_", "-") + "_alias"
            target_triple["subject"] = variant_s

            changes.append({
                "sentence_id": s_id,
                "triple_id": target_triple["id"],
                "corruption_type": "representation_variant",
                "before": [orig_s, target_triple["predicate"], target_triple["object"]],
                "after": [variant_s, target_triple["predicate"], target_triple["object"]],
                "inverse_actions": [
                    {
                        "action": "create_suggestion",
                        "sentence_id": s_id,
                        "triple_id": target_triple["id"],
                        "subject": orig_s,
                        "predicate": target_triple["predicate"],
                        "object": target_triple["object"],
                        "comment": "Oracle repair: restore canonical vocabulary representation"
                    },
                    {
                        "action": "approve_suggestion",
                        "triple_id": target_triple["id"]
                    }
                ]
            })

    elif error_type == "E10":  # Compound Conflict Case
        # Injects multiple competing suggestions where raters disagree
        for idx in selected_indices:
            s_idx, t_idx, s_id, orig_t = all_triples_idx[idx]
            target_triple = corrupted_data["sentences"][s_idx]["triples"][t_idx]
            orig_s = target_triple["subject"]
            orig_p = target_triple["predicate"]
            orig_o = target_triple["object"]

            corrupt_s = rng.choice([d for d in SUBJECT_DISTRACTORS if d != orig_s])
            corrupt_p = rng.choice([d for d in PREDICATE_DISTRACTORS if d != orig_p])
            target_triple["subject"] = corrupt_s
            target_triple["predicate"] = corrupt_p

            changes.append({
                "sentence_id": s_id,
                "triple_id": target_triple["id"],
                "corruption_type": "compound_conflict_case",
                "before": [orig_s, orig_p, orig_o],
                "after": [corrupt_s, corrupt_p, orig_o],
                "inverse_actions": [
                    # Competing erroneous suggestion from reviewer_a
                    {
                        "action": "create_suggestion",
                        "user": "reviewer_a",
                        "sentence_id": s_id,
                        "triple_id": target_triple["id"],
                        "subject": "erroneous_candidate",
                        "predicate": "incorrect_relation",
                        "object": orig_o,
                        "comment": "Erroneous competing suggestion"
                    },
                    # Valid consensus suggestion from reviewer_b
                    {
                        "action": "create_suggestion",
                        "user": "reviewer_b",
                        "sentence_id": s_id,
                        "triple_id": target_triple["id"],
                        "subject": orig_s,
                        "predicate": orig_p,
                        "object": orig_o,
                        "comment": "Authoritative consensus repair"
                    },
                    # Peer vote upvoting valid suggestion
                    {
                        "action": "vote_suggestion",
                        "user": "reviewer_c",
                        "target_suggestion_valid": True,
                        "vote": "approve"
                    },
                    # Owner approves winning valid suggestion
                    {
                        "action": "approve_winning_suggestion",
                        "triple_id": target_triple["id"]
                    }
                ]
            })

    # Save corrupted dataset
    corr_file = output_dir / "corrupted" / f"corrupted_{error_type}_d{int(density*100):02d}_seed{seed:02d}.json"
    with open(corr_file, "w", encoding="utf-8") as fh:
        json.dump(corrupted_data, fh, indent=2, ensure_ascii=False)

    # Save manifest
    manifest_data = {
        "experiment_id": experiment_id,
        "reference_sha256": ref_hash,
        "error_type": error_type,
        "corruption_name": ERROR_TYPE_NAMES[error_type],
        "density": density,
        "seed": seed,
        "total_eligible_triples": total_eligible,
        "injected_count": len(changes),
        "changes": changes,
    }
    manifest_file = output_dir / "manifests" / f"manifest_{error_type}_d{int(density*100):02d}_seed{seed:02d}.json"
    with open(manifest_file, "w", encoding="utf-8") as fh:
        json.dump(manifest_data, fh, indent=2, ensure_ascii=False)

    return corr_file, manifest_file


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    ref_file = base_dir / "reference" / "reference_gold.json"
    print(f"Testing deterministic corruption generator against: {ref_file}")

    for e in ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10"]:
        c_path, m_path = generate_corruption(ref_file, e, 0.10, 42, base_dir)
        print(f"Generated {e} (10%, seed 42) -> {c_path.name}, Manifest: {m_path.name}")
