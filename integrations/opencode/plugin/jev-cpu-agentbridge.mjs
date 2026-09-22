// JEV-CPU-AgentBridge — OpenCode plugin.
//
// Provides a single callable tool:
//   jev_decide
// which calls POST /v1/decide on the JEV-CPU-AgentBridge service.
//
// OpenCode loads this as a server plugin. Add to your opencode.json:
//   { "plugin": ["./integrations/opencode/plugin/jev-cpu-agentbridge.mjs"] }
//
// Requires @opencode-ai/plugin to be resolvable from this file (npm install
// in integrations/opencode/ — see package.json there).

import { tool } from "@opencode-ai/plugin";

export default async ({ client } = {}) => {
  const log = (level, message) => {
    try {
      client && client.app && client.app.log({ body: { service: "jev-cpu-agentbridge", level, message } });
    } catch (e) {}
  };

  const baseUrl = process.env.JEV_CPU_AGENTBRIDGE_URL || "http://localhost:8000";

  return {
    tool: {
      jev_decide: tool({
        description:
          "Evaluate a small discrete decision (2-16 options) using the local, CPU-only " +
          "JEV-CPU-AgentBridge instead of the main model. Use this for routine binary/few-way " +
          "judgment calls (retry vs abort, escalate vs log, accept vs reject), not open-ended reasoning.",
        args: {
          // z.record() crashes OpenCode 1.18.x's tool-schema serializer (ToolRegistry.state),
          // so `state` (string | dict | list per the Bridge API) is typed as z.any() here.
          state: tool.schema.any().describe("The evidence/state to evaluate the decision against."),
          question: tool.schema.string().describe("The decision criterion, e.g. 'What should happen next?'"),
          options: tool.schema
            .array(
              tool.schema.object({
                id: tool.schema.string(),
                description: tool.schema.string(),
              }),
            )
            .min(2)
            .max(16)
            .describe("2-16 candidate options to choose from."),
        },
        async execute(args) {
          const response = await fetch(`${baseUrl}/v1/decide`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(args),
          });
          const body = await response.json();
          if (!response.ok) {
            const message = body.error?.message || `Request failed: ${response.status}`;
            log("error", `jev_decide failed: ${message}`);
            throw new Error(message);
          }
          return {
            title: `${body.decision.id} (p=${body.selected_probability.toFixed(2)})`,
            output: JSON.stringify(body, null, 2),
            metadata: body.metadata,
          };
        },
      }),
    },
  };
};
