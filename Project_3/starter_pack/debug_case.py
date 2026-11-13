import json
import sys

import final_judge as fj

case_id, side = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "edited")
rows = [json.loads(l) for l in open("dev_pairs.jsonl", encoding="utf-8") if l.strip()]
criterion = open("JUDGE1_CRITERION.md", encoding="utf-8").read()
policy = open("policy.md", encoding="utf-8").read()
fj.prepare(criterion, policy, rows)

r = next(x for x in rows if x["case_id"] == case_id)
reply = r[side]
lang = r["orig_lang"] if side == "original" else r["lang"]
question = r["question_original"] if side == "original" else r["question"]
fields = dict(criterion=criterion.strip(), policy=policy.strip(), lang=lang, question=question, reply=reply)

print("=== REPLY ===\n" + reply)
analysis = fj.complete(fj.ANALYZE.format(examples=fj._examples_text(), **fields))
print("\n=== CALL 1 (analysis) ===\n" + analysis)
if fj._verdict(analysis) != "pass":
    check = fj.complete(fj.VERIFY.format(analysis=analysis[-3000:], **fields))
    print("\n=== CALL 2 (verify) ===\n" + check)
print("\n=== FINAL ===", fj.judge(question, reply, lang, criterion, policy))
