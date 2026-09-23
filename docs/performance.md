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
python -m benchmarks.run --engine laya       # requires: pip install jev-cpu-agentbridge[laya]
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

A larger, use-case-specific evaluation lives in
[`examples/eval/model_routing/`](../examples/eval/model_routing/). It has 240 labelled requests
for choosing the LLM tier (small / medium / large), a stdlib-only runner, and step-by-step
instructions another agent can execute. On it, laya's English model reached 59.6% overall
(EN 70.0%, IT 49.2%) and covered only 12.1% of requests at 95% accuracy. The multilingual model
reached 34.6%. Three-way routing is clearly harder than the samples above.

Twelve rows are far too few for a production threshold. Even laya accepted confident mistakes:
it chose `retry` at p=0.946 when four identical failures in a row called for `rollback`. Build
200–500 real examples per decision type and let `jev-eval` pick the threshold.
