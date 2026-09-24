# API Reference (v1)

The contract is the same for every engine (`semif`, `laya`, `kev`, `rizzoflow`, ...). The
running service publishes it as OpenAPI at `GET /openapi.json`, with interactive docs at `/docs`.

## Question types

A decision has one of the three JEV question types, set with `type`:

| `type` | Asks | Request | Answer |
|---|---|---|---|
| `choice` (default) | Which category? | `options`: 2–16 `{id, description}` | `decision` = the most likely option |
| `noul` | Yes or no? | no `options`; optional `yes_description` / `no_description` | `decision.id` = `yes` or `no`; `noul` = P(yes) |
| `score` | Where on this scale? | `options`: 2–16 levels, **lowest first** | `decision` = the most likely level; `score` = expected level, from 0 (first level) to n−1 |

Use the type that matches the question. The gain is on your side of the call: a `noul` answer
is directly `yes`/`no` with P(yes), and a `score` answer keeps the order of the scale (`score`
2.4 on levels 0–3 reads "between the third and fourth level, closer to the third"), which a
plain choice does not give you.

**How the engine is asked.** By default the Bridge asks every noul and score question as a
choice over the same options (`yes`/`no`, or the levels) and computes `noul` and `score` itself.
Several engines also have a native path for these types, and `JEV_NATIVE_TYPES` turns it on:

| Engine | Native path available |
|---|---|
| `laya` | noul, score (dedicated heads) |
| `kev`, `systemone` | noul, score (System One `noul` / `score` questions) |
| `rizzoflow` | noul (as `boolean`), score |
| `semif` | none: always asked as a choice |

`JEV_NATIVE_TYPES`: `false` (default), `true` / `all`, or a list such as `noul`. The response is
the same either way; `metadata.native_type` says which path was used and `GET /v1/info` lists
the types that are native in the running configuration.

Native is off by default because on the bundled
[question-types suite](../examples/eval/question_types) (80 questions, Italian and English) it
was never better:

| Engine | noul native / emulated | score exact, native / emulated |
|---|---|---|
| Kev-0.8B | 85.4% / 85.4% | 68.8% / 71.9% |
| Laya multilingual | 81.2% / 79.2% | 40.6% / 62.5% |
| Laya English | 79.2% / 83.3% | 43.8% / 46.9% |

Kev asks a noul internally as a choice between "no" and "yes", so the two paths are nearly the
same computation. Laya's native score head pulls answers toward the middle levels, even
confidently (42.9% accurate above p = 0.8 on the multilingual model). The noul differences are
one or two questions out of 48, within noise. Measure on your own questions before turning
native on.

## `POST /v1/decide`

```json
{
  "type": "choice",
  "state": "The deployment failed.",
  "question": "What should happen next?",
  "options": [
    { "id": "retry", "description": "Retry the deployment" },
    { "id": "abort", "description": "Abort the deployment" }
  ],
  "min_selected_probability": 0.85
}
```

| Field | Type | Notes |
|---|---|---|
| `type` | `choice` \| `noul` \| `score`, optional | Default `choice`. See [Question types](#question-types). |
| `state` | string \| object \| array | Compact evidence. Objects are serialized as sorted JSON by prompt-based adapters. |
| `question` (alias `criterion`) | string | The decision criterion. |
| `options` | 2–16 `{id, description}` | Required for `choice` and `score` (levels, lowest first); not allowed for `noul`. Ids must be unique (`DUPLICATE_OPTION_ID` otherwise). |
| `yes_description`, `no_description` | string, optional | `noul` only: what "yes" and "no" mean, when the question alone is not clear. |
| `min_selected_probability` | number 0..1, optional | Acceptance threshold for this call. Default: `JEV_MIN_SELECTED_PROBABILITY` (0.60). |

Response `200` (this example comes from the `:semif` image; other engines return the same
fields with their own `engine_details`):

```json
{
  "type": "choice",
  "decision": { "id": "retry", "description": "Retry the deployment" },
  "probabilities": { "retry": 0.81, "abort": 0.19 },
  "selected_probability": 0.81,
  "accepted": false,
  "threshold": 0.85,
  "score": null,
  "noul": null,
  "metadata": {
    "engine": "semif",
    "model": "Qwen/Qwen3-0.6B",
    "model_revision": "main",
    "mode": "direct",
    "latency_ms": 453.6,
    "native_type": true,
    "input_tokens": 65,
    "engine_details": { "prompt_version": "direct-options-v1", "prompt_sha256": "..." }
  }
}
```

- `probabilities` always has one entry per option **id**, in request order, for every engine.
- `accepted` is `selected_probability >= threshold`. `false` means "not confident enough, decide
  yourself" (e.g. fall back to the LLM). It does not mean "no".
- `metadata.engine`, `model`, `model_revision`, `mode`, `latency_ms` and `native_type` are
  always present.
  `input_tokens` is present when the adapter knows it. `engine_details` is adapter-specific
  and not part of the stable contract.

The examples below use illustrative values.

### Yes/no (`noul`)

```json
{
  "type": "noul",
  "state": "Customer: I bought these shoes 10 days ago. Policy: returns within 30 days.",
  "question": "Is the return request within policy?"
}
```

```json
{
  "type": "noul",
  "decision": { "id": "yes", "description": "Yes" },
  "probabilities": { "yes": 0.93, "no": 0.07 },
  "selected_probability": 0.93,
  "accepted": true,
  "threshold": 0.6,
  "score": null,
  "noul": 0.93,
  "metadata": { "engine": "kev", "native_type": false, "...": "..." }
}
```

`accepted` works as for a choice: the most likely answer (yes *or* no) must reach the
threshold. `accepted: false` means "not sure", not "no".

### Ordinal scale (`score`)

```json
{
  "type": "score",
  "state": "Ticket: our largest customer has a demo in 40 minutes and SSO login is broken.",
  "question": "How urgent is the request?",
  "options": [
    { "id": "low", "description": "Low: can wait days" },
    { "id": "medium", "description": "Medium: within the day" },
    { "id": "high", "description": "High: within the hour" },
    { "id": "critical", "description": "Critical: right now, damage ongoing" }
  ]
}
```

```json
{
  "type": "score",
  "decision": { "id": "high", "description": "High: within the hour" },
  "probabilities": { "low": 0.01, "medium": 0.08, "high": 0.62, "critical": 0.29 },
  "selected_probability": 0.62,
  "accepted": true,
  "threshold": 0.6,
  "score": 2.19,
  "noul": null,
  "metadata": { "engine": "kev", "native_type": false, "...": "..." }
}
```

`score` is the expected level (Σ index × probability), so 2.19 reads as "high, leaning
critical". Map it back to your own scale with `score / (len(options) - 1)` for 0..1.

## `POST /v1/decide/batch`

Several decisions sharing one state. Engines with a native shared path evaluate them together
(semif reuses the KV cache of the shared prefix).

```json
{
  "state": { "deployment": "api-v2", "status": "failed" },
  "min_selected_probability": 0.8,
  "decisions": [
    { "question": "Which team owns it?", "options": [...] },
    { "type": "noul", "question": "Should we notify the customer?", "min_selected_probability": 0.6 },
    { "type": "score", "question": "How severe is it?", "options": [...] }
  ]
}
```

Each item takes the same fields as `/v1/decide` except `state`, and types can be mixed.

Threshold precedence: per-decision value, then batch-level value, then service default.
Returns `{"decisions": [<DecideResponse>, ...]}` in request order, with `metadata.mode = "shared"`.
`latency_ms` is the wall time of the whole batch.

## `GET /health`

Process liveness. Always `{"status": "ok"}`, even while the engine is loading.

## `GET /ready`

`200 {"status": "ready", "engine": "laya", "model": "convaiinnovations/laya"}` once the adapter is
loaded, otherwise `503` with `MODEL_NOT_READY`.

## `GET /v1/info`

```json
{
  "api_version": "v1",
  "version": "0.6.0",
  "engine": {
    "name": "laya",
    "model": "convaiinnovations/laya",
    "revision": "multilingual",
    "native_batch": true,
    "native_types": ["choice"]
  },
  "available_engines": ["kev", "laya", "rizzoflow", "semif", "systemone"],
  "min_options": 2,
  "max_options": 16,
  "default_min_selected_probability": 0.6,
  "supported_modes": ["direct", "shared"],
  "supported_types": ["choice", "noul", "score"]
}
```

## Errors

Every error, whatever produces it, has the same envelope:

```json
{ "error": { "code": "DUPLICATE_OPTION_ID", "message": "...", "request_id": "..." } }
```

| HTTP | `code` | When |
|---|---|---|
| 422 | `INVALID_REQUEST` | Schema violation: missing field, 1 or 17+ options, threshold outside 0..1, `options` on a `noul` or missing on a `choice`/`score` |
| 400 | `INVALID_OPTIONS` / `DUPLICATE_OPTION_ID` / `INVALID_REQUEST` | Semantically invalid decision |
| 413 | `INPUT_TOO_LARGE` | Prompt above the adapter's limit (semif: `JEV_MAX_INPUT_TOKENS`) |
| 503 | `MODEL_NOT_READY` | Engine still loading |
| 503 | `ENGINE_UNAVAILABLE` | Remote backend unreachable (e.g. RizzoFlow server down) |
| 500 | `ENGINE_ERROR` | Adapter failure or output outside the contract |

Clients using JEV as a gate should treat any 5xx the same as `accepted=false` and fall back.
The SDK helpers already do.

## MCP

The same decisions are available as Model Context Protocol tools at `/mcp` (streamable HTTP):
`jev_yes_no`, `jev_choose`, `jev_score`, `jev_decide_batch` and `jev_info`, with the same
results and error codes as the endpoints above. See [mcp.md](mcp.md).
