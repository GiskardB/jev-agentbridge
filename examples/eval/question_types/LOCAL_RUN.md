# Question types: extended local run (instructions for the agent running it)

You are going to **write new labelled yes/no (`noul`) and ordinal-scale (`score`) questions**,
run them through JEV-AgentBridge on two engines (Laya and Kev), each with the engine's native
question-type path and with the default emulated path, and **push the dataset and the raw
results** to a new branch. Someone else analyses the results: your job is a clean, complete,
reproducible measurement, not conclusions.

Background: [README.md](README.md) in this folder. The bundled 80-question suite showed native
paths no better than emulated (Laya's native score clearly worse). 80 questions is small; this
run adds a larger, independent set to confirm or overturn that.

## Rules

1. **Do not modify code, docs or existing datasets.** You add exactly two things: one new
   dataset file and one new results folder (paths below), plus a `NOTES.md` inside it.
2. Write the dataset **before** running any engine, and do not edit labels after seeing
   results. If a label turns out to be ambiguous, keep it and list it in `NOTES.md`.
3. Run every configuration on the full dataset. `--limit` is only for the smoke test.
4. If a step fails, record the exact command and error in `NOTES.md`, then continue with the
   remaining configurations. Push whatever you have at the end.
5. Push only to the new branch. Do not open a pull request, do not merge, do not tag.
6. The machine is Windows: use PowerShell. Run every command from the repository root.
7. Remove every container you start when done (`docker rm -f ...`,
   `docker compose -f docker-compose.kev.yml down`).

## Step 0: branch

```powershell
git checkout main; git pull
$d = Get-Date -Format yyyyMMdd
git checkout -b "eval/question-types-$d"
$ds = "examples/eval/question_types/datasets/local-$d.jsonl"; $out = "examples/eval/question_types/results/local-$d"
New-Item -ItemType Directory -Force (Split-Path $ds), $out | Out-Null
```

`$d`, `$ds` (the new dataset) and `$out` (the results folder) are used below; if you open a new
PowerShell session, set them again.

## Step 1: write the dataset (200 questions)

One JSON object per line, UTF-8, same format as `question_types.jsonl`:

```json
{"id": "noul-it-001", "type": "noul", "lang": "it", "category": "policy", "difficulty": "normal", "state": "...", "question": "...", "expected": "yes"}
{"id": "score-en-001", "type": "score", "lang": "en", "category": "urgency", "difficulty": "hard", "state": "...", "question": "...", "options": [{"id": "low", "description": "..."}, {"id": "high", "description": "..."}], "expected": "high"}
```

Counts:

| | Italian | English | Total |
|---|---|---|---|
| `noul` | 60 (30 yes, 30 no) | 60 (30 yes, 30 no) | 120 |
| `score` | 40 | 40 | 80 |

Content rules:

- **Realistic agent situations**, the kind an orchestrator would ask a small model before or
  instead of calling an LLM: customer messages, support tickets, policy and eligibility
  checks, deployment and CI logs, code-review or coding-agent requests, emails, reviews,
  invoices, access requests. `state` is 1–4 sentences of evidence; `question` is the criterion.
- **`category`**: a short free label for the domain (`policy`, `support`, `devops`, `code`,
  `finance`, `sentiment`, `urgency`, `severity`, ...). Use at least 8 different categories.
- **noul**: write most questions in pairs (same question, one state whose answer is yes and one
  whose answer is no), so a model that always says the same thing scores 50%. Include
  questions whose natural answer is "no" as well as "yes". The answer must follow from the
  `state` alone, without outside knowledge.
- **score**: at least 6 different scales, with 3, 4 and 5 levels represented. Levels go
  **lowest first** and have ids plus a short description of what the level means. Spread the
  labels over all levels, including both extremes (not mostly the middle). Level descriptions
  in the row's language.
- **`difficulty`**: about 70% `normal` (a careful human answers instantly) and 30% `hard`
  (negation, an implicit answer, mixed signals that still point one way, sarcasm, numbers to
  compare). Still exactly one defensible answer.
- Italian and English rows are different situations, not translations of each other. Do not
  copy or paraphrase rows of `question_types.jsonl`.
- ids: `noul-it-001`... and `score-en-001`..., unique.

Validate before running anything (must print `OK` and the counts):

```powershell
python -c "import json,collections,sys; p=sys.argv[1]; rows=[json.loads(l) for l in open(p,encoding='utf-8') if l.strip()]; ids=[r['id'] for r in rows]; assert len(ids)==len(set(ids)),'duplicate ids'; [(_ for _ in ()).throw(AssertionError(r['id'])) for r in rows if r['type']=='noul' and (r['expected'] not in ('yes','no') or 'options' in r)]; [(_ for _ in ()).throw(AssertionError(r['id'])) for r in rows if r['type']=='score' and (not 3<=len(r['options'])<=5 or r['expected'] not in [o['id'] for o in r['options']])]; print('OK', collections.Counter((r['type'],r['lang']) for r in rows), collections.Counter((r['lang'],r['expected']) for r in rows if r['type']=='noul'))" $ds
```

Commit the dataset alone now, so the labels are fixed before any result exists:

```powershell
git add $ds; git commit -m "Add local question-types dataset $d"
```

## Step 2: record the environment

Create `$out/NOTES.md` with: CPU model and core count, RAM, OS,
Docker version, whether a GPU was used (default images are CPU), and the start time.

## Step 3: Laya (multilingual, the default), emulated then native

```powershell
docker pull ghcr.io/giskardb/jev-agentbridge:latest
docker run -d --name jev-qt -p 8000:8000 -v jev-hf-cache:/root/.cache/huggingface ghcr.io/giskardb/jev-agentbridge:latest
```

Wait until `Invoke-RestMethod http://localhost:8000/ready` answers `ready` (first start
downloads the model). Then:

```powershell
Invoke-RestMethod http://localhost:8000/v1/info | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 "$out/info-laya-emulated.json"
python examples/eval/question_types/run_eval.py --dataset $ds --out-dir $out run --url http://localhost:8000 --label laya-emulated --limit 5
python examples/eval/question_types/run_eval.py --dataset $ds --out-dir $out run --url http://localhost:8000 --label laya-emulated
docker rm -f jev-qt
docker run -d --name jev-qt -p 8000:8000 -v jev-hf-cache:/root/.cache/huggingface -e JEV_NATIVE_TYPES=all ghcr.io/giskardb/jev-agentbridge:latest
```

Wait for `/ready` again, then the same three commands with the label `laya-native`
(`info-laya-native.json`; skip the `--limit 5` smoke run the second time). Check in the info
file that `engine.native_types` lists `noul` and `score` for the native run and only `choice`
for the emulated one. Then `docker rm -f jev-qt`.

## Step 4: Kev-0.8B, emulated then native

```powershell
docker compose -f docker-compose.kev.yml pull
docker compose -f docker-compose.kev.yml up -d
```

The first start downloads about 2 GB and can take several minutes. Wait until
`docker compose -f docker-compose.kev.yml ps` shows the bridge `healthy`, then:

```powershell
Invoke-RestMethod http://localhost:8000/v1/info | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 "$out/info-kev-emulated.json"
python examples/eval/question_types/run_eval.py --dataset $ds --out-dir $out run --url http://localhost:8000 --label kev-emulated
$env:JEV_NATIVE_TYPES = "all"; docker compose -f docker-compose.kev.yml up -d
```

Wait for `healthy`, check that `/v1/info` now lists `noul` and `score` in
`engine.native_types`, save it as `info-kev-native.json`, run with the label `kev-native`,
then:

```powershell
Remove-Item Env:JEV_NATIVE_TYPES; docker compose -f docker-compose.kev.yml down
```

## Step 5: report and notes

```powershell
python examples/eval/question_types/run_eval.py --out-dir $out report
```

Complete `NOTES.md` with:

- end time, and the wall time of each full run (the runner prints per-request latency; the
  predictions files carry `latency_ms`);
- any failure, retry or anomaly, with the exact command and error;
- labels you now think are ambiguous (id and why), without changing them;
- nothing else: no interpretation of which path is better.

## Step 6: commit and push

```powershell
git add $out
git status
```

`git status` must show nothing staged outside the results folder (the dataset was committed in
step 1). Then:

```powershell
git commit -m "Add local question-types results $d (Laya and Kev, native vs emulated)"
git push -u origin "eval/question-types-$d"
```

Expected content of the results folder: `REPORT.md`, `NOTES.md`, four `info-*.json`, and for
each of `laya-emulated`, `laya-native`, `kev-emulated`, `kev-native` a `.predictions.jsonl`
and a `.summary.json`. End by printing the branch name and `REPORT.md`.
