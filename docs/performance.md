# Performance

Benchmark with `python -m benchmarks.run --engine <semif|laya|rizzoflow>`. The benchmark measures:

- cold start (engine construction; includes model download on the very first run)
- warm direct decision latency (p50, p95, min, max), after one discarded warmup call
- warm shared/batch decision latency (3 decisions, one state)

CPU inference latency is input-length and hardware dependent. Do not claim sub-100ms without
benchmarking on stated hardware.

## Cold start vs warm inference

The first execution downloads the model to the Hugging Face cache; subsequent executions reuse it.
`cold_start_seconds` includes that download on a cold cache — expect it to drop significantly once
the model is cached locally (see the measured numbers below).

## Running benchmarks

```bash
python -m benchmarks.run --engine semif
python -m benchmarks.run --engine laya       # requires: pip install jev-agentbridge[laya]
python -m benchmarks.run --engine rizzoflow  # requires a running RizzoFlow server, see below
```

Output includes machine-readable JSON and a human-readable summary.

## Measured: semif vs laya (CPU, warm cache)

One real run, single machine, single-threaded PyTorch default settings — not a multi-run statistical
study. Re-run `python -m benchmarks.run` on your own hardware before trusting these numbers for a
capacity or cost decision.

**Hardware**: Intel Core i7-6700HQ (4c/8t @ 2.6GHz), 8GB RAM, no GPU. `--iterations 8` (24 samples/engine
across the 3 scenarios in `benchmarks/run.py`).

| Metric | semif (Qwen3-0.6B) | laya (English, 421M) |
|---|---|---|
| Cold start (warm HF cache) | 11.6s | 34.3s |
| Warm direct p50 | 720ms | 339ms |
| Warm direct p95 | 891ms | 517ms |
| Warm direct min/max | 630 / 908ms | 266 / 534ms |
| Warm shared (batch of 3) | 1.506s | 0.852s |

On this CPU, laya answers a single decision **~2.1x faster** at p50 and **~1.8x faster** batched — a
real but much smaller gap than Laya's own published GPU figure (7.8x vs a third-party "Jev" number,
not this codebase). Laya's engine construction is noticeably slower to spin up here even with a warm
Hugging Face cache; investigate before assuming that holds on your hardware. Neither engine has been
benchmarked here past 16 options — see the accuracy caveats in the [README](../README.md#pluggable-engines).

## RizzoFlow (not in the table above)

RizzoFlow ([Rizzo-AI-Academy/rizzo-flow](https://github.com/Rizzo-AI-Academy/rizzo-flow)) ships a
different model family and size entirely (quantized Spark-X2.5, 1.7B or 4B, GGUF via llama.cpp), run
as its own server rather than in-process — it isn't a fair apples-to-apples row in the table above,
so it was verified separately rather than folded in:

```bash
git clone https://github.com/Rizzo-AI-Academy/rizzo-flow && cd rizzo-flow
uv sync --locked && uv run rizzo download --size 1.7b --quant q4_k_m --runtime cpu
uv run rizzo serve --device cpu --size 1.7b --quant q4_k_m
```

Then `JEV_ENGINE=rizzoflow JEV_RIZZOFLOW_URL=http://127.0.0.1:8017` against this Bridge. Confirmed
working end-to-end on this CPU: single decision ~3.3s (`retry`, p=0.9966) through this Bridge's own
`/v1/decide`, correctly answering the same example used throughout this repo's docs. RizzoFlow's own
README says plainly they hadn't benchmarked CPU-only before ("not tried: we have no CPU number"), so
treat that number the same way — as a "yes it works," not a latency claim.

Note: as of this writing, `rizzo download`'s tar extraction (`TarFile.extract(..., filter="data")`)
requires Python ≥3.12, even though the project's own `pyproject.toml` declares `requires-python =
">=3.11"`; it fails on 3.11. Unrelated to this Bridge (RizzoFlow runs as its own separate process),
but worth knowing before you hit it yourself.

## Accuracy and threshold

Latency says nothing about whether an engine is right. When JEV gates an LLM, the question is:
*at which threshold do decisions with `accepted=true` match what the LLM would have decided, and
what share of traffic does that leave to JEV?* `jev-eval` measures this against any running
Bridge, for any engine:

```bash
jev-eval --dataset examples/eval/sample.jsonl --url http://localhost:8000 --target-accuracy 0.97
```

The dataset is JSONL, one labelled decision per line (`state`, `question`, `options`,
`expected`). For each threshold from 0.50 to 0.95 the tool prints two numbers. *Coverage* is the
share of decisions JEV would answer alone. *Accuracy on accepted* is how often those answers are
right. It then recommends the lowest threshold that reaches the target, which is the one with
the most coverage. Use 200–500 real examples of one decision type; `examples/eval/sample.jsonl`
(12 rows) only shows the format.

### Measured: all in-process engines on the samples

One run per configuration, CPU, through the Bridge API (`jev-eval`), on
`examples/eval/sample.jsonl` (English) and `examples/eval/sample_it.jsonl` (the same 12 decisions
in Italian):

| Engine / config | Accuracy EN | Accuracy IT | p50 latency |
|---|---|---|---|
| laya, English model (default) | **83.3%** | **75.0%** | ~350ms |
| laya, `JEV_LAYA_SUBFOLDER=multilingual` | 75.0% | 75.0% | ~170ms |
| semif, `direct-options-v1` prompt (default) | 41.7% | 41.7% | ~530ms |
| semif, `direct-options-v2` prompt | 75.0% | 66.7% | ~530ms |

This is why laya became the default engine in 0.4.0. semif v1 is close to chance; its prompt
ends right after the option list, so the next token is rarely the letter. v2 appends
`"\n\nAnswer:"`. It stays opt-in (`JEV_SEMIF_PROMPT_VERSION=direct-options-v2`) until it is
validated on a larger dataset. A chat-template variant was also tried (8/12 EN) and is not shipped.

Twelve rows are far too few for a production threshold. Even laya accepted confident mistakes:
it chose `retry` at p=0.946 when four identical failures in a row called for `rollback`. Build
200–500 real examples per decision type and let `jev-eval` pick the threshold.


### Measured: model routing (240 requests)

[`examples/eval/model_routing/`](../examples/eval/model_routing/) is a use-case evaluation: choose
the LLM tier (small / medium / large) for 240 hand-labelled requests, 120 Italian and 120
English. It was executed by a separate agent following its `INSTRUCTIONS.md`, using the 0.4.0
images. The laya numbers match an independent run to the decimal. Full output is in
[`results/REPORT.md`](../examples/eval/model_routing/results/REPORT.md) and
[`results/FINDINGS.md`](../examples/eval/model_routing/results/FINDINGS.md).

| Configuration | Accuracy | EN | IT | Threshold for ≥ 95% | Coverage | p50 latency |
|---|---|---|---|---|---|---|
| LLM baseline: qwen3-32b via OpenRouter, temperature 0 | **96.2%** | 95.8% | 96.7% | n/a (no probability) | n/a | ~9.1 s (reasoning enabled) |
| Kev-0.8B via `JEV_ENGINE=kev` (remote, CPU fp32; run with the same runner, not by the external agent) | **80.4%** | 78.3% | **82.5%** | 0.60 | **60.0%** | ~1.85 s |
| laya, English model (default) | 59.6% | 70.0% | 49.2% | 0.55 | 12.1% | ~970 ms |
| semif, `direct-options-v2` | 51.7% | 56.7% | 46.7% | never reached | 0% | ~1.4 s |
| semif, `direct-options-v1` | 37.5% | 41.7% | 33.3% | 0.65 | 7.1% | ~1.4 s |
| laya, multilingual model | 34.6% | 37.5% | 31.7% | never reached | 0% | ~290 ms |
| Always answer "medium" (floor) | 33.3% | | | | | |

What this shows:

- **Kev-0.8B is the best JEV engine measured so far, by a wide margin.** At threshold 0.60 it
  answers 144 of 240 requests alone (72 Italian, 72 English) and gets 137 right (95.1%). At 0.75
  it answers 76 with no error. It made no confident errors (p ≥ 0.8). Its weak spot is `small`
  requests (63.7%, mostly routed to `medium`), which is the safe direction for routing. On CPU it
  takes about 1.85 s per decision; Kev's own figures on a GPU are tens of milliseconds. Kev-4B and
  9B were not measured.

- **The task is learnable and the labels hold up.** The LLM gets 96.2% in both languages. The
  gap is in today's JEV models, not in the dataset or in the bridge.
- **laya (English model), the default in-process engine, is not a router yet.** It sends most small
  and large requests to `medium`. Its probabilities never exceed about 0.73, so at the 0.55
  threshold it takes only 29 of 240 requests (28 correct), all of them English.
- **Italian gets no coverage** from any in-process configuration at the 95% target (Kev does cover it).
- **The multilingual Laya model and semif v1 have strong, opposite biases** (toward `small` and
  toward `large`). Do not use them for this task.
- **Latency does not compensate on its own.** At about 1 s per decision on the evaluator's
  machine, laya is 9× faster than a reasoning LLM, but a non-reasoning LLM classifier may be
  comparable. Measure both on your hardware before counting on a speed win.

## Question types: native vs emulated

The engines that have native yes/no (`noul`) and scale (`score`) paths were measured against
asking the same questions as a choice, on the 80-question
[question-types suite](../examples/eval/question_types):

| Engine | noul native / emulated | score exact, native / emulated |
|---|---|---|
| Kev-0.8B | 85.4% / 85.4% | 68.8% / 71.9% |
| Laya multilingual | 81.2% / 79.2% | 40.6% / 62.5% |
| Laya English | 79.2% / 83.3% | 43.8% / 46.9% |

Native was never better, and Laya's native score was clearly worse, so the Bridge asks noul and
score as a choice by default (`JEV_NATIVE_TYPES=false`).
