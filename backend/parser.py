"""
parser.py — Parses CSV or Excel files containing ontology triples.

Expected file format (no header row):
  Col 0: Subject
  Col 1: Predicate
  Col 2: Object
  Col 3: Version label  ("By me", "v2", "GPT", etc.)
  Cols 4-12: May contain natural-language sentence text and annotations
  Other columns: analysis notes (ignored)

Sentence groups are identified by detecting rows that contain real
natural-language sentences (heuristic filter).  "=" separator rows act as
hard sentence-group boundaries.  Blank rows act as sub-block separators
within a sentence group (potential multiple versions of the same sentence).
"""

import io
from typing import Any, Dict, List

import pandas as pd


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _to_str(val) -> str:
    """Safely convert a cell value to a stripped string, or '' if null."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _is_blank_row(row: pd.Series) -> bool:
    """True if the first 9 columns (indices 0–8) are all empty.
    Rows where cols 0-2 are empty but a higher column has meaningful text
    (e.g. a sentence-only row like ',,,4.03. Maintain...') are NOT blank.
    """
    for ci in range(min(len(row), 9)):
        if _to_str(row.iloc[ci]):
            return False
    return True


def _is_equals_separator(row: pd.Series) -> bool:
    """True if col 0 starts with '=' (===== divider line)."""
    return _to_str(row.iloc[0]).startswith("=")


def _read_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read the file bytes into a pandas DataFrame with no header."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)
    else:
        try:
            df = pd.read_csv(
                io.StringIO(file_bytes.decode("utf-8-sig")), header=None, dtype=str
            )
        except Exception:
            df = pd.read_csv(
                io.StringIO(file_bytes.decode("latin-1")), header=None, dtype=str
            )
    return df


# ---------------------------------------------------------------------------
# Sentence detection heuristics
# ---------------------------------------------------------------------------

# Text that starts with these patterns is annotation noise, not a real sentence
_BAD_SENTENCE_STARTS = (
    "v2 ", "v2-", "v2:", "1)", "2)", "3)", "4)", "5)", "6)", "7)", "8)", "9)",
    "note:", "note -", "we can", "this way", "here,", "since ",
    "only signals", "at least", "condition", "synthesized",
    "clicking", "this sentence", "following is", "jeff, rajan",
    "reminder:", "important:", "todo", "using ", "if there is",
    "besides,", "a better version", "these analysis", "more importantly",
    "applies_to is used", "it seems", "so we can", "summary:",
    "how to ", "one way is", "another way", "i believe", "i am think",
    "what commit", "because of their roles",
    "primary_obligations", "humanity_001", "special_care_001",
    "this is a passive", "this is guessed", "not unfairly intervene follows",
    "not engage is a", "refrain from follows", "however introduces",
    "not give follows", "not influence follows",
    "reification", "these three are", "i don", "in this;",
    "and organizations participate",  # continuation fragment
)


def _looks_like_sentence(text: str) -> bool:
    """Return True if *text* looks like a real natural-language sentence."""
    if len(text) < 25:
        return False
    lower = text.lower().strip()
    # Must contain at least one lowercase letter (not ALL-CAPS labels)
    if not any(c.islower() for c in text):
        return False
    return not any(lower.startswith(p) for p in _BAD_SENTENCE_STARTS)


def _find_sentence_candidate(rows: List[pd.Series]) -> str:
    """
    Scan all cells in cols 3–12 across every row.
    Returns the first cell value that passes _looks_like_sentence().
    Falls back to the first non-empty value if none passes.
    """
    fallback = ""
    for row in rows:
        for ci in range(3, min(len(row), 13)):
            v = _to_str(row.iloc[ci])
            if not v:
                continue
            if _looks_like_sentence(v):
                return v
            if not fallback:
                fallback = v
    return fallback


# ---------------------------------------------------------------------------
# Triple extraction
# ---------------------------------------------------------------------------

def _extract_triples(rows: List[pd.Series]) -> List[Dict[str, str]]:
    """Return rows where subject, predicate, and object are all non-empty."""
    triples = []
    for row in rows:
        subj = _to_str(row.iloc[0])
        pred = _to_str(row.iloc[1]) if len(row) > 1 else ""
        obj  = _to_str(row.iloc[2]) if len(row) > 2 else ""
        if subj and pred and obj:
            triples.append({"subject": subj, "predicate": pred, "object": obj})
    return triples


# ---------------------------------------------------------------------------
# Sentence-detection-driven grouping
# ---------------------------------------------------------------------------

def _get_version_label(rows: List[pd.Series]) -> str:
    """Return col-3 of the first triple row in the block."""
    for row in rows:
        s = _to_str(row.iloc[0])
        p = _to_str(row.iloc[1]) if len(row) > 1 else ""
        o = _to_str(row.iloc[2]) if len(row) > 2 else ""
        if s and p and o:
            return _to_str(row.iloc[3]) if len(row) > 3 else ""
    return ""


def _build_sentence_groups(df: pd.DataFrame) -> List[List[Dict[str, Any]]]:
    """
    Split the dataframe into sentence groups.
    Each group is a list of version-dicts: {"label": str, "rows": [...]}

    Algorithm (sentence-detection-driven):
    1.  Walk rows; collect consecutive non-separator rows into sub-blocks.
        – '=' rows trigger a hard commit of the current group.
        – Blank rows delimit sub-blocks within a group.
    2.  For each sub-block:
        a.  If it contains a *real* sentence → commit current group, start
            a new group with this sub-block as Version 1.
        b.  Else if it has a *different* non-empty version label from the
            last version in the current group → append as a new version.
        c.  Else → merge its rows into the current group's last version
            (continuation / same version).
    """
    all_rows = [row for _, row in df.iterrows()]

    # --- Step 1: collect sub-blocks as events ---
    # events: either list[pd.Series] (sub-block) or "HARD" (== separator)
    events: List[Any] = []
    current: List[pd.Series] = []

    for row in all_rows:
        if _is_equals_separator(row):
            if current:
                events.append(current)
                current = []
            events.append("HARD")
        elif _is_blank_row(row):
            if current:
                events.append(current)
                current = []
        else:
            # Detect sentence-header rows: no triples (cols 0-2 empty) but
            # a real sentence exists in cols 3-12.  These rows mark the start
            # of a new clause even when no blank row precedes them.
            c0 = _to_str(row.iloc[0])
            c1 = _to_str(row.iloc[1]) if len(row) > 1 else ""
            c2 = _to_str(row.iloc[2]) if len(row) > 2 else ""
            if not (c0 and c1 and c2):
                sent = ""
                for ci in range(3, min(len(row), 13)):
                    v = _to_str(row.iloc[ci])
                    if v:
                        sent = v
                        break
                if sent and _looks_like_sentence(sent):
                    # Sentence-header row → flush current sub-block first
                    if current:
                        events.append(current)
                        current = []
            current.append(row)
    if current:
        events.append(current)

    # --- Step 2: group events into sentence groups ---
    sentence_groups: List[List[Dict[str, Any]]] = []
    cur_group: List[Dict[str, Any]] = []

    def _commit():
        nonlocal cur_group
        if cur_group:
            sentence_groups.append(cur_group)
            cur_group = []

    for event in events:
        if event == "HARD":
            _commit()
            continue

        sub_block: List[pd.Series] = event
        sent_cand = _find_sentence_candidate(sub_block)
        has_real  = _looks_like_sentence(sent_cand)
        ver_label = _get_version_label(sub_block)

        if has_real:
            # Real sentence → always starts a brand-new group
            _commit()
            cur_group = [{"label": ver_label, "rows": list(sub_block)}]
        elif ver_label and cur_group and ver_label != cur_group[-1]["label"]:
            # Different non-empty label → new version of current group
            cur_group.append({"label": ver_label, "rows": list(sub_block)})
        else:
            # Continuation: merge into last version (or seed a new group)
            if cur_group:
                cur_group[-1]["rows"].extend(sub_block)
            else:
                cur_group = [{"label": ver_label, "rows": list(sub_block)}]

    _commit()
    return sentence_groups


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file_rich(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Enhanced parser: returns sentence groups, each with one or more versions.

    Return structure:
    [
      {
        "group_id": 1,
        "sentence_text": "It is not intended ...",
        "selected_version_id": "1_1",
        "versions": [
          {
            "version_id": "1_1",
            "version_label": "By me",
            "sentence_candidate": "It is not intended ...",
            "triples": [
              {"id": "1_1_1", "subject": "...", "predicate": "...", "object": "..."}
            ]
          },
          ...
        ]
      },
      ...
    ]
    """
    df = _read_dataframe(file_bytes, filename)
    while df.shape[1] < 8:
        df[df.shape[1]] = ""

    raw_groups = _build_sentence_groups(df)

    groups: List[Dict[str, Any]] = []
    group_id = 1

    for raw_versions in raw_groups:
        version_objects: List[Dict[str, Any]] = []
        best_sentence = ""

        for vi, ver in enumerate(raw_versions):
            triples_raw = _extract_triples(ver["rows"])
            if not triples_raw:
                continue  # skip versions with no usable triples

            sent_cand = _find_sentence_candidate(ver["rows"])

            # Keep the best "real" sentence across versions for this group
            if not best_sentence and _looks_like_sentence(sent_cand):
                best_sentence = sent_cand

            version_objects.append({
                "version_id":        f"{group_id}_{vi + 1}",
                "version_label":     ver["label"] if ver["label"] else f"Version {vi + 1}",
                "sentence_candidate": sent_cand,
                "triples": [
                    {
                        "id":        f"{group_id}_{vi + 1}_{j + 1}",
                        "subject":   t["subject"],
                        "predicate": t["predicate"],
                        "object":    t["object"],
                    }
                    for j, t in enumerate(triples_raw)
                ],
            })

        if not version_objects:
            continue

        # Fallback sentence: first non-empty candidate across all versions
        if not best_sentence:
            for v in version_objects:
                if v["sentence_candidate"]:
                    best_sentence = v["sentence_candidate"]
                    break

        groups.append({
            "group_id":           group_id,
            "sentence_text":      best_sentence,
            "selected_version_id": version_objects[0]["version_id"],
            "versions":           version_objects,
        })
        group_id += 1

    return groups


def parse_file(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Legacy flat parser — kept for backward compatibility.
    Collapses each group to its first version.
    """
    groups = parse_file_rich(file_bytes, filename)
    sentences = []
    for sid, g in enumerate(groups, start=1):
        first_version = g["versions"][0]
        triples = [
            {
                "id":           f"{sid}_{i + 1}",
                "subject":      t["subject"],
                "predicate":    t["predicate"],
                "object":       t["object"],
                "grade":        10.0,  # Default grade for gold triples
                "author":       None,
                "completeness": None,
                "relation":     10,
                "suggestions":  [],
                "votes":        {},
            }
            for i, t in enumerate(first_version["triples"])
        ]
        sentences.append({
            "id":             sid,
            "text":           g["sentence_text"],
            "suggestion":     "",
            "sentence_grade": None,
            "triples":        triples,
        })
    return sentences
