# Integration Guide

## Generic pattern

```
Agent → Tool → POST /v1/decide → Bridge → Decision
```

## Choosing the engine

The Bridge API is identical for every engine. The only difference is the image tag you run:

| Image tag | Runtime engine | What it is |
|---|---|---|
| `:latest` / `:semif` | `semif` (default) | Qwen3-0.6B causal LM, next-token scoring, CPU only |
| `:laya` | `laya` | Non-autoregressive encoder models, CPU only |
| `:rizzoflow` | `rizzoflow` | HTTP client to a separately-run RizzoFlow server — also usable as a general JEV integration point |

The engine is baked into the image by the release pipeline, so `JEV_ENGINE` is not needed when
you pull the matching tag:

```bash
docker run -p 8000:8000 ghcr.io/giskardb/jev-agentbridge:latest   # semif
docker run -p 8000:8000 ghcr.io/giskardb/jev-agentbridge:laya     # laya
docker run -p 8000:8000 ghcr.io/giskardb/jev-agentbridge:rizzoflow # rizzoflow
```

For `rizzoflow`, set `JEV_RIZZOFLOW_URL` (default `http://localhost:8017`) to point at the
RizzoFlow server you run separately. The `:rizzoflow` image is a general JEV integration point —
you can replace the URL and talk to any RizzoFlow-compatible server you run yourself.

## Python SDK

```python
from jev_agent_bridge import AgentBridgeClient

client = AgentBridgeClient("http://localhost:8000")
result = client.decide(
    state="Deployment failed",
    question="What should happen next?",
    options=[
        {"id": "retry", "description": "Retry deployment"},
        {"id": "abort", "description": "Abort deployment"},
    ],
)
print(result["decision"]["id"])
```

## TypeScript SDK

```ts
import { AgentBridgeClient } from '@jev-cpu/agentbridge'
const client = new AgentBridgeClient('http://localhost:8000')
const result = await client.decide({...})
```

## OpenCode integration

See `integrations/opencode/`.
