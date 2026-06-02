import csv
import re
from pathlib import Path

SEP_RE = re.compile(r"^=+$")

def clean_cell(text: str) -> str:
    return text.strip()

def is_sentence_candidate(text: str) -> bool:
    text = clean_cell(text)
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith(("v2 -", "since ", "here,", "we can ", "this ")):
        return False
    return len(text.split()) >= 5 and any(p in text for p in ".?!")

def parse_original_csv(file_path):
    sentences = {}
    current_sentence = ""
    triples = []
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        rows = []
        for row in reader:
            rows.append([clean_cell(x) for x in row])

    for ridx, row in enumerate(rows):
        while len(row) <= 7:
            row.append("")

        c0, c1, c2 = row[0], row[1], row[2]
        sentence_candidate = row[7]

        if SEP_RE.match(c0):
            if current_sentence and triples:
                sentences[current_sentence] = triples
            current_sentence = ""
            triples = []
            continue

        if not any(row):
            continue

        if is_sentence_candidate(sentence_candidate):
            if current_sentence and triples:
                sentences[current_sentence] = triples
            current_sentence = sentence_candidate
            triples = []
            print(f"Found sentence: {current_sentence}")
            continue

        if c0 and c1 and c2 and not SEP_RE.match(c0):
            triples.append((c0, c1, c2))

    if current_sentence and triples:
        sentences[current_sentence] = triples
    return sentences

def parse_generated_csv(file_path):
    sentences = {}
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sentence = row['source_sentence'].strip()
            triple = (row['subject'].strip(), row['predicate'].strip(), row['object'].strip())
            if sentence not in sentences:
                sentences[sentence] = []
            sentences[sentence].append(triple)
    return sentences

def main():
    original_path = Path('long_coe_tuples(Rajan_Golden_dataset).csv')
    generated_path = Path('backend/gold_benchmark.csv')

    original = parse_original_csv(original_path)
    generated = parse_generated_csv(generated_path)

    print(f"Original sentences: {len(original)}")
    print(f"Generated sentences: {len(generated)}")

    missing_sentences = set(original.keys()) - set(generated.keys())
    extra_sentences = set(generated.keys()) - set(original.keys())

    if missing_sentences:
        print(f"Missing sentences: {len(missing_sentences)}")
        for s in missing_sentences:
            print(f"  {s}")
    else:
        print("All sentences present.")

    if extra_sentences:
        print(f"Extra sentences: {len(extra_sentences)}")
        for s in extra_sentences:
            print(f"  {s}")

    # Check triples
    all_original_triples = set()
    for triples in original.values():
        all_original_triples.update(triples)

    all_generated_triples = set()
    for triples in generated.values():
        all_generated_triples.update(triples)

    missing_triples = all_original_triples - all_generated_triples
    extra_triples = all_generated_triples - all_original_triples

    print(f"Original triples: {len(all_original_triples)}")
    print(f"Generated triples: {len(all_generated_triples)}")

    if missing_triples:
        print(f"Missing triples: {len(missing_triples)}")
        for t in missing_triples:
            print(f"  {t}")
    else:
        print("All triples present.")

    if extra_triples:
        print(f"Extra triples: {len(extra_triples)}")
        for t in extra_triples:
            print(f"  {t}")

if __name__ == '__main__':
    main()