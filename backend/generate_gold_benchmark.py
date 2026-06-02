#!/usr/bin/env python3
"""Generate a row-based gold benchmark CSV from the block-style `new set.csv`."""

from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from evaluate_openie_new_set import Triple, clean_cell, SEP_RE, parse_new_set_csv


NEGATIVE_PATTERNS = {
    "not",
    "is_not",
    "should_not",
    "should_not_be",
    "not_intended_for",
    "prohibits",
    "not_addressed_by",
}

PROHIBITION_PATTERNS = {
    "prohibits",
    "is_not",
    "not_intended_for",
    "should_not",
    "should_not_be",
    "must_not",
}

OBLIGATION_PATTERNS = {
    "should",
    "shall",
    "must",
}

PERMISSION_PATTERNS = {
    "can_be",
    "may",
    "may_have",
    "allowed",
}


def guess_polarity(predicate: str) -> str:
    text = predicate.lower()
    if any(p in text for p in NEGATIVE_PATTERNS):
        return "negative"
    return "affirmative"


def guess_modality(predicate: str) -> str:
    text = predicate.lower()
    if any(p in text for p in PROHIBITION_PATTERNS):
        return "prohibition"
    if any(p in text for p in OBLIGATION_PATTERNS):
        return "obligation"
    if any(p in text for p in PERMISSION_PATTERNS):
        return "permission"
    return "none"


def is_sentence_candidate(text: str) -> bool:
    text = clean_cell(text)
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith(("v2 -", "since ", "here,", "we can ", "this ")):
        return False
    return len(text.split()) >= 5 and any(p in text for p in ".?!")


def convert_gold_csv(input_path: Path, output_path: Path, sentence_col: int = 7) -> None:
    rows: List[List[str]] = []
    with input_path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append([clean_cell(x) for x in row])

    triples: List[Dict[str, str]] = []
    current_sid = 1
    current_sentence = ""
    last_sentence = ""
    triple_counter = 1

    def sid() -> str:
        return f"s{current_sid:04d}"

    for ridx, row in enumerate(rows):
        while len(row) <= max(2, sentence_col):
            row.append("")

        c0, c1, c2 = row[0], row[1], row[2]
        sentence_candidate = row[sentence_col]
        note_candidate = row[sentence_col]

        if SEP_RE.match(c0):
            if current_sentence:
                current_sid += 1
            current_sentence = ""
            continue

        if not any(row):
            continue

        if is_sentence_candidate(sentence_candidate):
            current_sentence = sentence_candidate
            last_sentence = sentence_candidate
            continue

        if not current_sentence and last_sentence:
            current_sentence = last_sentence

        if c0 and c1 and c2 and not SEP_RE.match(c0):
            note = ""
            if note_candidate and not is_sentence_candidate(note_candidate):
                note = note_candidate
            triples.append(
                {
                    "sentence_id": sid(),
                    "source_sentence": current_sentence,
                    "triple_id": f"t{triple_counter:05d}",
                    "subject": c0,
                    "predicate": c1,
                    "object": c2,
                    "polarity": guess_polarity(c1),
                    "modality": guess_modality(c1),
                    "scope": "",
                    "note": note,
                    "status": "approved",
                }
            )
            triple_counter += 1

    # Write row-based benchmark CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sentence_id",
                "source_sentence",
                "triple_id",
                "subject",
                "predicate",
                "object",
                "polarity",
                "modality",
                "scope",
                "note",
                "status",
            ],
        )
        writer.writeheader()
        for row in triples:
            writer.writerow(row)

    print(f"Wrote {len(triples)} benchmark rows to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert block-style new set CSV into a row-based benchmark.")
    parser.add_argument("input_csv", help="Path to the raw gold CSV, e.g. 'new set.csv'.")
    parser.add_argument("output_csv", help="Path for the cleaned benchmark CSV.")
    parser.add_argument("--sentence-col", type=int, default=7, help="Column index for sentence/note text.")
    args = parser.parse_args()
    convert_gold_csv(Path(args.input_csv), Path(args.output_csv), sentence_col=args.sentence_col)
