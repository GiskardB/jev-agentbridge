# Model routing evaluation: instructions for the agent running it

You are going to measure how well JEV-AgentBridge picks **which LLM tier (small / medium /
large) should answer a user request**. You will run the published Docker images against a
labelled dataset and produce a comparison report. Follow the steps in order. Do not skip the
smoke test.

## What you are measuring

The service receives a user request and answers `small`, `medium` or `large` with a
probability. In production it is used as a gate: if the probability is at or above a
threshold, the answer is used; otherwise an LLM decides. So the key numbers are:

- **Accuracy**: share of requests routed to the expected tier.
- **Coverage at the recommended threshold**: share of requests JEV could route on its own
  while staying at or above the target accuracy (default 95%). This is the share of LLM
  routing calls it would save.
- **Confident errors**: wrong answers with probability ≥ 0.8. These are the dangerous ones,
  because the gate would trust them.

## Files

| File | Role |
|---|---|
| `model_routing.jsonl` | 240 labelled requests: 120 Italian, 120 English, 40 per tier per language. **Do not edit.** |
| `run_eval.py` | Runner. Python standard library only; no install needed. |
| `README.md` | How the dataset was built, and the labelling rules. |
| `results/` | Created by the runner. Everything you produce goes here. |

## Rules

1. Do not modify `model_routing.jsonl` or the labels, even if you disagree with one. Note
   disagreements in your findings instead (step 7).
2. Do not change engine settings beyond the configurations listed below. The point is to
   compare fixed configurations, not to tune on the test set.
3. Run every configuration on the full dataset. `--limit` is only for the smoke test.
4. If a step fails, stop and report the exact command and error. Do not work around it
   silently.
5. Remove every container you start (`docker rm -f ...`) when you are done with it.

## Prerequisites

- Docker (Docker Desktop on Windows/macOS) running, with internet access to `ghcr.io` and
  `huggingface.co`. The first run of each engine downloads its model (about 1–2 GB).
- Python 3.9 or newer on the PATH (`python --version`; on some Linux/macOS systems use
  `python3`).
- About 1 hour in total, most of it downloads. Each full run takes 2–5 minutes.
- Port 8000 free. If it is not, use another host port (e.g. `-p 8010:8000`) and pass the
  matching `--url http://localhost:8010`.

All commands below are single-line, so they work in PowerShell, cmd and bash. Run them from
this directory (`examples/eval/model_routing/`).

A named Docker volume (`jev-hf-cache`) keeps downloaded models between containers, so each
model is downloaded only once.

## Step 1: smoke test (about 5 minutes)

```
docker run -d --name jev-eval -p 8000:8000 -v jev-hf-cache:/root/.cache/huggingface ghcr.io/giskardb/jev-agentbridge:0.4.0
python run_eval.py run --url http://localhost:8000 --label smoke --limit 10
docker rm -f jev-eval
```

The runner waits up to 5 minutes for the service to be ready (`/ready`), then prints progress.
Expected output: `Bridge ready: engine=laya ...`, then a summary with `"samples": 10` and
`"failed_requests": 0`. If `failed_requests` is not 0, open `results/smoke.predictions.jsonl`
and read the `error` field before going on.

Then delete the smoke results so they do not appear in the report:

```
python -c "import pathlib; [p.unlink() for p in pathlib.Path('results').glob('smoke.*')]"
```

## Step 2: laya, English model (the default engine)

```
docker run -d --name jev-eval -p 8000:8000 -v jev-hf-cache:/root/.cache/huggingface ghcr.io/giskardb/jev-agentbridge:0.4.0
python run_eval.py run --url http://localhost:8000 --label laya-en
docker rm -f jev-eval
```

## Step 3: laya, multilingual model

```
docker run -d --name jev-eval -p 8000:8000 -v jev-hf-cache:/root/.cache/huggingface -e JEV_LAYA_SUBFOLDER=multilingual ghcr.io/giskardb/jev-agentbridge:0.4.0
python run_eval.py run --url http://localhost:8000 --label laya-multilingual
docker rm -f jev-eval
```

## Step 4: semif, both prompt versions

```
docker run -d --name jev-eval -p 8000:8000 -v jev-hf-cache:/root/.cache/huggingface ghcr.io/giskardb/jev-agentbridge:0.4.0-semif
python run_eval.py run --url http://localhost:8000 --label semif-v1
docker rm -f jev-eval
docker run -d --name jev-eval -p 8000:8000 -v jev-hf-cache:/root/.cache/huggingface -e JEV_SEMIF_PROMPT_VERSION=direct-options-v2 ghcr.io/giskardb/jev-agentbridge:0.4.0-semif
python run_eval.py run --url http://localhost:8000 --label semif-v2
docker rm -f jev-eval
```

## Step 4b (optional): Kev

[Kev](https://github.com/jaredpalmer/kev) runs as its own server (Python 3.12–3.13, needs
[uv](https://docs.astral.sh/uv/)); the bridge talks to it over the System One protocol. Kev
listens on `127.0.0.1` only, so run the bridge from source on the same machine, from the
repository root, instead of Docker. Use `kev-0.8b` without a GPU; on a GPU or Apple Silicon use
`kev-4b` and label the run `kev-4b`.

```
git clone https://github.com/jaredpalmer/kev
cd kev
uv sync --extra serve
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.8b --port 8009
```

In a second terminal, from the root of this repository (PowerShell: `$env:JEV_ENGINE="kev"`
instead of the `JEV_ENGINE=kev` prefix):

```
JEV_ENGINE=kev uv run python -m uvicorn jev_agentbridge.main:app --port 8000
```

In a third terminal, from `examples/eval/model_routing/`:

```
python run_eval.py run --url http://localhost:8000 --label kev-0.8b --timeout 120
```

Stop both servers with Ctrl+C when done.

## Step 5 (optional, recommended): LLM baseline

This shows what the LLM that JEV would replace achieves on the same data. Do it only if you
have access to an LLM API. Record which model you used.

For every row of `model_routing.jsonl`, send this prompt with temperature 0. Replace
`{request}` with the row's `state` field.

```
You route user requests to the cheapest model that can handle them well.
Reply with exactly one word: small, medium or large.

small  = simple, short request: greeting, factual question, FAQ, conversion, translating or fixing one sentence
medium = standard writing or coding task: email, summary, explaining a concept, a simple function or fix
large  = complex task: multi-step reasoning, in-depth analysis, architecture, hard debugging, planning or comparing options

Request:
{request}
```

Write one JSON line per row to `results/llm.predictions.jsonl`. Normalize the answer to
lowercase and strip spaces and punctuation. Use `null` if it is not one of the three words.

```
{"id": "it-small-01", "predicted": "small", "latency_ms": 820}
```

Then score it:

```
python run_eval.py score --predictions results/llm.predictions.jsonl --label llm-baseline
```

An LLM gives no probability, so it is scored as always confident (coverage 100%). Compare its
**accuracy** with the JEV runs.

## Step 6: build the report

```
python run_eval.py report
```

This writes `results/REPORT.md`: one comparison table, plus a confusion matrix and the
confident errors for each run.

## Step 7: write your findings

Create `results/FINDINGS.md` answering these questions, citing numbers from `REPORT.md`:

1. Which configuration has the best overall accuracy? What is it in Italian vs English?
2. At the 95% target, which configuration has the highest coverage, and at which threshold?
   A recommended threshold of `-` means the target was never reached.
3. Which tier is confused most often, and in which direction (see confusion matrices)?
4. How many confident errors (p ≥ 0.8) did each configuration make? Quote the three worst.
5. If you ran step 5: how far is the best JEV configuration from the LLM baseline?
6. Recommendation, in one or two sentences: use JEV for routing now, only for a subset (which
   one, at which threshold), or not yet?
7. Labels in the dataset that you think are wrong or ambiguous, by `id`, with one line each.
   Do not change them.

Hand back `results/REPORT.md`, `results/FINDINGS.md` and all `results/*.summary.json`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Bridge ... not ready after 300s` | Model still downloading on a slow connection. Check with `docker logs jev-eval`. Re-run with `--wait-seconds 1200`. |
| `port is already allocated` | Port 8000 is in use. Map another port (`-p 8010:8000`) and pass `--url http://localhost:8010`. |
| `Conflict. The container name "/jev-eval" is already in use` | A previous container was left over. Run `docker rm -f jev-eval`. |
| `failed_requests` > 0 | See the `error` field in `results/<label>.predictions.jsonl`. A 503 means the engine is not ready; a 413 means the input is too large. |
| `python` not found on Windows | Use `py` instead of `python`. |
| Very slow requests (> 3 s each) | CPU contention. Close other heavy programs and re-run. Latency is recorded but it is not the main metric here. |

## Reference: numbers from the dataset author's machine

These give you a sanity check, not a target. They come from a single run through a local
service on a cloud CPU: laya English model 59.6% (EN 70.0%, IT 49.2%), recommended threshold
0.55 with 12.1% coverage; laya multilingual 34.6%. If your laya-en numbers differ by more
than about 5 points, mention it in the findings. It may mean a different image or model was
used.
