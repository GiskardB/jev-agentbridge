# OpenCode Integration for JEV-CPU-AgentBridge

This integration provides a callable tool `jev_decide` that maps the OpenCode agent's decision request to `POST /v1/decide` on the JEV-CPU-AgentBridge service.

## Installation

Add the plugin to your `opencode.json`:

```json
{
  "plugin": ["./integrations/opencode/plugin/jev-cpu-agentbridge.mjs"]
}
```

Or set the URL via environment variable:

```bash
export JEV_CPU_AGENTBRIDGE_URL=http://localhost:8000
```

## Usage

Once installed, the agent can call the `jev_decide` tool with the canonical decision request:

```json
{
  "state": "A deployment failed because the health check timed out.",
  "question": "What should happen next?",
  "options": [
    { "id": "retry", "description": "Retry the deployment" },
    { "id": "abort", "description": "Abort the deployment" },
    { "id": "escalate", "description": "Escalate to a human operator" }
  ]
}
```

The tool returns:

```json
{
  "decision": { "id": "retry", "description": "Retry the deployment" },
  "probabilities": { "retry": 0.81, "abort": 0.12, "escalate": 0.07 },
  "selected_probability": 0.81,
  "accepted": true,
  "metadata": { ... }
}
```

## SKILL.md

See `skill/SKILL.md` for when to use JEV and when not to.