"""Claim-level LLM judge with evidence-gated FAIL and a false-positive check.

Design (criterion-agnostic; all task semantics come from criterion + policy + dev examples):
  1. prepare(): build a few CONTRASTIVE calibration examples from dev pairs (a PASS reply next to its
     minimally edited FAIL reply, with the construction note as the reason) plus harmless-edit examples
     that stay PASS. Pairs are used only to build examples; judge() always sees a single reply.
  2. judge() call 1: the model decomposes the reply into claims, translates each to English, finds the
     policy sentence on the same topic and labels the relation. FAIL is only allowed with a quoted
     policy sentence the claim breaks.
  3. judge() call 2 (only if call 1 says FAIL): an independent verifier checks the cited violation.
     Concise, translated, reordered or padded replies are not violations by themselves.
At most 2 LLM calls per reply.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The model must be allowed to reason; the final verdict is parsed from the last VERDICT line.
if int(os.environ.get("JUDGE_LLM_MAX_TOKENS", "0") or 0) < 900:
    os.environ["JUDGE_LLM_MAX_TOKENS"] = "900"

from baseline_judge import complete  # noqa: E402

CONTRASTS: list[dict] = []   # {"good":..., "bad":..., "why":...}
KEEPS: list[dict] = []       # {"reply":..., "lang":...} harmless variants that stay PASS


def _s(x) -> str:
    return str(x or "").strip()


def prepare(criterion: str, policy: str, dev_pairs: list[dict]) -> None:
    CONTRASTS.clear()
    KEEPS.clear()
    rng = random.Random(13)
    rows = list(dev_pairs)
    rng.shuffle(rows)

    harmful, harmless = [], []
    for r in rows:
        ol, el = _s(r.get("original_label", "pass")).lower(), _s(r.get("edited_label")).lower()
        if not _s(r.get("original")) or not _s(r.get("edited")):
            continue
        if ol == "pass" and el == "fail":
            harmful.append(r)
        elif ol == "pass" and el == "pass":
            harmless.append(r)

    # One contrast per edit type (round-robin), different sources where possible, max 5.
    seen_types, seen_src = set(), set()
    for strict in (True, False):
        for r in harmful:
            if len(CONTRASTS) >= 5:
                break
            et, src = _s(r.get("edit_type")) or "?", _s(r.get("source_id"))
            if strict and (et in seen_types or src in seen_src):
                continue
            if any(c["bad"] == r["edited"] for c in CONTRASTS):
                continue
            seen_types.add(et); seen_src.add(src)
            CONTRASTS.append({
                "good": _s(r.get("original")),
                "bad": _s(r.get("edited_unpadded") or r.get("edited")),
                "why": _s(r.get("edit_note")) or f"edit type: {et}",
                "lang": _s(r.get("lang")) or "en",
            })

    # A few harmless variants (prefer non-English and openers/fillers) to show style changes stay PASS.
    seen_types = set()
    for r in harmless:
        if len(KEEPS) >= 3:
            break
        et = _s(r.get("edit_type"))
        if et in seen_types:
            continue
        seen_types.add(et)
        KEEPS.append({"reply": _s(r.get("edited")), "lang": _s(r.get("lang")) or "en"})


def _examples_text() -> str:
    if not CONTRASTS and not KEEPS:
        return "(none provided)"
    out = []
    for i, c in enumerate(CONTRASTS, 1):
        out.append(
            f"Contrast {i} ({c['lang']}):\n  PASS: {json.dumps(c['good'], ensure_ascii=False)}\n"
            f"  FAIL: {json.dumps(c['bad'], ensure_ascii=False)}\n  Why the FAIL version fails: {c['why']}"
        )
    for k in KEEPS:
        out.append(f"Also PASS (harmless wording/language change, {k['lang']}): {json.dumps(k['reply'], ensure_ascii=False)}")
    return "\n".join(out)


ANALYZE = """You check ONE customer-support reply against a criterion and a company policy.

CRITERION (defines PASS and FAIL):
{criterion}

COMPANY POLICY (source of truth):
{policy}

CALIBRATION EXAMPLES (each FAIL differs from its PASS by one small substantive change; style,
greetings, filler, order and language never matter):
{examples}

Customer question ({lang}): {question}
Reply ({lang}): {reply}

Work step by step:
1. List each substantive claim or promise in the reply. Translate it into English, preserving exact
   numbers, units, certainty words (may/usually/try vs will/always/guaranteed), conditions and scope
   (some/certain vs all/any). Ignore greetings, thanks, filler and reassurance.
2. For each claim, quote the single policy sentence on the SAME topic (or write "none").
3. Label each claim:
   SUPPORTED      - matches policy (a shorter or paraphrased statement is fine)
   LESS_GENEROUS  - promises less than or is more cautious than policy
   NOT_COVERED    - policy is silent and the claim is not a promise beyond it
   VIOLATION      - breaks the criterion against the quoted policy sentence: e.g. a number/amount/
                    duration more favourable to the customer, certainty where policy hedges, a
                    condition or exception the policy attaches to THIS promise dropped, wider scope,
                    or a policy detail stated wrongly
4. A VIOLATION must be backed by a quoted policy sentence. Leaving out topics the customer did not ask
   about is NOT a violation. Brevity, translation, word order and politeness are NOT violations.

End with exactly one line: VERDICT: PASS (no VIOLATION) or VERDICT: FAIL (at least one VIOLATION)."""


VERIFY = """A first reviewer flagged this customer-support reply as violating the criterion. Verify it.

CRITERION:
{criterion}

COMPANY POLICY:
{policy}

Customer question ({lang}): {question}
Reply ({lang}): {reply}

First reviewer's analysis:
{analysis}

Uphold the FAIL only if a specific statement in the reply, read for its meaning in {lang}, really
conflicts with a specific policy sentence in the way the criterion forbids (e.g. more generous number,
removed hedge, removed condition that governs that same promise, wrong detail, broader scope).
Overturn it if the reply is merely concise, translated, reworded, reordered, padded, or silent about
something not asked; or if the reviewer misread the policy, matched the wrong topic, or misread a number.

Briefly explain, then end with exactly one line: VERDICT: FAIL (violation confirmed) or VERDICT: PASS."""


_VERDICT_RE = re.compile(r"VERDICT\s*[:\-]?\s*\**\s*(PASS|FAIL)", re.IGNORECASE)


def _verdict(answer: str) -> str | None:
    hits = _VERDICT_RE.findall(answer or "")
    if hits:
        return hits[-1].lower()
    bare = re.findall(r"\b(PASS|FAIL)\b", answer or "")
    return bare[-1].lower() if bare else None


def judge(question: str, reply: str, lang: str, criterion: str, policy: str) -> str:
    fields = dict(criterion=criterion.strip(), policy=policy.strip(), lang=lang, question=question, reply=reply)
    analysis = complete(ANALYZE.format(examples=_examples_text(), **fields))
    first = _verdict(analysis)
    if first == "pass":
        return "pass"
    # FAIL or unparseable (likely truncated): get a second opinion instead of failing blindly.
    check = complete(VERIFY.format(analysis=(analysis or "")[-3000:], **fields))
    return "fail" if _verdict(check) == "fail" else "pass"
