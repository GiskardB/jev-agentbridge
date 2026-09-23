# OpenCode Integration for JEV-CPU-AgentBridge

This integration provides a callable tool `jev_decide` that maps the OpenCode agent's decision request to `POST /v1/decide` on the JEV-CPU-AgentBridge service.

## Installation

### Option A: from npm (recommended)

Add the package name straight to your `opencode.json` — OpenCode installs and caches it for you,
no local clone needed:

```json
{
  "plugin": ["opencode-jev-agentbridge"]
}
```

or via the CLI, which does the same thing:

```bash
opencode plugin opencode-jev-agentbridge
```

### Option B: from this repo (local path)

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

Verify the tool actually registers without starting a full OpenCode session:

```bash
cd integrations/opencode && npm test
```

### Point it at your running Bridge instance

```bash
export JEV_CPU_AGENTBRIDGE_URL=http://localhost:8000
```

### Enable the skill (recommended)

The tool alone only gets called when the model explicitly decides to reach for it. The skill in
`skills/jev-cpu-agentbridge/` teaches the agent *when* that is, and OpenCode surfaces its
description automatically on every step once it's discoverable — but only if it lives in one of
OpenCode's skill paths. Copy or symlink it in:

```bash
# per-project
mkdir -p .opencode/skills && cp -r <path-to-this-package>/skills/jev-cpu-agentbridge .opencode/skills/

# or globally, for every project
mkdir -p ~/.config/opencode/skills && cp -r <path-to-this-package>/skills/jev-cpu-agentbridge ~/.config/opencode/skills/
```

If installed from npm, `<path-to-this-package>` is wherever OpenCode cached it (typically under
`~/.cache/opencode/node_modules/opencode-jev-agentbridge/`); if installed from this repo, it's
`integrations/opencode/`.

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

See [`skills/jev-cpu-agentbridge/SKILL.md`](skills/jev-cpu-agentbridge/SKILL.md) for when to use
JEV and when not to — install it per the "Enable the skill" step above so OpenCode actually loads
it.