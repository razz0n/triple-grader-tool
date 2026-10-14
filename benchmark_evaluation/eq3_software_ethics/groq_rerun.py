"""
groq_rerun.py — Re-run of the Groq-hosted models on the 15 software-ethics sentences.

Sends the 21-shot prompt template (prompt and fewshots/21_shot_prompt_template.txt) with exactly
one target sentence per request to each Groq model at temperature 0, stores every raw API response,
and compares the returned triples with the frozen candidate sessions. Only the sentence text is sent;
the reference triples in frozen_sentences.json are never included in a prompt.

It never modifies candidates/, frozen_b0/ or curated_b1/. Outputs go to reproducibility_rerun/.

    GROQ_API_KEY=... python benchmark_evaluation/eq3_software_ethics/groq_rerun.py
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import importlib.util

EXP = Path(__file__).resolve().parent
sys.path.insert(0, str(EXP.parent.parent))

from benchmark_evaluation.common.eq3_metrics import triple_key  # noqa: E402

# Shared HTTP helper from the biomedical re-run (loaded by path: both scripts are named groq_rerun.py).
_spec = importlib.util.spec_from_file_location("bio_groq_rerun", EXP.parent / "eq3_biomedical_bel" / "groq_rerun.py")
_bio = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bio)
call_groq = _bio.call_groq

TEMPLATE = EXP / "prompt and fewshots" / "21_shot_prompt_template.txt"
SENTENCES = EXP / "prompt and fewshots" / "frozen_sentences.json"
PLACEHOLDER = "[TARGET_SENTENCE_HERE]"
OUT = EXP / "reproducibility_rerun"
MODELS = {
    "openai/gpt-oss-120b": "candidates_gpt_oss_120b_sentences.json",
    "qwen/qwen3.8-27b": "candidates_qwen_38b_sentences.json",
}
TEMPERATURE = 0


def load_targets():
    data = json.loads(SENTENCES.read_text(encoding="utf-8"))
    return [{"sentence_id": s["sentence_id"], "sentence": s["sentence"]} for s in data["sentences"]]


def frozen_triples(fname: str):
    session = json.loads((EXP / "candidates" / fname).read_text(encoding="utf-8"))
    return {s["sentence_id"]: {triple_key(t) for t in s.get("triples", [])} for s in session["versions"][0]["sentences"]}


def parse_triples(content: str):
    text = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.S)
        if not match:
            return [], "unparseable"
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return [], "unparseable"
    if not isinstance(data, list):
        return [], "not a JSON array"
    triples = [t for t in data if isinstance(t, dict) and all(k in t for k in ("subject", "predicate", "object"))]
    return triples, None if len(triples) == len(data) else "some items lack subject/predicate/object"


def main() -> None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        sys.exit("Set GROQ_API_KEY in the environment.")
    template = TEMPLATE.read_text(encoding="utf-8")
    assert template.count(PLACEHOLDER) == 1
    targets = load_targets()
    OUT.mkdir(exist_ok=True)
    report = {"template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
              "temperature": TEMPERATURE, "models": {}}

    for model, fname in MODELS.items():
        raw_dir = OUT / "raw" / model.replace("/", "__")
        raw_dir.mkdir(parents=True, exist_ok=True)
        frozen = frozen_triples(fname)
        rows = []
        for target in targets:
            path = raw_dir / f"{target['sentence_id']}.json"
            prompt = template.replace(PLACEHOLDER, target["sentence"])
            if not path.exists():
                response = call_groq(key, model, prompt)
                path.write_text(json.dumps({
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "model": model, "temperature": TEMPERATURE,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "target": target, "response": response,
                }, indent=2, ensure_ascii=False), encoding="utf-8")
                time.sleep(1.0)
            record = json.loads(path.read_text(encoding="utf-8"))
            content = record["response"]["choices"][0]["message"].get("content", "")
            triples, error = parse_triples(content)
            new = {triple_key(t) for t in triples} - {("", "", "")}
            old = frozen.get(target["sentence_id"], set())
            rows.append({"sentence_id": target["sentence_id"], "parse_error": error, "n_rerun": len(new),
                         "n_frozen": len(old), "n_common": len(new & old), "identical": new == old})
        report["models"][model] = {
            "targets": len(rows),
            "identical_targets": sum(r["identical"] for r in rows),
            "parse_errors": sum(1 for r in rows if r["parse_error"]),
            "triples_rerun": sum(r["n_rerun"] for r in rows),
            "triples_frozen": sum(r["n_frozen"] for r in rows),
            "triples_common": sum(r["n_common"] for r in rows),
            "per_target": rows,
        }
        m = report["models"][model]
        print(f"{model}: {m['identical_targets']}/{m['targets']} sentences identical; {m['triples_common']} common triples "
              f"(re-run {m['triples_rerun']}, frozen {m['triples_frozen']}); {m['parse_errors']} parse issues")
    (OUT / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
