"""
freeze_eq3.py: records and checks the SHA-256 of every EQ3 input.

The inputs of each corpus are the four frozen candidate files, the benchmark B1, the prompt and
demonstrations, and the four curated sessions exported from TripleGrader. Their hashes are kept in
FROZEN_MANIFEST.json. A manifest is written only when it is missing or when --refreeze is given;
otherwise the script stops if any input differs from it.

Usage:
    python benchmark_evaluation/freeze_eq3.py            # check (or create) the manifests
    python benchmark_evaluation/freeze_eq3.py --refreeze  # rewrite them on purpose
"""

import argparse
import json
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH_DIR.parent))

from benchmark_evaluation.common.eq3_curation import (  # noqa: E402
    B1_FILE, MODELS, candidates_file, load_json, session_file, sha256_file,
)

DOMAINS = {
    "eq3_software_ethics": {
        "domain": "Software Engineering Ethics",
        "prompt_files": ["prompt and fewshots/few_shot_examples.json", "prompt and fewshots/frozen_sentences.json"],
    },
    "eq3_biomedical_bel": {
        "domain": "Biomedical Native-BEL",
        "prompt_files": [
            "prompt and few shots/01_prompt_en.txt",
            "prompt and few shots/02_few_shot_examples_30.json",
            "prompt and few shots/09_prompt_with_shots_template_en.txt",
        ],
    },
}


def input_files(cfg: dict) -> list:
    files = [candidates_file(stem) for _, stem in MODELS] + [B1_FILE] + cfg["prompt_files"]
    return files + [session_file(stem) for _, stem in MODELS]


def manifest_for(exp: Path, cfg: dict) -> dict:
    b1 = load_json(exp / B1_FILE)
    return {
        "domain": cfg["domain"],
        "b1_file": B1_FILE,
        "b1_triples": sum(len(s["triples"]) for s in b1["sentences"]),
        "sentences": len(b1["sentences"]),
        "sha256": {rel: sha256_file(exp / rel) for rel in input_files(cfg)},
    }


def check(dir_name: str, refreeze: bool = False) -> dict:
    exp = BENCH_DIR / dir_name
    cfg = DOMAINS[dir_name]
    path = exp / "FROZEN_MANIFEST.json"
    current = manifest_for(exp, cfg)
    if refreeze or not path.exists():
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"[{dir_name}] manifest written ({len(current['sha256'])} files)")
        return current
    stored = load_json(path)
    changed = [rel for rel, digest in current["sha256"].items() if stored.get("sha256", {}).get(rel) != digest]
    missing = [rel for rel in stored.get("sha256", {}) if rel not in current["sha256"]]
    if changed or missing:
        raise SystemExit(f"[{dir_name}] inputs differ from FROZEN_MANIFEST.json: {changed + missing}")
    print(f"[{dir_name}] all {len(current['sha256'])} inputs match FROZEN_MANIFEST.json")
    return stored


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refreeze", action="store_true", help="rewrite the manifests")
    args = ap.parse_args()
    for dir_name in DOMAINS:
        check(dir_name, args.refreeze)


if __name__ == "__main__":
    main()
