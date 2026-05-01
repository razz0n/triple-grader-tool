"""
evaluate.py — CLI for evaluating a graded session against OpenIE.

Usage
-----
  python evaluate.py --session PATH_TO_SESSION.json [options]

Options
-------
  --session   Path to a graded session JSON file (from the grading tool)
              OR a session ID if --storage-dir is provided.
  --storage-dir  Root storage directory to search for session by ID.
                 Defaults to ./storage/users/
  --match     Matching mode: "exact" or "soft" (default: soft)
  --both      Run both exact and soft match and write separate result files.
  --out       Output directory for result files (default: ./eval_results/)
  --no-json   Skip writing eval_results.json
  --no-csv    Skip writing eval_results.csv

Output files (written to --out directory)
------------------------------------------
  eval_results[_exact|_soft].json  — full result with per-sentence detail
  eval_results[_exact|_soft].csv   — flat CSV, one row per sentence

Example
-------
  python evaluate.py --session storage/users/abc123/session.json --both --out results/
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_session(session_arg: str, storage_dir: str) -> dict:
    p = Path(session_arg)

    # Direct file path
    if p.is_file():
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # Session ID search inside storage_dir
    root = Path(storage_dir)
    if root.is_dir():
        for candidate in root.glob(f"*/{session_arg}.json"):
            with open(candidate, "r", encoding="utf-8") as fh:
                return json.load(fh)
        # Also try direct child
        direct = root / f"{session_arg}.json"
        if direct.is_file():
            with open(direct, "r", encoding="utf-8") as fh:
                return json.load(fh)

    raise FileNotFoundError(
        f"Could not find session '{session_arg}'. "
        "Pass a full file path or a session ID with --storage-dir."
    )


def _write_json(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(f"  [JSON] {path}")


def _write_csv(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for s in result.get("per_sentence", []):
        gold_str = "; ".join(
            f"{t.get('subject','')} | {t.get('predicate','')} | {t.get('object','')}"
            for t in s.get("gold_triples", [])
        )
        pred_str = "; ".join(
            f"{t.get('subject','')} | {t.get('predicate','')} | {t.get('object','')}"
            for t in s.get("pred_triples", [])
        )
        rows.append({
            "session_id":     result.get("session_id", ""),
            "source_file":    result.get("source_filename", ""),
            "match_mode":     result.get("match_mode", ""),
            "sentence_id":    s["sentence_id"],
            "sentence_text":  s["sentence_text"],
            "n_gold":         s["n_gold"],
            "n_pred":         s["n_pred"],
            "true_positives": s["true_positives"],
            "precision":      s["precision"],
            "recall":         s["recall"],
            "f1":             s["f1"],
            "gold_triples":   gold_str,
            "pred_triples":   pred_str,
        })

    # Append macro and micro summary rows
    for agg_key in ("macro", "micro"):
        agg = result.get(agg_key, {})
        rows.append({
            "session_id":     result.get("session_id", ""),
            "source_file":    result.get("source_filename", ""),
            "match_mode":     result.get("match_mode", ""),
            "sentence_id":    f"[{agg_key}]",
            "sentence_text":  "",
            "n_gold":         agg.get("n_gold", ""),
            "n_pred":         agg.get("n_pred", ""),
            "true_positives": agg.get("true_positives", ""),
            "precision":      agg.get("precision", ""),
            "recall":         agg.get("recall", ""),
            "f1":             agg.get("f1", ""),
            "gold_triples":   "",
            "pred_triples":   "",
        })

    fieldnames = [
        "session_id", "source_file", "match_mode", "sentence_id",
        "sentence_text", "n_gold", "n_pred", "true_positives",
        "precision", "recall", "f1", "gold_triples", "pred_triples",
    ]

    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [CSV]  {path}")


def _print_summary(result: dict) -> None:
    mode = result["match_mode"]
    macro = result["macro"]
    micro = result["micro"]
    n = len(result.get("per_sentence", []))
    print(f"\n  Sentences evaluated : {n}")
    print(f"  Match mode          : {mode}")
    print(f"  ┌{'─'*14}┬{'─'*11}┬{'─'*11}┬{'─'*11}┐")
    print(f"  │{'':14}│{'Precision':^11}│{'Recall':^11}│{'F1':^11}│")
    print(f"  ├{'─'*14}┼{'─'*11}┼{'─'*11}┼{'─'*11}┤")
    print(f"  │{'Macro avg':14}│{macro['precision']:^11.4f}│{macro['recall']:^11.4f}│{macro['f1']:^11.4f}│")
    print(f"  │{'Micro avg':14}│{micro['precision']:^11.4f}│{micro['recall']:^11.4f}│{micro['f1']:^11.4f}│")
    print(f"  └{'─'*14}┴{'─'*11}┴{'─'*11}┴{'─'*11}┘")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate a graded session against Stanford OpenIE (stanza).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--session", required=True,
                        help="Path to graded session JSON or a session UUID.")
    parser.add_argument("--storage-dir", default="storage/users",
                        help="Root directory to search for session by ID. Default: storage/users")
    parser.add_argument("--match", choices=["exact", "soft"], default="soft",
                        help="Triple matching mode. Default: soft")
    parser.add_argument("--both", action="store_true",
                        help="Run both exact and soft matching and write separate files.")
    parser.add_argument("--out", default="eval_results",
                        help="Output directory. Default: ./eval_results/")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output.")
    parser.add_argument("--no-csv",  action="store_true", help="Skip CSV output.")
    args = parser.parse_args(argv)

    # ── Load session ─────────────────────────────────────────────────────
    print(f"\nLoading session: {args.session}")
    try:
        session = _load_session(args.session, args.storage_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    src = session.get("source_filename", "unknown")
    n_sentences = len(session.get("sentences", []))
    n_graded = sum(
        1 for s in session.get("sentences", [])
        for t in s.get("triples", []) if t.get("grade") is not None
    )
    print(f"  Source file : {src}")
    print(f"  Sentences   : {n_sentences}")
    print(f"  Graded triples: {n_graded}")

    # ── Lazy import after arg parsing (avoids slow stanza load on --help) ─
    from openie_eval import evaluate_session

    out_dir = Path(args.out)
    modes = ["exact", "soft"] if args.both else [args.match]

    for mode in modes:
        print(f"\nRunning OpenIE evaluation (mode={mode})...")
        result = evaluate_session(session, match_mode=mode)
        _print_summary(result)

        suffix = f"_{mode}" if args.both else ""
        if not args.no_json:
            _write_json(result, out_dir / f"eval_results{suffix}.json")
        if not args.no_csv:
            _write_csv(result, out_dir / f"eval_results{suffix}.csv")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
