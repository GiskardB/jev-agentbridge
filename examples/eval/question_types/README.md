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

Start the same engine twice, once with native types and once with `JEV_NATIVE_TYPES=false`,
then run the suite against both. Windows PowerShell, with Docker:

```powershell
docker run -d --name jev-native   -p 8000:8000 ghcr.io/giskardb/jev-agentbridge:latest
docker run -d --name jev-emulated -p 8001:8000 -e JEV_NATIVE_TYPES=false ghcr.io/giskardb/jev-agentbridge:latest

python examples/eval/question_types/run_eval.py run --url http://localhost:8000 --label laya-native
python examples/eval/question_types/run_eval.py run --url http://localhost:8001 --label laya-emulated
python examples/eval/question_types/run_eval.py report
```

For Kev, run the compose file twice, one run after the other:

```powershell
docker compose -f docker-compose.kev.yml up -d
python examples/eval/question_types/run_eval.py run --url http://localhost:8000 --label kev-native
$env:JEV_NATIVE_TYPES = "false"; docker compose -f docker-compose.kev.yml up -d
python examples/eval/question_types/run_eval.py run --url http://localhost:8000 --label kev-emulated
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

RESULTS_TABLE
