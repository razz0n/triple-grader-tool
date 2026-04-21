import sys
sys.path.insert(0, r'c:\ObsidianRajan\RajanBrains\09 ATTACHMENTS\CSU\Ontology tool\backend')
from parser import parse_file

with open(r'c:\ObsidianRajan\RajanBrains\09 ATTACHMENTS\CSU\Ontology tool\long_coe_tuples(Rajan_Golden_dataset).csv', 'rb') as f:
    data = f.read()

result = parse_file(data, 'test.csv')
print(f'Total sentences: {len(result)}')
for s in result[:4]:
    print()
    print(f'--- Sentence {s["id"]} ---')
    print(f'Text: {s["text"][:120]}')
    print(f'Triples ({len(s["triples"])}):')
    for t in s['triples']:
        print(f'  [{t["id"]}] {t["subject"]} | {t["predicate"]} | {t["object"]}')

print()
print('--- Also test Golden dataset ---')
with open(r'c:\ObsidianRajan\RajanBrains\09 ATTACHMENTS\CSU\Ontology tool\long_coe_tuples(Golden_dataset).csv', 'rb') as f:
    data2 = f.read()
result2 = parse_file(data2, 'golden.csv')
print(f'Total sentences: {len(result2)}')
for s in result2[:2]:
    print(f'  Sentence {s["id"]}: {len(s["triples"])} triples | text: {s["text"][:80]}')
