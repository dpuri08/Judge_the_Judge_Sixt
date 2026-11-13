# Submission: Project 3 — Judge the Judge

## Authors
**Team name:** Dpuri08

**Project:** Project 3: Judge the Judge

## Problem and approach

We built an LLM judge that evaluates one customer-support reply at a time against a criterion and company policy. It must catch harmful edits (for example, a wrong number, a dropped condition or hedge, or an incorrect policy detail) while allowing harmless edits such as different openers, filler, reordering, and translation. The same code must work with an unseen criterion; only the criterion text and example pairs change.

Our key finding was that false alarms on good replies were the main weakness: our first attempt failed 61 of 226 good original replies. We therefore designed the judge to reason claim by claim, require policy evidence for every FAIL, and independently verify each proposed FAIL.

- `prepare()` builds up to five contrastive PASS/FAIL examples from the supplied development pairs, including the reason for each difference, plus three harmless PASS variants.
- **Call 1:** lists the reply's claims, translates them to English, quotes the relevant policy sentence, and labels each claim. A FAIL requires a quoted policy sentence. Brevity, translation, ordering, and politeness are explicitly not violations.
- **Call 2:** runs only after a proposed FAIL. An independent verifier can overturn false alarms, such as a policy misreading, a topic mismatch, or a reply that is merely concise or translated.
- The judge uses at most two calls per reply, temperature 0, and no hand-written or criterion-specific rules.

**Assumptions:** The judge sees one reply at a time, not the original/edited pair or edit type. Labels are based on how the pairs were constructed, and the policy fits in the prompt.

## Models and why

We used the model provided through the hackathon endpoint. We did not compare models; we focused on the judge design. Claude Haiku 4.5 was fast enough for a two-call verification design.

| Model | Open-weight or closed | Where it runs | Main metric(s) | Cost and time per item | Chosen? |
| --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Closed | Hackathon-provided OpenAI-compatible API endpoint | Judge 1 held-out combined: 0.906; surprise held-out combined: 0.933 | About 1.1 seconds per reply (80 replies in 90.5 seconds, parallel run); 1 call for PASS, up to 2 for FAIL | Yes — provided model; fast and inexpensive enough for the verification call |

**Settings:** Temperature 0. `JUDGE_LLM_MAX_TOKENS` was raised to 900 inside the judge to give the model enough room to reason before returning its verdict.

## Results

**Metric:** Combined is the harmonic mean of catch (harmful edits caught) and keep (harmless edits left alone), with each averaged over edit types. Held-out results use three of the nine source replies withheld from examples (`split_holdout.py`), to estimate performance on unseen sources.

### Judge 1 — Does the reply over-promise?

| Evaluation | Combined | Catch | Keep | Original pass |
| --- | ---: | ---: | ---: | ---: |
| Baseline (full dev, 226 cases) | 0.697 | 0.592 | 0.847 | n/a |
| First attempt (full dev) | 0.707 | 0.674 | 0.742 | 0.730 |
| Our judge (full dev, 226 cases) | 0.908 | 0.864 | 0.958 | 0.965 |
| Our judge (held-out sources, 77 cases) | 0.906 | 0.844 | 0.977 | 1.000 |

Two runs produced identical verdicts on 152/152 replies (Cohen's kappa: 1.000).

### Surprise criterion — Does the reply state the policy correctly?

The code was unchanged; only the criterion and examples changed.

| Evaluation | Combined | Catch | Keep | Original pass |
| --- | ---: | ---: | ---: | ---: |
| Baseline (surprise dev, 73 cases) | 0.652 | 0.600 | 0.715 | 0.795 |
| Our judge (surprise dev, 73 cases) | 0.917 | 0.900 | 0.935 | 0.945 |
| Our judge (held-out sources, 25 cases) | 0.933 | 0.917 | 0.950 | 1.000 |

On the surprise criterion, the unchanged recipe improved the combined score by 0.265 over the baseline on the same 73 cases (0.917 vs. 0.652). The baseline caught only 1/10 dropped conditions; our judge's catch rate for these was 0.80. The baseline kept only 3/8 translations; our judge kept 0.875.

**What did not work**
- One-word answers with three-prompt majority voting scored 0.707; without room to reason, the model failed 27% of good replies.
- Few-shot examples without reasons confused the model because the PASS and FAIL replies were nearly identical. Side-by-side contrasts with an explicit reason worked better.
- A stricter verifier improved dropped-condition catch from 0.70 to 0.80, but caused more false alarms. Held-out combined fell from 0.906 to 0.887, so we reverted it.
- Scores on a small fast subset varied from 0.88 to 0.95 for the same code; we therefore report full-dev and held-out results.

**Limits**
- Dropped conditions remain the weakest edit type, with catch around 0.70–0.80; the verifier sometimes accepts them as concise wording.
- Held-out sets are small: nine source replies overall, and only 1–5 cases per edit type in the surprise held-out set. Treat the results as approximate (roughly ±0.05).
- Labels come from pair construction, not human annotators. All data is synthetic car-rental support replies.
- We used one model and did not compare it with other models.

The test-set results were not yet available when this submission was prepared.

## How to run

**Environment:** Python 3.12; standard library only (nothing to install). Run commands from `Project_3/starter_pack/`.

**Environment variables (names only):** `JUDGE_LLM_BASE_URL`, `JUDGE_LLM_API_KEY`, `JUDGE_LLM_MODEL`.

**Judge 1 — full development set**
```bash
python run_judge.py --judge final_judge.py --pairs dev_pairs.jsonl --criterion JUDGE1_CRITERION.md --policy policy.md --dev dev_pairs.jsonl --out v2_full.csv
python score.py v2_full.csv dev_pairs.jsonl --baseline baseline_dev_verdicts.csv
```

**Judge 1 — held-out sources**
```bash
python split_holdout.py dev_pairs.jsonl 3
python run_judge.py --judge final_judge.py --pairs dev_holdout.jsonl --criterion JUDGE1_CRITERION.md --policy policy.md --dev dev_train.jsonl --out v2_holdout.csv
python score.py v2_holdout.csv dev_holdout.jsonl
```

**Surprise criterion — held-out sources** (run the split from inside `surprise/`)
```bash
cd surprise
python ../split_holdout.py dev_pairs.jsonl 3
cd ..
python run_judge.py --judge final_judge.py --pairs surprise/dev_holdout.jsonl --criterion surprise/CRITERION.md --policy policy.md --dev surprise/dev_train.jsonl --out surprise_v2_holdout.csv
python score.py surprise_v2_holdout.csv surprise/dev_holdout.jsonl
```

**Inspect one case and run the demo**
```bash
python debug_case.py J1D-0101 original
python demo_server.py
# Open http://localhost:8000
```

To run the demo with the surprise criterion:
```bash
python demo_server.py --criterion surprise/CRITERION.md --dev surprise/dev_pairs.jsonl
```

## Demo

`submission/slides.pdf` — five slides covering the problem, starting point, approach, results, and reproduction steps.

The local demo (`demo.html` + `demo_server.py`) displays the verdict, claim-by-claim analysis with quoted policy sentences, and the verification step. To demonstrate criterion switching, judge the reply “charged at double the daily rate” under both criteria: Judge 1 should PASS it (it is not an over-promise), while the surprise criterion should FAIL it (it misstates the policy).

## Next steps

- **Dropped conditions:** Add a targeted check that lists the conditions attached to each policy promise and confirms that every condition appears in the reply.
- **Model comparison:** Evaluate other models on the same held-out sets; consider using a stronger model only for verification.
- **More realistic evaluation:** Test with human-labelled replies and real customer-support traffic, rather than only synthetic pairs.
- **Potential SIXT use:** Run the judge before sending agent-written or AI-drafted replies in any language. It could flag promises that exceed policy (or policy details stated incorrectly) and show the supporting policy sentence. When policy changes, update the policy and criterion text rather than the code.
