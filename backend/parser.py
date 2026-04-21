"""
parser.py — Parses CSV or Excel files containing ontology triples.

Expected file format (no header row):
  Col 0: Subject
  Col 1: Predicate
  Col 2: Object
  Col 3: Notes / version label  (ignored)
  Col 7: Natural-language sentence text  (may be split across multiple rows in a block)
  Other columns: analysis notes (ignored)

Blocks are separated by:
  - Rows where cols 0, 1, and 2 are all empty/NaN
  - Rows where col 0 starts with "=" (separator lines like =====...)
"""

import io
import re
from typing import List, Dict, Any

import pandas as pd


def _to_str(val) -> str:
    """Safely convert a cell value to a stripped string, or '' if null."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _is_separator(row: pd.Series) -> bool:
    """True if this row is an empty row or a ======= separator line."""
    col0 = _to_str(row.iloc[0])
    col1 = _to_str(row.iloc[1]) if len(row) > 1 else ""
    col2 = _to_str(row.iloc[2]) if len(row) > 2 else ""
    if col0 == "" and col1 == "" and col2 == "":
        return True
    if col0.startswith("="):
        return True
    return False


def _split_into_blocks(df: pd.DataFrame) -> List[List[pd.Series]]:
    """Split the dataframe into logical blocks separated by empty/separator rows."""
    blocks: List[List[pd.Series]] = []
    current: List[pd.Series] = []

    for _, row in df.iterrows():
        if _is_separator(row):
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(row)

    if current:
        blocks.append(current)

    return blocks


def _assemble_sentence(block: List[pd.Series]) -> str:
    """Concatenate all non-empty col-7 values across a block into one sentence."""
    parts = []
    for row in block:
        if len(row) > 7:
            val = _to_str(row.iloc[7])
            if val:
                parts.append(val)
    return " ".join(parts).strip()


def _extract_triples(block: List[pd.Series]) -> List[Dict[str, str]]:
    """Extract rows where subject, predicate, and object are all non-empty."""
    triples = []
    for row in block:
        subj = _to_str(row.iloc[0])
        pred = _to_str(row.iloc[1]) if len(row) > 1 else ""
        obj  = _to_str(row.iloc[2]) if len(row) > 2 else ""
        if subj and pred and obj:
            # Skip rows that look like section labels or pure noise
            # e.g. "This,is,Code_of_ethics" — keep; separator patterns already filtered
            triples.append({
                "subject":   subj,
                "predicate": pred,
                "object":    obj,
            })
    return triples


def _read_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read the file bytes into a pandas DataFrame with no header."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)
    else:
        # CSV — try UTF-8-sig first (handles BOM), fall back to latin-1
        try:
            df = pd.read_csv(io.StringIO(file_bytes.decode("utf-8-sig")), header=None, dtype=str)
        except Exception:
            df = pd.read_csv(io.StringIO(file_bytes.decode("latin-1")), header=None, dtype=str)
    return df


def parse_file(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parse an ontology triples file and return a structured sentence list.

    Returns:
        [
          {
            "id": 1,
            "text": "Computers have a central and growing role ...",
            "suggestion": "",
            "sentence_grade": None,
            "triples": [
              {
                "id": "1_1",
                "subject": "Computers",
                "predicate": "have",
                "object": "role_001",
                "grade": None
              },
              ...
            ]
          },
          ...
        ]
    """
    df = _read_dataframe(file_bytes, filename)

    # Ensure we have at least 8 columns (pad if narrower)
    while df.shape[1] < 8:
        df[df.shape[1]] = ""

    blocks = _split_into_blocks(df)

    sentences = []
    sentence_id = 1

    for block in blocks:
        sentence_text = _assemble_sentence(block)
        triples_raw   = _extract_triples(block)

        # Skip blocks that have no usable sentence or no triples
        if not sentence_text or not triples_raw:
            continue

        triples = [
            {
                "id":        f"{sentence_id}_{i + 1}",
                "subject":   t["subject"],
                "predicate": t["predicate"],
                "object":    t["object"],
                "grade":     None,
            }
            for i, t in enumerate(triples_raw)
        ]

        sentences.append({
            "id":             sentence_id,
            "text":           sentence_text,
            "suggestion":     "",
            "sentence_grade": None,
            "triples":        triples,
        })
        sentence_id += 1

    return sentences
