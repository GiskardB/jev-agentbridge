# API Reference (v1)

The contract is the same for every engine (`semif`, `laya`, `rizzoflow`, ...). The running
service publishes it as OpenAPI at `GET /openapi.json`, with interactive docs at `/docs`.

## `POST /v1/decide`

```json
{
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
| `state` | string \| object \| array | Compact evidence. Objects are serialized as sorted JSON by prompt-based adapters. |
| `question` (alias `criterion`) | string | The decision criterion. |
| `options` | 2–16 `{id, description}` | Ids must be unique (`DUPLICATE_OPTION_ID` otherwise). |
| `min_selected_probability` | number 0..1, optional | Acceptance threshold for this call. Default: `JEV_MIN_SELECTED_PROBABILITY` (0.60). |

Response `200` (this example comes from the `:semif` image; other engines return the same
fields with their own `engine_details`):

```json
{
  "decision": { "id": "retry", "description": "Retry the deployment" },
  "probabilities": { "retry": 0.81, "abort": 0.19 },
  "selected_probability": 0.81,
  "accepted": false,
  "threshold": 0.85,
  "metadata": {
    "engine": "semif",
    "model": "Qwen/Qwen3-0.6B",
    "model_revision": "main",
    "mode": "direct",
    "latency_ms": 453.6,
    "input_tokens": 65,
    "engine_details": { "prompt_version": "direct-options-v1", "prompt_sha256": "..." }
  }
}
```

- `probabilities` always has one entry per option **id**, in request order, for every engine.
- `accepted` is `selected_probability >= threshold`. `false` means "not confident enough, decide
  yourself" (e.g. fall back to the LLM). It does not mean "no".
- `metadata.engine`, `model`, `model_revision`, `mode` and `latency_ms` are always present.
  `input_tokens` is present when the adapter knows it. `engine_details` is adapter-specific
  and not part of the stable contract.

## `POST /v1/decide/batch`

Several decisions sharing one state. Engines with a native shared path evaluate them together
(semif reuses the KV cache of the shared prefix).

```json
{
  "state": { "deployment": "api-v2", "status": "failed" },
  "min_selected_probability": 0.8,
  "decisions": [
    { "question": "Should we retry?", "options": [...] },
    { "question": "Should we notify?", "options": [...], "min_selected_probability": 0.6 }
  ]
}
```

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
  "version": "0.4.0",
  "engine": { "name": "laya", "model": "convaiinnovations/laya", "revision": "main", "native_batch": true },
  "available_engines": ["laya", "rizzoflow", "semif"],
  "min_options": 2,
  "max_options": 16,
  "default_min_selected_probability": 0.6,
  "supported_modes": ["direct", "shared"]
}
```

## Errors

Every error, whatever produces it, has the same envelope:

```json
{ "error": { "code": "DUPLICATE_OPTION_ID", "message": "...", "request_id": "..." } }
```

| HTTP | `code` | When |
|---|---|---|
| 422 | `INVALID_REQUEST` | Schema violation: missing field, 1 or 17+ options, threshold outside 0..1 |
| 400 | `INVALID_OPTIONS` / `DUPLICATE_OPTION_ID` / `INVALID_REQUEST` | Semantically invalid decision |
| 413 | `INPUT_TOO_LARGE` | Prompt above the adapter's limit (semif: `JEV_MAX_INPUT_TOKENS`) |
| 503 | `MODEL_NOT_READY` | Engine still loading |
| 503 | `ENGINE_UNAVAILABLE` | Remote backend unreachable (e.g. RizzoFlow server down) |
| 500 | `ENGINE_ERROR` | Adapter failure or output outside the contract |

Clients using JEV as a gate should treat any 5xx the same as `accepted=false` and fall back.
The SDK helpers already do.

## MCP

The same decisions are available as Model Context Protocol tools at `/mcp` (streamable HTTP):
`jev_decide`, `jev_decide_batch` and `jev_info`, with the same arguments, results and error codes
as the endpoints above. See [mcp.md](mcp.md).
