"""
validate_manifest.py — Integrity and schema validator for corruption manifests.

Validates that generated corruption manifests conform to expected schema:
  - Reference dataset SHA-256 integrity match
  - Valid and non-empty inverse action definitions
  - Strict change non-triviality (before != after)
  - Change count and indexing consistency
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def validate_manifest(manifest_path: Path, ref_path: Path) -> Dict[str, Any]:
    """Validates an individual manifest file against the reference gold standard."""
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    # 1. Reference SHA-256 Check
    with open(ref_path, "rb") as fh:
        actual_ref_sha256 = hashlib.sha256(fh.read()).hexdigest()

    expected_sha256 = manifest.get("reference_sha256")
    assert expected_sha256 == actual_ref_sha256, (
        f"SHA-256 mismatch in {manifest_path.name}: manifest has {expected_sha256}, actual is {actual_ref_sha256}"
    )

    # 2. Structural checks
    changes = manifest.get("changes", [])
    injected_count = manifest.get("injected_count", 0)
    assert len(changes) == injected_count, (
        f"Injected count mismatch in {manifest_path.name}: declared {injected_count}, found {len(changes)}"
    )

    valid_actions = {
        "create_suggestion", "approve_suggestion", "mark_for_removal",
        "add_missing_triple", "vote_suggestion", "approve_winning_suggestion"
    }

    # 3. Change-level checks
    for idx, change in enumerate(changes):
        s_id = change.get("sentence_id")
        t_id = change.get("triple_id")
        assert s_id, f"Missing sentence_id at change #{idx} in {manifest_path.name}"
        assert t_id, f"Missing triple_id at change #{idx} in {manifest_path.name}"

        inv_actions = change.get("inverse_actions", [])
        assert len(inv_actions) > 0, f"No inverse actions for triple {t_id} in {manifest_path.name}"

        for act in inv_actions:
            act_name = act.get("action")
            assert act_name in valid_actions, f"Unknown inverse action '{act_name}' in {manifest_path.name}"

        # Non-triviality check
        before = change.get("before")
        after = change.get("after")
        if before is not None and after is not None:
            assert before != after, f"Trivial corruption at change #{idx} (before == after) in {manifest_path.name}"

    return {
        "manifest": manifest_path.name,
        "error_type": manifest.get("error_type"),
        "density": manifest.get("density"),
        "seed": manifest.get("seed"),
        "changes_validated": len(changes),
        "status": "VALID",
    }


def validate_all_manifests(manifests_dir: Path, ref_path: Path) -> List[Dict[str, Any]]:
    """Validates all manifest files in the manifests directory."""
    manifest_files = list(manifests_dir.glob("*.json"))
    if not manifest_files:
        print(f"No manifests found in {manifests_dir}")
        return []

    print(f"Validating {len(manifest_files)} manifests against reference standard: {ref_path.name}")
    results = []
    for mf in manifest_files:
        res = validate_manifest(mf, ref_path)
        results.append(res)
        print(f"  [PASS] {res['manifest']} ({res['error_type']}, density {res['density']*100:.0f}%, seed {res['seed']}) — {res['changes_validated']} changes verified.")

    print(f"\nAll {len(results)} manifests successfully validated with 100% schema integrity and cryptographic hash alignment.")
    return results


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    ref = base_dir / "reference" / "reference_gold.json"
    m_dir = base_dir / "manifests"
    validate_all_manifests(m_dir, ref)
