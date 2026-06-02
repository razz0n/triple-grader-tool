"""Test script to debug evaluation issues."""
import sys
sys.path.insert(0, r'c:\ObsidianRajan\RajanBrains\09 ATTACHMENTS\CSU\Ontology tool\backend')

from parser import parse_file
from openie_eval import evaluate_session, run_openie

# Load a session using the parser
with open(r'c:\ObsidianRajan\RajanBrains\09 ATTACHMENTS\CSU\Ontology tool\long_coe_tuples(Golden_dataset).csv', 'rb') as f:
    data = f.read()

sentences = parse_file(data, 'golden.csv')
print(f"Loaded {len(sentences)} sentences from parser")

# Check first sentence structure
s = sentences[0]
print(f"\n--- Sentence 1 ---")
print(f"Text: {s['text'][:100]}...")
print(f"Triples: {len(s['triples'])}")
for t in s['triples'][:3]:
    print(f"  {t['subject']} | {t['predicate']} | {t['object']} | grade={t.get('grade')}")

# Create a mock session structure
session = {
    "session_id": "test-123",
    "source_filename": "golden.csv",
    "sentences": sentences
}

# Test run_openie
print("\n--- Testing run_openie ---")
try:
    pred_results = run_openie(sentences[:5])  # Limit to first 5 sentences for debugging
    print(f"OpenIE extracted triples for {len(pred_results)} sentences")
    for sid, triples in pred_results.items():
        print(f"  Sentence {sid}: {len(triples)} predicted triples")
        for t in triples:
            print(f"    {t['subject']} | {t['predicate']} | {t['object']}")
except Exception as e:
    print(f"Error in run_openie: {e}")
    import traceback
    traceback.print_exc()

# Test full evaluation
print("\n--- Testing evaluate_session ---")
try:
    # Limit to first 5 sentences for debugging
    limited_session = {
        "session_id": "test-123",
        "source_filename": "golden.csv",
        "sentences": sentences[:5]
    }
    result = evaluate_session(limited_session, match_mode="soft")
    print(f"Evaluation completed!")
    print(f"  Macro: P={result['macro']['precision']}, R={result['macro']['recall']}, F1={result['macro']['f1']}")
    print(f"  Micro: P={result['micro']['precision']}, R={result['micro']['recall']}, F1={result['micro']['f1']}")
    print(f"  Sentences evaluated: {len(result['per_sentence'])}")
    
    # Show details for all sentences
    for i, sent_result in enumerate(result['per_sentence']):
        print(f"\n  Sentence {i+1} details:")
        print(f"    Text: {sent_result['sentence_text'][:80]}...")
        print(f"    Gold triples: {sent_result['n_gold']}")
        print(f"    Pred triples: {sent_result['n_pred']}")
        print(f"    TP: {sent_result['true_positives']}")
        print(f"    Precision: {sent_result['precision']}")
        print(f"    Recall: {sent_result['recall']}")
        print(f"    F1: {sent_result['f1']}")
    
    # Save full results to a file
    import json
    with open('eval_results.json', 'w') as f:
        json.dump(result, f, indent=2)
    print("\nFull results saved to eval_results.json")
except Exception as e:
    print(f"Error in evaluate_session: {e}")
    import traceback
    traceback.print_exc()