#!/usr/bin/env python3
"""Generate a row-based gold benchmark CSV from the rearranged CSV with explicit Sentences and Notes columns."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

SEP_RE = re.compile(r"^=+$")

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


def clean_cell(text: str) -> str:
    """Clean and normalize cell text."""
    if not text:
        return ""
    return text.strip()


def convert_gold_csv_v2(input_path: Path, output_path: Path) -> None:
    """
    Convert rearranged CSV with explicit Sentences and Notes columns.
    
    Format:
    - Column 0: Subject
    - Column 1: Predicate
    - Column 2: Object
    - Columns 3-6: metadata (unused)
    - Column 7: Sentences
    - Column 8: Notes
    
    Logic:
    - Track current sentence as we encounter rows with column 7 content
    - Rows with triples get assigned to current sentence
    - Separator rows (===) mark end of sentence block and increment sentence ID
    """
    rows: List[List[str]] = []
    with input_path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append([clean_cell(x) for x in row])

    triples: List[Dict[str, str]] = []
    current_sid = 1
    current_sentence = ""
    triple_counter = 1

    def sid() -> str:
        return f"s{current_sid:04d}"

    for ridx, row in enumerate(rows):
        # Ensure row has enough columns
        while len(row) <= 8:
            row.append("")

        c0, c1, c2 = row[0], row[1], row[2]
        col7_sentence = row[7] if len(row) > 7 else ""
        col8_note = row[8] if len(row) > 8 else ""

        # Skip header row
        if ridx == 0 and c0.lower() == "subject":
            continue

        # Skip separator rows (====...)
        if SEP_RE.match(c0):
            if current_sentence:
                current_sid += 1
            current_sentence = ""
            continue

        # Skip empty rows
        if not any(row[:3]):
            continue

        # Update current sentence if column 7 has text
        if col7_sentence:
            current_sentence = col7_sentence

        # If this row has a triple (subject, predicate, object all present)
        if c0 and c1 and c2 and not SEP_RE.match(c0):
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
                    "note": col8_note,
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
    input_csv = Path("long_coe_tuples(Rajan_Golden_dataset).csv")
    output_csv = Path("backend/gold_benchmark.csv")
    convert_gold_csv_v2(input_csv, output_csv)
