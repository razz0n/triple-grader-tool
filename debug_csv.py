import csv

with open('long_coe_tuples(Rajan_Golden_dataset).csv') as f:
    reader = csv.reader(f)
    for i, row in enumerate(reader):
        if i < 15:
            print(f'Row {i}: len={len(row)}')
            print(f'  Subject: {row[0][:30] if row[0] else ""}')
            print(f'  Pred: {row[1][:20] if len(row) > 1 and row[1] else ""}')
            print(f'  Obj: {row[2][:20] if len(row) > 2 and row[2] else ""}')
            print(f'  Col 8 (Sentence): {row[8][:40] if len(row) > 8 and row[8] else ""}')
            print(f'  Col 9 (Note): {row[9][:40] if len(row) > 9 and row[9] else ""}')
            print()
