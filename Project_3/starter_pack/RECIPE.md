ur recipe for building an LLM judge
Team Dpuri08 · Project 3: Judge the Judge

An LLM judge reads one customer-support reply and decides: does it follow the rule (PASS) or not (FAIL)? This page explains, step by step, how we built ours, so anyone can repeat it for a new rule. All numbers come from score.py. Scores go from 0 to 1; higher is better.

Step 1. Diagnose
First, find out where the judge goes wrong.

What we looked at:

diagnose.py, to see which kinds of edits and which languages fail most.
debug_case.py, which prints the AI's full reasoning for one reply, so we can see why it made a mistake.
What we found:

The starting judge (baseline) missed most removed conditions (28 of 30 wrong), half of the removed hedges ("usually" changed to "always"), and often rejected replies whose sentences were only reordered. French and German were the weakest languages.
Our first attempt asked the AI for a one-word answer three times and took a vote. It rejected 61 of 226 good replies (about 1 in 4). This was the biggest problem: a case only counts as correct if the good reply passes, so every false alarm on a good reply costs points.
Reading the AI's reasoning showed three typical mistakes:
"We will try to reserve a seat" was treated as a promise. One good English reply was failed 8 times because of this.
A smaller number was treated as harmless, even when it is better for the customer ("up to 5 days" instead of "up to 10 days").
A dropped condition was excused as the reply simply being "short".
Lesson: fix false alarms on good replies first. They hurt the score the most.

Step 2. Split: rules vs. LLM
We use no fixed rules. The AI does all the checking.

Whether a number, condition or promise is wrong depends on the rule, the policy, the language and the context. A fixed rule such as "fail every reply that says always" would break on new cases and new languages. So nothing about car rental, numbers or edit types is written into the code. The rule text and the examples are inputs, which is why the same code also works for a brand-new rule.

Step 3. Improve the LLM part
Three simple ideas (in final_judge.py, at most 2 AI calls per reply):

Show good vs. bad examples. From the example file, we build up to 5 pairs: a correct reply next to an almost identical wrong one, plus one sentence explaining why the wrong one fails. We also show 3 harmless changes (a greeting, a translation) that still pass.
Check sentence by sentence, with proof. The AI lists every claim in the reply, translates it to English, and finds the matching sentence in the policy. It may only say FAIL if it can quote the policy sentence that is broken. Shorter replies, translations, a different word order and polite phrases are never a reason to fail.
Double-check every FAIL. When the first check says FAIL, a second check reviews it and removes false alarms (for example when the AI misread the policy or picked the wrong topic). A PASS needs only one check.
We also let the AI write out its reasoning before the final answer (an answer of up to 900 tokens instead of a single word), and we read the final VERDICT: PASS or VERDICT: FAIL line from its answer.

Step 4. Verify
Measure on the full dev set and on replies the judge has never seen.

"Unseen replies" means: we held back 3 of the 9 source replies (split_holdout.py), did not use them as examples, and scored only those. This is the fairest guess for new test cases.

combined	catch	keep	good replies passed
Baseline (full dev)	0.697	0.592	0.847	n/a
Our first attempt (full dev)	0.707	0.674	0.742	0.730
Ours (full dev, 226 cases)	0.908	0.864	0.958	0.965
Ours (unseen replies, 77 cases)	0.906	0.844	0.977	1.000
catch = share of harmful edits caught; keep = share of harmless edits left alone.
By language (combined): German 0.909, English 0.869, Spanish 0.883, French 0.934, Italian 0.883.
By edit type: removed hedges 0.95, wrong policy details 0.92, wrong numbers 0.89, removed conditions 0.70 (caught); greetings and removed padding 1.00, reordering 0.97, filler 0.93, translation 0.89 (kept).
Same answer twice: two runs gave the same verdict on 152 of 152 replies.
Speed: about 1 second per reply when run in parallel.
Check: the score on unseen replies (0.906) is almost the same as on the full set (0.908). So the improvement is real, not a result of the judge seeing its own test cases.

Surprise criterion
What did we change? Nothing in the code. We only changed the inputs: --criterion surprise/CRITERION.md --dev surprise/dev_pairs.jsonl

The new rule asks "is every fact correct?", so mistakes in both directions count, for example "double the daily rate" (worse for the customer). The judge handled this because the rule text is in its instructions and the examples come from the new example file.

combined	catch	keep	good replies passed
Baseline (73 cases)	0.652	0.600	0.715	0.795
Ours, code unchanged (73 cases)*	0.917	0.900	0.935	0.945
Ours, code unchanged (unseen replies, 25 cases)	0.933	0.917	0.950	1.000
* Slightly flattering, because the examples come from the same file. The unseen set is small (1 to 5 cases per edit type), so read it as roughly 0.90, give or take 0.05.

What did not work
One-word answers with 3 votes (score 0.707): without room to think, the AI rejected about 1 in 4 good replies.
Examples without a reason: a correct and a wrong reply that looked almost the same confused the AI. Adding one sentence on why fixed it.
A stricter double-check: it caught more removed conditions (0.70 → 0.80) but rejected more harmless replies. The score on unseen replies dropped (0.906 → 0.887), so we went back.
Tuning on the small "fast" set: the same code scored anywhere from 0.88 to 0.95 there, so it was too noisy to decide anything. We only trusted the full set and the unseen replies.
Still weak: noticing a missing condition (for example "if the car is returned undamaged" left out). It is caught 7 to 8 times out of 10. The double-check sometimes accepts it as the reply just being short.