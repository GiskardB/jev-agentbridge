# JEV-CPU-AgentBridge

JEV-CPU-AgentBridge is a local decision gateway for AI agents. It evaluates small
discrete choices using a CPU-hosted decision model and returns a structured
result, allowing an agent to reserve its primary generative model for tasks
that actually require generation or open-ended reasoning.

## Features

- **Local-first**: runs entirely on CPU, no external API calls
- **CPU-first**: uses Qwen/Qwen3-0.6B with PyTorch float32
- **Provider-agnostic**: no dependency on OpenAI, Anthropic, or any other LLM provider
- **Agent-oriented**: structured decision requests and responses
- **Deterministic/reproducible**: pinned model revisions and prompt versioning

## Quick start

```bash
docker compose up --build
```

Then:

```bash
curl http://localhost:8000/health
```

## First decision

```bash
curl -X POST http://localhost:8000/v1/decide \
  -H "Content-Type: application/json" \
  -d '{
    "state": "A deployment failed because the health check timed out.",
    "question": "What should happen next?",
    "options": [
      {"id": "retry", "description": "Retry the deployment"},
      {"id": "abort", "description": "Abort the deployment"}
    ]
  }'
```

## Python SDK

```python
from jev_cpu_agentbridge import AgentBridgeClient

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
import { AgentBridgeClient } from "@jev-cpu/agentbridge";

const client = new AgentBridgeClient("http://localhost:8000");
const result = await client.decide({
  state: "Deployment failed",
  question: "What should happen next?",
  options: [
    { id: "retry", description: "Retry deployment" },
    { id: "abort", description: "Abort deployment" },
  ],
});
console.log(result.decision.id);
```

## OpenCode integration

See `integrations/opencode/`.

## Documentation

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Integration](docs/integration.md)
- [Performance](docs/performance.md)

## License

MIT — see [LICENSE](LICENSE).