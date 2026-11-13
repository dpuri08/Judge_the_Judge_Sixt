# Our recipe for building an LLM judge

Fill this in as you go. It is what you hand in, next to your code: a repeatable recipe someone else could follow
for a criterion they have never seen. Keep each step short. Numbers come from `score.py`.

## Step 1. Diagnose
What did you look at, and where does the baseline fail? (edit types, languages, a few example misses)

- Baseline diagnosis (`baseline_dev_verdicts.csv`): condition removals were the largest failure (28/30 wrong),
  followed by hedge removals (10/20); harmless sentence reorders were also often rejected (8/30). The shipped
  report shows weaker catch/keep slices in French and German. Examples include dropping the branch-open condition
  in German and dropping “según disponibilidad” in Spanish; “usually” → “always” is missed in English.
- Check before moving on: focus on preserving qualifiers and conditions while accepting harmless wording changes.

## Step 2. Split: rules vs. LLM
No criterion-independent regex safely determines whether a number, condition, or promise is wrong: these depend
on the supplied criterion, policy, language, and context. `final_judge.py` therefore sends those semantic checks
to the model rather than hard-coding Judge 1 terms or numbers. A future rule can be added only when it is derived
from the current inputs and validated against harmless examples.

- Check: each rule is tested on dev and never fails a harmless edit.

## Step 3. Improve the LLM part
`final_judge.py` gives a structured policy comparison, explicitly calls out omissions, scope, conditions,
quantities and certainty, and asks the model to preserve multilingual nuance. `prepare()` selects balanced labelled
single-reply examples dynamically; two differently focused calls vote conservatively. The judge uses no pair fields
or cross-call state and is limited to two calls per reply.

- Check: catch goes up on dev without keep going down.

## Step 4. Verify
Before and after, on the full dev set and per language.

| | combined | catch | keep |
|---|---|---|---|
| Baseline | 0.697 | 0.592 | 0.847 |
| Ours | Not run: this environment has no working Python runtime or configured LLM endpoint. | | |

- Check: the gain holds on edit types and phrasings you did not tune on.

## Surprise criterion
What did you change for the new criterion? (Only inputs may change: the criterion text and the examples.)

| | combined | catch | keep |
|---|---|---|---|
| Baseline | | | |
| Ours, recipe unchanged | | | |

## What did not work
