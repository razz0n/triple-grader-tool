"""
groq_rerun.py: a second run of the two Groq-hosted models on the 40 biomedical targets.

Sends the frozen 30-shot prompt template (prompt and few shots/09_prompt_with_shots_template_en.txt)
with exactly one target per request to each Groq model at temperature 0, stores every raw API
response, and compares the returned BEL statements with the frozen candidate sessions.

It never modifies candidates/, curated_b1/ or curation_sessions/. Outputs go to reproducibility_rerun/.

    GROQ_API_KEY=... python benchmark_evaluation/eq3_biomedical_bel/groq_rerun.py

The API key is read from the environment only and is never written to disk. Requests that already
have a stored response are skipped, so an interrupted run can be resumed.
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXP = Path(__file__).resolve().parent
TEMPLATE = EXP / "prompt and few shots" / "09_prompt_with_shots_template_en.txt"
PLACEHOLDER = "<PASTE EXACTLY ONE TARGET JSON OBJECT HERE>"
OUT = EXP / "reproducibility_rerun"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = {
    "openai/gpt-oss-120b": "candidates_gpt_oss_120b_sentences.json",
    "qwen/qwen3.8-27b": "candidates_qwen_38b_sentences.json",
}
TEMPERATURE = 0


def norm_bel(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def load_targets():
    session = json.loads((EXP / "candidates" / MODELS["openai/gpt-oss-120b"]).read_text(encoding="utf-8"))
    return [{"sentence_id": s["sentence_id"], "sentence": s.get("sentence_text") or s.get("text")}
            for s in session["versions"][0]["sentences"]]


def frozen_statements(fname: str):
    session = json.loads((EXP / "candidates" / fname).read_text(encoding="utf-8"))
    out = {}
    for s in session["versions"][0]["sentences"]:
        out[s["sentence_id"]] = {norm_bel(t.get("raw_bel") or f"{t['subject']} {t['predicate']} {t['object']}")
                                 for t in s.get("triples", [])}
    return out


def build_prompt(template: str, target: dict) -> str:
    assert template.count(PLACEHOLDER) == 1
    return template.replace(PLACEHOLDER, json.dumps(target, indent=2, ensure_ascii=False))


def call_groq(key: str, model: str, prompt: str) -> dict:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
    }).encode("utf-8")
    for attempt in range(6):
        req = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            # Groq's edge rejects the default Python-urllib user agent.
            "User-Agent": "triplegrader-eq3-rerun/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503) and attempt < 5:
                time.sleep(min(60, 5 * 2 ** attempt))
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail[:300]}")
    raise RuntimeError("retries exhausted")


def parse_statements(content: str):
    """Returns (list of BEL strings, error or None). Strips reasoning blocks and Markdown fences."""
    text = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        match = re.search(r"\[.*\]", text, re.S)
        if not match:
            return [], f"unparseable: {e}"
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as e2:
            return [], f"unparseable: {e2}"
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        return [], "not a JSON array of strings"
    return data, None


def main() -> None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        sys.exit("Set GROQ_API_KEY in the environment.")
    template = TEMPLATE.read_text(encoding="utf-8")
    targets = load_targets()
    OUT.mkdir(exist_ok=True)
    report = {"template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
              "temperature": TEMPERATURE, "models": {}}

    for model, fname in MODELS.items():
        raw_dir = OUT / "raw" / model.replace("/", "__")
        raw_dir.mkdir(parents=True, exist_ok=True)
        frozen = frozen_statements(fname)
        rows = []
        for target in targets:
            path = raw_dir / f"{target['sentence_id'].replace(':', '_')}.json"
            prompt = build_prompt(template, target)
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
            statements, error = parse_statements(content)
            new = {norm_bel(s) for s in statements}
            old = frozen.get(target["sentence_id"], set())
            rows.append({"sentence_id": target["sentence_id"], "parse_error": error,
                         "n_rerun": len(new), "n_frozen": len(old), "n_common": len(new & old),
                         "identical": new == old})
        n_new = sum(r["n_rerun"] for r in rows)
        n_old = sum(r["n_frozen"] for r in rows)
        n_common = sum(r["n_common"] for r in rows)
        report["models"][model] = {
            "targets": len(rows),
            "identical_targets": sum(r["identical"] for r in rows),
            "parse_errors": sum(1 for r in rows if r["parse_error"]),
            "statements_rerun": n_new, "statements_frozen": n_old, "statements_common": n_common,
            "per_target": rows,
        }
        print(f"{model}: {sum(r['identical'] for r in rows)}/{len(rows)} targets identical; "
              f"{n_common} common statements (re-run {n_new}, frozen {n_old}); "
              f"{report['models'][model]['parse_errors']} parse errors")
    (OUT / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
