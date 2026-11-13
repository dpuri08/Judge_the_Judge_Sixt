
Submission: Project 3, Judge the Judge (Dpuri08)
Authors
Team name: Dpuri08

Project: Project 3: Judge the Judge

Problem and approach
An LLM judge checks one customer-support reply at a time against a criterion and the company policy. It must fail a reply after a small harmful edit (a wrong number, a dropped condition or hedge, a wrong policy detail) and pass it after a harmless edit (opener, filler, reordering, translation). The same code must work for a criterion it has never seen; only the criterion text and the example pairs change.

Key finding: the baseline, and our first attempt, failed many good original replies (our first attempt: 61/226). The score needs the original to pass for both catch and keep, so false alarms on good replies were the biggest loss.

Main idea: reason claim by claim, allow a FAIL only with evidence, and check every FAIL a second time.

prepare() builds up to 5 contrastive examples from the supplied dev pairs (a PASS reply next to its minimally edited FAIL reply, plus the reason) and 3 harmless variants that stay PASS.
Call 1: the model lists each claim, translates it to English, quotes the policy sentence on the same topic, and labels it. A FAIL needs a quoted policy sentence. Brevity, translation, order and politeness are explicitly not violations.
Call 2, only after a FAIL: an independent verifier overturns false alarms (misread policy, wrong topic, a reply that is only concise or translated).
At most 2 calls per reply, temperature 0, no hand-written rules, nothing criterion-specific in the code.

Why it beats the baseline (in short):

The baseline asks for a one-word PASS/FAIL with no reasoning, so it fails many good replies and misses small changes.
Our judge makes the AI show its reasoning claim by claim, so it can see numbers, conditions and hedges.
A FAIL must quote the policy sentence it breaks, which stops false alarms on good replies.
Every FAIL gets a second check, which removes the remaining false alarms.
Assumptions: the judge sees one reply at a time, never the pair or the edit type. Labels come from how the pairs were built. The policy fits in the prompt.

Models and why
We used one model, the one provided through the hackathon endpoint. We did not compare models; we spent the time on the judge design (see Results).

Model	Open-weight or closed	Where it runs	Main metric(s)	Cost and time per item	Chosen?
claude-haiku-4.5	closed	API (hackathon-provided OpenAI-compatible endpoint)	Judge 1 held-out combined 0.906; surprise held-out combined 0.933	about 1.1 s per reply wall-clock (80 replies in 90.5 s, run in parallel by run_judge.py); 1 call when it passes, 2 when call 1 fails	yes: the provided model; fast and cheap enough for 2 reasoning calls per reply
Settings: JUDGE_LLM_MAX_TOKENS raised to 900 inside the judge so the model can reason before its verdict; temperature 0.

Results
What the score means (plain words). Each test case is a good reply and a slightly changed copy of it.

Catch: the judge must FAIL the changed copy when the change is harmful. Higher = fewer missed mistakes.
Keep: the judge must PASS the changed copy when the change is harmless. Higher = fewer false alarms.
Combined: the two scores averaged in a way that punishes a judge that is strong on one and weak on the other. A judge that fails everything, or passes everything, scores 0.
Original pass: the share of good replies the judge passes. This drives catch and keep, so it matters most.
Baseline: the simple starting judge, scored the same way. Our score is compared against it.
Metric: combined = harmonic mean of catch (harmful edits caught) and keep (harmless edits left alone), each averaged over edit types. Held-out = 3 of 9 source replies held back and not used as examples (split_holdout.py), so it estimates performance on unseen sources.

Judge 1 (does the reply over-promise?)

combined	catch	keep	original pass
Baseline (full dev, 226)	0.697	0.592	0.847	n/a
Our first attempt (full dev)	0.707	0.674	0.742	0.730
Ours (full dev, 226)	0.908	0.864	0.958	0.965
Ours (held-out sources, 77)	0.906	0.844	0.977	1.000
Consistency: two runs gave the same verdict on 152/152 replies (kappa 1.000).

Surprise criterion (does the reply state the policy correctly?), code unchanged

combined	catch	keep	original pass
Baseline (surprise dev, 73)	0.652	0.600	0.715	0.795
Ours (surprise dev, 73; examples from the same file)	0.917	0.900	0.935	0.945
Ours (held-out sources, 25)	0.933	0.917	0.950	1.000
On the surprise criterion, the unchanged recipe beats the baseline by +0.265 combined (0.917 vs 0.652 on the same 73 cases). The baseline catches only 1/10 dropped conditions there (ours: 0.80) and keeps only 3/8 translations (ours: 0.875).

Test set: to be added after 16:00.

What did not work

One-word answers with 3-prompt majority voting (0.707): without room to reason, the model failed 27% of good replies.
Few-shot examples without a reason: near-identical PASS and FAIL replies confused the model. Side-by-side contrasts with a stated reason fixed this.
A stricter verifier raised dropped-condition catch (0.70 → 0.80) but failed more harmless edits; the held-out score fell from 0.906 to 0.887, so we reverted it.
Scores on the small fast subset varied between 0.88 and 0.95 for the same code, so we decided on full dev and held-out only.
Limits

Dropped conditions remain the weakest type (about 0.70 to 0.80 catch): the verifier sometimes accepts them as "concise".
Held-out sets are small (9 source replies in total; 1 to 5 cases per edit type in the surprise held-out set), so read the numbers as roughly ±0.05.
Labels come from construction, not human annotators. All data is synthetic car-rental replies.
One model only; no comparison with other models.
How to run
Python 3.12, standard library only (nothing to install). From Project_3/starter_pack/.

Environment variables (names only): JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY, JUDGE_LLM_MODEL.

Judge 1, full dev:

python run_judge.py --judge final_judge.py --pairs dev_pairs.jsonl --criterion JUDGE1_CRITERION.md --policy policy.md --dev dev_pairs.jsonl --out v2_full.csv
python score.py v2_full.csv dev_pairs.jsonl --baseline baseline_dev_verdicts.csv
Judge 1, held-out sources:

python split_holdout.py dev_pairs.jsonl 3
python run_judge.py --judge final_judge.py --pairs dev_holdout.jsonl --criterion JUDGE1_CRITERION.md --policy policy.md --dev dev_train.jsonl --out v2_holdout.csv
python score.py v2_holdout.csv dev_holdout.jsonl
Surprise criterion, held-out sources (run the split from inside surprise/):

cd surprise && python ../split_holdout.py dev_pairs.jsonl 3 && cd ..
python run_judge.py --judge final_judge.py --pairs surprise/dev_holdout.jsonl --criterion surprise/CRITERION.md --policy policy.md --dev surprise/dev_train.jsonl --out surprise_v2_holdout.csv
python score.py surprise_v2_holdout.csv surprise/dev_holdout.jsonl
Inspect one case (prints the model's full reasoning):

python debug_case.py J1D-0101 original
Demo UI (then open http://localhost:8000):

python demo_server.py
python demo_server.py --criterion surprise/CRITERION.md --dev surprise/dev_pairs.jsonl
Demo
submission/slides.pdf: screenshots of our solution, meaning the running local demo and how we tried to solve the problem.

The local demo (demo.html + demo_server.py) shows the verdict, the claim-by-claim analysis with quoted policy sentences, and the verification step. One way to show the criterion switch: judge the reply "charged at double the daily rate" under both criteria. Judge 1 should pass it (not an over-promise); the surprise criterion should fail it (misstates the policy).

Next steps
Dropped conditions: add a targeted check: for each promise, list the conditions the policy attaches to it and confirm each is present in the reply.
Model comparison: run the same held-out sets with other models, possibly a stronger model only for the verification call.
More and real data: check against human-labelled replies and real support traffic, not only synthetic pairs.
Use at SIXT: a pre-send check for agent and AI-drafted replies in every language. It flags replies that promise more (or state less) than policy and shows the policy sentence. When policy changes, only the policy and criterion text change, not the code.
