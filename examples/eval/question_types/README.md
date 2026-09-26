# Question types: native vs emulated

JEV questions come in three types: `choice`, `noul` (yes/no) and `score` (ordinal scale).
Some engines have a dedicated path for noul and score (Laya and Kev heads, RizzoFlow's
`boolean`/`score`), others do not and the bridge emulates them as a choice over the same
options. This suite measures whether the native path helps on a given engine.

## Contents

`question_types.jsonl`: 80 rows.

| | Italian (`it`) | English (`en`) | Total |
|---|---|---|---|
| `noul` (24 yes, 24 no) | 24 | 24 | 48 |
| `score` (3 scales: urgency 4 levels, sentiment 5, severity 3) | 16 | 16 | 32 |

```json
{"id": "noul-it-000", "type": "noul", "lang": "it", "state": "...", "question": "La richiesta di reso rientra nella policy?", "expected": "yes"}
{"id": "score-en-064", "type": "score", "lang": "en", "state": "...", "question": "How urgent is the request?", "options": [{"id": "low", "description": "Low: can wait days"}, "..."], "expected": "critical"}
```

Most noul questions come in pairs, one "yes" and one "no" with the same question, so a model
that always answers the same way scores 50%. Score rows list the levels lowest first.

## Run

Start the same engine twice, once with native types (`JEV_NATIVE_TYPES=all`) and once with the
default (emulated), then run the suite against both. Windows PowerShell, with Docker:

```powershell
docker run -d --name jev-native   -p 8000:8000 -e JEV_NATIVE_TYPES=all ghcr.io/giskardb/jev-agentbridge:latest
docker run -d --name jev-emulated -p 8001:8000 ghcr.io/giskardb/jev-agentbridge:latest

python examples/eval/question_types/run_eval.py run --url http://localhost:8000 --label laya-native
python examples/eval/question_types/run_eval.py run --url http://localhost:8001 --label laya-emulated
python examples/eval/question_types/run_eval.py report
```

For Kev, run the compose file twice, one run after the other:

```powershell
docker compose -f docker-compose.kev.yml up -d
python examples/eval/question_types/run_eval.py run --url http://localhost:8000 --label kev-emulated
$env:JEV_NATIVE_TYPES = "all"; docker compose -f docker-compose.kev.yml up -d
python examples/eval/question_types/run_eval.py run --url http://localhost:8000 --label kev-native
Remove-Item Env:JEV_NATIVE_TYPES; python examples/eval/question_types/run_eval.py report
```

Wait for `docker compose -f docker-compose.kev.yml ps` to show the bridge healthy before each
run. The runner needs only Python 3.9+ (standard library).

Metrics, per type and language:

- **accuracy**: the most likely answer equals the label;
- **coverage @ threshold**: share of questions with `selected_probability` ≥ threshold, and the
  accuracy on those (what a gate at that threshold would answer by itself);
- score only: **±1**, the share within one level of the label, and **MAE**, the mean distance
  between `score` (expected level) and the labelled level.

## Results

Measured on 2026-09-24, CPU, bridge 0.6.0: Kev-0.8B through a local `kev.serve`, Laya 0.3
in-process (multilingual and English models). Raw predictions and summaries are in
[`results/`](results/).

| Run | Native | noul acc. | noul IT | noul EN | noul cov. @0.8 (acc.) | score exact | score ±1 | score MAE | score cov. @0.8 (acc.) |
|---|---|---|---|---|---|---|---|---|---|
| kev-0.8b-emulated | False | 85.4% | 83.3% | 87.5% | 70.8% (100.0%) | 71.9% | 100.0% | 0.505 | 18.8% (100.0%) |
| kev-0.8b-native | True | 85.4% | 83.3% | 87.5% | 64.6% (100.0%) | 68.8% | 100.0% | 0.5054 | 21.9% (100.0%) |
| laya-en-emulated | False | 83.3% | 79.2% | 87.5% | 83.3% (82.5%) | 46.9% | 90.6% | 0.6214 | 21.9% (71.4%) |
| laya-en-native | True | 79.2% | 79.2% | 79.2% | 72.9% (85.7%) | 43.8% | 90.6% | 0.7067 | 34.4% (63.6%) |
| laya-multilingual-emulated | False | 79.2% | 75.0% | 83.3% | 79.2% (84.2%) | 62.5% | 84.4% | 0.6479 | 53.1% (70.6%) |
| laya-multilingual-native | True | 81.2% | 79.2% | 83.3% | 79.2% (84.2%) | 40.6% | 87.5% | 0.7885 | 43.8% (42.9%) |

"cov. @0.8 (acc.)" is the share of questions answered with p ≥ 0.8 and the accuracy on them.

What it says:

- **noul**: native and emulated are within one or two questions out of 48 on every engine. Kev
  runs a noul internally as a choice between "no" and "yes", so the two paths are nearly the
  same computation there.
- **score**: Kev is equal (±1 question). Laya's native score head is clearly worse on the
  multilingual model (40.6% vs 62.5%) and pulls answers toward the middle levels, including
  confident ones (42.9% accurate at p ≥ 0.8). On the English model both paths are weak on
  Italian scales.
- Hence the default: noul and score are asked as a choice (`JEV_NATIVE_TYPES=false`). The typed
  API still pays off on the caller's side (`yes`/`no` answers, ordered `score`).

80 questions is a small suite: treat differences of a few points as noise and re-run on your
own questions before changing the default.

### Second run: 200 new questions (2026-09-26)

[`datasets/local-20260926.jsonl`](datasets/local-20260926.jsonl): 120 noul and 80 score,
Italian and English, 17 categories (policy, support, devops, code, finance, HR, legal, security,
access...), 30% `hard` rows, written and committed before any run by a local agent following
[LOCAL_RUN.md](LOCAL_RUN.md). Bridge 0.6.2, Kev pinned `9a45d25e`, Laya multilingual, CPU.
Results and environment notes: [`results/local-20260926/`](results/local-20260926/).

| Run | noul acc. | noul IT / EN | score exact | score ±1 |
|---|---|---|---|---|
| kev-emulated | 82.5% | 81.7% / 83.3% | 72.5% | 98.8% |
| kev-native | 82.5% | 81.7% / 83.3% | 67.5% | 98.8% |
| laya-emulated | 59.2% | 56.7% / 61.7% | 45.0% | 80.0% |
| laya-native | 57.5% | 55.0% / 60.0% | 32.5% | 83.8% |

Pooled over both suites (280 questions), with McNemar's exact test on the questions where the
two paths disagree:

| Engine, type | native | emulated | disagreements (native right / emulated right) | p |
|---|---|---|---|---|
| Kev noul (168) | 83.3% | 83.3% | 2 / 2 | 1.00 |
| Kev score (112) | 67.9% | 72.3% | 2 / 7 | 0.18 |
| Laya noul (168) | 64.3% | 64.9% | 17 / 18 | 1.00 |
| Laya score (112) | 34.8% | 50.0% | 16 / 33 | 0.02 |

- Native is never better; for Laya's score it is significantly worse. Emulation stays the default.
- **Kev as a noul gate** (emulated, pooled): threshold 0.60 answers 81% at 90.4% accuracy,
  0.70 answers 66% at 95.5%, 0.80 answers 48% at 98.8%. Weakest categories: HR 7/12,
  access 8/12.
- **Laya is not a noul gate** on realistic questions: 59% accuracy, "yes" predicted 81 times
  out of 120, 26 wrong answers with p ≥ 0.8.
- **Scales**: Kev picks the exact level 72% of the time but is within one level 99% of the
  time, with low confidence on the exact level. That led to the ±1 acceptance window of 0.7.0:
  see [`results/score-window-0.7.0/`](results/score-window-0.7.0/).
