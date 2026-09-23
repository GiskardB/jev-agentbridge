# Model routing dataset

Labelled dataset for one concrete use of JEV as a gate in front of an LLM: deciding **which
model tier should answer a user request**, so that easy requests go to a cheap model and only
hard ones reach the expensive one.

To run the evaluation, follow [INSTRUCTIONS.md](INSTRUCTIONS.md). They are written so that
another agent can execute them end to end.

## Contents

`model_routing.jsonl`: 240 rows, balanced.

| | small | medium | large | Total |
|---|---|---|---|---|
| Italian (`it`) | 40 | 40 | 40 | 120 |
| English (`en`) | 40 | 40 | 40 | 120 |

Each row is a normal `jev-eval` row plus two extra fields:

```json
{
  "id": "it-small-01",
  "lang": "it",
  "state": "Ciao, come stai?",
  "question": "Quale modello deve gestire questa richiesta?",
  "options": [{"id": "small", "description": "..."}, {"id": "medium", "description": "..."}, {"id": "large", "description": "..."}],
  "expected": "small"
}
```

`question` and the option descriptions are in the row's language. Italian and English rows
are different requests, not translations of each other.

## Labelling rules

Label by **what a good answer requires**, not by topic or by length of the request.

| Label | Use when a good answer needs... | Examples |
|---|---|---|
| `small` | A fact, a lookup, a one-line transformation or a courtesy reply. A small model would answer it as well as a large one. | Greeting, "what is the capital of...", unit conversion, translating or fixing one sentence, FAQ about the service |
| `medium` | One standard piece of writing or code with a clear spec, or explaining one concept. No real trade-offs to weigh. | Email, summary of a given text, a function or a query, explaining a concept, fixing a clear error |
| `large` | Several reasoning steps, weighing trade-offs, analysing a lot of material, designing a system, or diagnosing an unclear problem. | Architecture, root-cause analysis, comparing options with a recommendation, planning, proofs, long-document review |

Tie-breakers:
- If a request could be answered adequately at a lower tier, pick the lower tier. Routing
  exists to save cost.
- "Explain X" is `medium`. "Explain X **and decide** / compare / design / apply it to our
  case" is `large`.
- A short error message with an obvious fix is `medium`. An intermittent or unexplained
  failure is `large`.

## Limits

- **Synthetic.** The requests were written by hand for this evaluation, not taken from real
  traffic. One author wrote and labelled them all, with no second annotator. Real traffic is
  messier: longer messages, mixed languages, pasted logs, follow-ups that depend on earlier
  turns.
- **Attachments are described, not included.** For example "Analyze these three years of
  financial statements..." has no data attached. The label reflects the request as a router
  would see it.
- Classes are balanced (1/3 each); real traffic usually is not. Re-weight or use a real
  sample before estimating savings.

## Next step: real data

For a decision you can act on, repeat the evaluation on 200–500 **real** requests from your
logs, labelled with the rules above (ideally by two people, keeping only the rows they agree
on). Save them in the same JSONL format with unique `id`s and run the same commands with the
dataset option placed before the subcommand:

```
python run_eval.py --dataset your_file.jsonl run --url http://localhost:8000 --label laya-en-real
```
