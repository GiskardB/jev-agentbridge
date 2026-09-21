# API Reference

## `POST /v1/decide`

Evaluate a single decision.

```json
{
  "state": "The deployment failed.",
  "question": "What should happen next?",
  "options": [
    { "id": "retry", "description": "Retry the deployment" },
    { "id": "abort", "description": "Abort the deployment" }
  ]
}
```

Returns `DecisionResponse`.

## `POST /v1/decide/batch`

Evaluate multiple decisions sharing one state.

```json
{
  "state": { "deployment": "api-v2", "status": "failed" },
  "decisions": [
    { "question": "Should we retry?", "options": [...] },
    { "question": "Should we notify?", "options": [...] }
  ]
}
```

Returns `BatchDecideResponse` with one `DecisionResponse` per decision.

## `GET /health`

Process health. Always returns `{"status": "ok"}`.

## `GET /ready`

Model readiness. Returns `{"status": "ready", "model": "..."}` after initialization.

## `GET /v1/info`

Engine information.
