# OpenCode Integration for JEV-CPU-AgentBridge

This integration provides a callable tool `jev_decide` that maps the OpenCode agent's decision request to `POST /v1/decide` on the JEV-CPU-AgentBridge service.

## Installation

1. Install the plugin's own dependency (the real `@opencode-ai/plugin` SDK the tool is built with):

   ```bash
   cd integrations/opencode && npm install
   ```

2. Add the plugin to your `opencode.json`:

   ```json
   {
     "plugin": ["./integrations/opencode/plugin/jev-cpu-agentbridge.mjs"]
   }
   ```

3. Point it at your running Bridge instance:

   ```bash
   export JEV_CPU_AGENTBRIDGE_URL=http://localhost:8000
   ```

Verify the tool actually registers without starting a full OpenCode session:

```bash
cd integrations/opencode && npm test
```

## Usage

Once installed, the agent calls the `jev_decide` tool with the canonical decision request:

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

The tool result's `output` field is the Bridge's JSON response as a string:

```json
{
  "decision": { "id": "retry", "description": "Retry the deployment" },
  "probabilities": { "A": 0.81, "B": 0.12, "C": 0.07 },
  "selected_probability": 0.81,
  "accepted": true,
  "metadata": { "engine": "semif", "model": "Qwen/Qwen3-0.6B", "latency_ms": 210.4 }
}
```

*(`engine` in the metadata reflects the image you ran — `semif` is the default.)*

Verified end-to-end with the real `opencode` CLI (`opencode-ai` on npm) and a live OpenRouter model:
the agent called `jev_decide`, got back `retry` at p=0.77, and reported it correctly. Two real bugs
were found and fixed doing that verification — see [CHANGELOG.md](../../CHANGELOG.md):

- The tool was registered under the wrong shape (`{'tool.jev_decide': ...}` instead of
  `{tool: {jev_decide: ...}}`) — OpenCode's loader ignored it silently, no error, no log line.
- The `state` argument's schema used `z.record()`, which crashes OpenCode 1.18.x's internal
  tool-schema serializer (`ToolRegistry.state`); it's typed as `z.any()` instead.

## SKILL.md

See `skill/SKILL.md` for when to use JEV and when not to.