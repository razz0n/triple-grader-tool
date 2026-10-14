"""
freeze_eq3.py — Freezes the EQ3 inputs (candidates, B0, B1, prompts, demonstrations).

For each domain this script
  1. checks that B1 (curated_b1/b1_curated_gold.json) equals the final version
     stored in every candidate session file,
  2. checks that frozen_b0/b0_raw_candidates.json equals the normalized union of
     the initial candidate versions (the file is written only if it is absent and
     is never overwritten),
  3. records the SHA-256 of every input in FROZEN_MANIFEST.json.

Once a manifest exists it is never overwritten unless --refreeze is given.
All analysis scripts call common.eq3_metrics.verify_frozen() and stop if any
frozen file has changed.

Usage:
    python benchmark_evaluation/freeze_eq3.py            # verify / create manifests
    python benchmark_evaluation/freeze_eq3.py --refreeze  # rewrite manifests (deliberate)
"""

import argparse
import json
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parent))

from benchmark_evaluation.common.eq3_metrics import (  # noqa: E402
    MODEL_FILES, build_union, load_candidate_sessions, load_json, sentence_sets, sha256_file,
)

DOMAINS = {
    "eq3_software_ethics": {
        "domain": "Software Engineering Ethics",
        "prompt_files": ["prompt and fewshots/few_shot_examples.json", "prompt and fewshots/frozen_sentences.json"],
        "b0_name": "Software Ethics Pre-Curation Candidate Union (B0)",
    },
    "eq3_biomedical_bel": {
        "domain": "Biomedical Native-BEL",
        "prompt_files": [
            "prompt and few shots/01_prompt_en.txt",
            "prompt and few shots/02_few_shot_examples_30.json",
            "prompt and few shots/09_prompt_with_shots_template_en.txt",
        ],
        "b0_name": "Biomedical Native-BEL Pre-Curation Candidate Union (B0)",
    },
}

B0_REL = "frozen_b0/b0_raw_candidates.json"
B1_REL = "curated_b1/b1_curated_gold.json"


def write_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def freeze(dir_name: str, cfg: dict, refreeze: bool) -> None:
    exp = BENCH_DIR / dir_name
    manifest_path = exp / "FROZEN_MANIFEST.json"
    sessions = load_candidate_sessions(exp / "candidates")

    b1 = load_json(exp / B1_REL)
    gold = sentence_sets(b1["sentences"])
    for name, sess in sessions.items():
        if sentence_sets(sess["versions"][-1]["sentences"]) != gold:
            raise SystemExit(f"[{dir_name}] final version of {name} differs from {B1_REL}")

    union = build_union(sessions)
    union_sets = sentence_sets(union)
    b0_rel = B0_REL
    b0_path = exp / b0_rel
    if b0_path.exists() and sentence_sets(load_json(b0_path)["sentences"]) != union_sets:
        raise SystemExit(f"[{dir_name}] {b0_rel} is not the union of the current candidate files; investigate manually")
    if not b0_path.exists():
        write_json(b0_path, {
            "dataset_name": cfg["b0_name"],
            "description": "Normalized union of the initial candidate triples of ChatGPT-5.6-High, Gemini-3.1-Pro, "
                           "GPT-OSS 120B and Qwen 3.8 27B. Built by freeze_eq3.py; do not edit.",
            "normalization": "per sentence; slots trimmed, lower-cased, underscores/hyphens/double quotes removed",
            "total_sentences": len(union),
            "total_triples": sum(len(s["triples"]) for s in union),
            "sentences": union,
        })
        print(f"[{dir_name}] wrote {b0_rel} ({sum(len(s['triples']) for s in union)} triples)")

    files = [f"candidates/{fname}" for _, fname in MODEL_FILES] + [b0_rel, B1_REL] + cfg["prompt_files"]
    digests = {rel: sha256_file(exp / rel) for rel in files}

    if manifest_path.exists() and not refreeze:
        current = load_json(manifest_path)["sha256"]
        changed = [rel for rel in files if current.get(rel) != digests[rel]]
        if changed:
            raise SystemExit(f"[{dir_name}] frozen inputs changed: {changed}. Investigate before using --refreeze.")
        print(f"[{dir_name}] manifest verified ({len(files)} files unchanged)")
        return

    write_json(manifest_path, {
        "domain": cfg["domain"],
        "b0_file": b0_rel,
        "b1_file": B1_REL,
        "b0_triples": sum(len(v) for v in sentence_sets(load_json(b0_path)["sentences"]).values()),
        "b1_triples": sum(len(v) for v in gold.values()),
        "sentences": len(gold),
        "sha256": digests,
    })
    print(f"[{dir_name}] wrote FROZEN_MANIFEST.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refreeze", action="store_true", help="rewrite manifests even if they exist")
    args = ap.parse_args()
    for dir_name, cfg in DOMAINS.items():
        freeze(dir_name, cfg, args.refreeze)


if __name__ == "__main__":
    main()
