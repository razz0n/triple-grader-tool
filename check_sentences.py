import csv

sentences = {}
with open('backend/gold_benchmark.csv') as f:
    for row in csv.DictReader(f):
        s = row['source_sentence']
        t = (row['subject'], row['predicate'], row['object'])
        if s not in sentences:
            sentences[s] = []
        sentences[s].append(t)

print('Sentence count:', len(sentences))
for s in sentences:
    print(repr(s[:100] + '...' if len(s) > 100 else s))