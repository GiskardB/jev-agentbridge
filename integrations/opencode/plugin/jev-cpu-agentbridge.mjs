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
import { existsSync, mkdirSync, cpSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// OpenCode only auto-discovers skills from .opencode/skills/<name>/ (or the
// .claude/.agents/global equivalents) — it has no API for a plugin to
// register a skill in code. So on first load we copy our bundled skill into
// the project's .opencode/skills/, best-effort, without clobbering an
// existing copy (e.g. one the user customized).
// ponytail: copy-once, no version check — a plugin update won't refresh an
// already-installed skill; delete .opencode/skills/jev-cpu-agentbridge/ to
// pick up a newer bundled version.
function installSkill(log) {
  try {
    const here = dirname(fileURLToPath(import.meta.url));
    const src = join(here, "..", "skills", "jev-cpu-agentbridge");
    const dest = join(process.cwd(), ".opencode", "skills", "jev-cpu-agentbridge");
    if (existsSync(src) && !existsSync(dest)) {
      mkdirSync(dirname(dest), { recursive: true });
      cpSync(src, dest, { recursive: true });
      log("info", `jev-cpu-agentbridge: installed skill to ${dest}`);
    }
  } catch (e) {
    log(
      "warn",
      `jev-cpu-agentbridge: could not auto-install the skill (${e.message}); copy ` +
        "skills/jev-cpu-agentbridge/ into .opencode/skills/ manually if needed.",
    );
  }
}

export default async ({ client } = {}) => {
  const log = (level, message) => {
    try {
      client && client.app && client.app.log({ body: { service: "jev-cpu-agentbridge", level, message } });
    } catch (e) {}
  };

  installSkill(log);

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
          log(
            "info",
            `jev_decide -> ${body.decision.id} (accepted=${body.accepted}, p=${body.selected_probability.toFixed(2)}, ` +
              `engine=${body.metadata?.engine}, ${body.metadata?.latency_ms}ms)`,
          );
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
