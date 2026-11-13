"""Split dev_pairs.jsonl by source_id into a train part (for --dev) and a held-out part (to score).

    python split_holdout.py dev_pairs.jsonl 3
writes dev_train.jsonl and dev_holdout.jsonl (holdout = 3 source_ids, chosen with a fixed seed).
"""
import json
import random
import sys

path, k = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3
rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
sources = sorted({r["source_id"] for r in rows})
held = set(random.Random(7).sample(sources, k))
with open("dev_train.jsonl", "w", encoding="utf-8") as tr, open("dev_holdout.jsonl", "w", encoding="utf-8") as ho:
    for r in rows:
        (ho if r["source_id"] in held else tr).write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"held-out sources: {sorted(held)}")
print(f"train rows: {sum(r['source_id'] not in held for r in rows)}, holdout rows: {sum(r['source_id'] in held for r in rows)}")
