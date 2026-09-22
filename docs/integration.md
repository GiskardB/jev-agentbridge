# Integration Guide

## Generic pattern

```
Agent → Tool → POST /v1/decide → Bridge → Decision
```

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
