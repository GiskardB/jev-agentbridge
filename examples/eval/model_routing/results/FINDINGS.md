# Model routing evaluation: findings

Based on `results/REPORT.md` (5 configurations, 240 requests each, `failed_requests: 0` in every
run, including the LLM baseline from step 5).

## 1. Best overall accuracy

**laya-en**, 59.6% overall (EN 70.0%, IT 49.2%). Next best is semif-v2 at 51.7% (EN 56.7%, IT
46.7%). laya-en is the only configuration where English clears 70%; every configuration is
weaker in Italian than English, laya-en included (70.0% vs 49.2%, a 20.8-point gap).

## 2. Coverage at the 95% target

**laya-en** again: recommended threshold 0.55, coverage 12.1% — the only run with coverage in
double digits. semif-v1 does reach a recommended threshold (0.65) but at only 7.1% coverage.
laya-multilingual and semif-v2 never reach 95% accuracy at any threshold (recommended threshold
`-`), so they cannot self-route any share of traffic under this target.

## 3. Most-confused tier and direction

Aggregating the four confusion matrices, **"small" is the tier confused most often**: averaged
across all four runs, small-expected requests are misrouted ~63% of the time (202/320), against
~51% for medium and ~49% for large. The dominant direction is **over-escalation**: small requests
get pushed up to medium (115 of the 202 small errors) or large (87), not down — no configuration
under-routes a large/medium request into small more than it over-routes small requests upward.
Per configuration the bias differs: laya-en and semif-v2 pull everything toward **medium**
(large→medium 44/40, small→medium 43/59); semif-v1 pulls everything toward **large**
(medium→large 71, small→large 68); laya-multilingual pulls everything toward **small**
(large→small 59, medium→small 67) — the opposite bias from the other three, and the reason its
accuracy floor is so low.

## 4. Confident errors (p ≥ 0.8)

- laya-en: **0**
- semif-v1: **0**
- semif-v2: **9**
- laya-multilingual: **11** (worst of all runs)

Three worst overall (all from laya-multilingual, the highest-confidence wrong answers across
every run):

1. `en-small-03` — expected **small**, got **large** at p=0.99: "How many ounces are in a pound?"
2. `it-small-04` — expected **small**, got **large** at p=0.98: "Quanti grammi ci sono in
   un'oncia?"
3. `en-medium-12` — expected **medium**, got **small** at p=0.96: "Convert this short Python
   script that reads a JSON file into Node.js."

(llm-baseline also shows "9 confident errors", all at p=1.00 — but an LLM's one-word answer has
no real probability distribution behind it, so `run_eval.py score` treats every external
prediction as maximally confident by convention. That's not comparable to JEV's calibrated
per-option probability; it just means the LLM was wrong on 9/240 with nothing to gate on.)

laya-en and semif-v1 having zero confident errors is notable given their mediocre raw accuracy:
when they're wrong, they tend to be wrong at low confidence, which is exactly what a
threshold-gated deployment needs — it's *why* laya-en gets any usable coverage at all.

## 5. Distance from the LLM baseline

Measured: `qwen/qwen3-32b` via OpenRouter, temperature 0, same prompt as `INSTRUCTIONS.md`,
scored as `llm-baseline` in `results/llm-baseline.summary.json`.

**96.2% accuracy** (EN 95.8%, IT 96.7%) — 36.6 points above laya-en's 59.6%, and better balanced
across languages (laya-en drops 20.8 points EN→IT; the LLM baseline actually does marginally
*better* in Italian). It's also right on every single `small` row (100% vs laya-en's 45.0%), the
tier laya-en struggles with most.

The gap has a large latency cost, though: **p50 9052ms** vs laya-en's 970ms (~9.3x slower) — this
particular OpenRouter model runs with reasoning/chain-of-thought enabled by default (visible in
the raw API response), which is almost certainly most of that latency; a non-reasoning model would
likely close some of the speed gap at some accuracy cost, but that's a different measurement.

## 6. Recommendation

**Use JEV for routing only on the confident subset, not as a full replacement.** The accuracy gap
to the LLM baseline (59.6% vs 96.2%) is too large to route on laya-en alone, but the 12.1% of
traffic where laya-en's own confidence clears 0.55 is exactly the slice where it agrees with the
95%-accuracy bar — gate on that slice (skip the LLM call, fall back to it otherwise) and take the
free ~9s + cost saving there; send everything else to the LLM as today. None of the four JEV
configurations is usable for Italian on its own (best IT accuracy is 49.2%, against 96.7% for the
LLM). Do not ship laya-multilingual or semif-v1 for this task as configured — they're wrong more
often than right and, worse, wrong with the *opposite* systematic bias from the other two, which
would make mixing configurations unpredictable.

## 7. Possibly wrong or ambiguous labels

- `it-small-40` — "Riassumi in tre parole: 'La riunione è spostata a giovedì'." Labelled
  **small**, but the rubric explicitly lists "summary" under **medium**. It's a summary of a
  single short sentence, so it plausibly belongs in either bucket depending on whether the rubric
  means "summarization is a medium-complexity *operation*" or "trivial summaries of trivial input
  stay small" — the rubric doesn't disambiguate this case.
- No other clear label errors found on manual review of the small-with-long-text and
  large-with-short-text edge cases (e.g. `it-large-37`, a one-sentence smart-contract security
  audit request, is short but genuinely large-complexity — correctly labelled). This was a
  targeted spot-check, not an exhaustive review of all 240 rows.
