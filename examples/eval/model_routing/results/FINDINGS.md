# Model routing evaluation: findings

Based on `results/REPORT.md` (4 configurations, 240 requests each, `failed_requests: 0` in every
run). Step 5 (LLM baseline) was not run — see question 5.

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

laya-en and semif-v1 having zero confident errors is notable given their mediocre raw accuracy:
when they're wrong, they tend to be wrong at low confidence, which is exactly what a
threshold-gated deployment needs — it's *why* laya-en gets any usable coverage at all.

## 5. Distance from the LLM baseline

**Not measured.** Step 5 is optional and needs a live LLM API call for all 240 rows; an
`OPENROUTER_API_KEY` is present in this environment but `CAVE_OPENROUTER=0` indicates it's
deliberately disabled here, and spending real API budget on 240 calls isn't something to do
without asking first. If you want this filled in, say so and I'll run it and update this file plus
`results/llm-baseline.summary.json`.

## 6. Recommendation

**Use JEV for routing only on the confident subset, not as a full replacement yet.** laya-en at
threshold 0.55 is the one configuration that clears the 95%-accuracy bar, but only on 12.1% of
traffic — worth wiring in as a gate (skip the LLM call on that slice, fall back to the LLM
otherwise) but not enough coverage to call this "solved." None of the four configurations is
usable for Italian on its own (best IT accuracy is 49.2%, well under any reasonable bar). Do not
ship laya-multilingual or semif-v1 for this task as configured — they're wrong more often than
right and, worse, wrong with the *opposite* systematic bias from the other two, which would make
mixing configurations unpredictable.

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
