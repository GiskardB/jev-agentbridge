# OpenCode + JEV-CPU-AgentBridge Example

This example demonstrates using OpenCode with OpenRouter for LLM capabilities and JEV-CPU-AgentBridge for local discrete decision-making.

## Architecture

```
┌─────────────────┐    ┌────────────────────┐
│   OpenCode CLI  │    │  JEV-CPU-AgentBridge│
│ (with OpenRouter)│──►│ (local CPU inference)│
└─────────────────┘    └────────────────────┘
       │                        │
       │  POST /v1/decide      │
       └──────────────────────┘
```

## Running the Example

```bash
# 1. Start JEV-CPU-AgentBridge
docker compose -f examples/opencode-docker/docker-compose.yml up --build jev

# 2. Run the integration test
docker compose -f examples/opencode-docker/docker-compose.yml --build opencode

# Or use docker-compose directly
docker compose up --build
```

## Comparison: JEV vs OpenRouter

| Aspect | JEV-CPU-AgentBridge | OpenRouter |
|---|---|---|
| **Latency** | ~700ms (local CPU) | ~1400ms (remote inference) |
| **Cost** | $0 (local CPU only) | ~45 tokens per request |
| **Network** | None required (after model download) | Requires API key + internet |
| **Best for** | Small discrete decisions | Generative tasks, open-ended reasoning |
| **Privacy** | Data stays local | Data sent to remote API |

## Files

- `Dockerfile` - OpenCode CLI with httpx for OpenRouter calls
- `docker-compose.yml` - Services: jev (AgentBridge) + opencode (OpenCode)
- `test_integration.py` - Comparison test script

## OpenRouter Configuration

Set the API key in your environment:

```bash
export OPENROUTER_API_KEY="sk-or-..."
export OPENROUTER_MODEL="qwen/qwen3-32b"
```

Then run:

```bash
docker compose up --build
```

The OpenCode service will automatically pick up the environment variables and run the integration test.