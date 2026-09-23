#!/usr/bin/env node
// Structural smoke test for the OpenCode plugin.
//
// OpenCode's plugin loader silently ignores tools registered under the wrong
// shape — no error, the tool just never appears (this bit us once: the
// plugin used to export `{ 'tool.jev_decide': {...} }` instead of
// `{ tool: { jev_decide: {...} } }`, and nothing surfaced the mistake short
// of loading it in a real OpenCode instance). This test catches that class
// of regression without needing a running opencode server.

import assert from "node:assert/strict";
import { existsSync, rmSync } from "node:fs";
import { join } from "node:path";
import plugin from "./plugin/jev-cpu-agentbridge.mjs";

const installedSkillDir = join(process.cwd(), ".opencode", "skills", "jev-cpu-agentbridge");
// This test's cwd is this package's own directory, so it's always safe to
// remove whatever the plugin installs here — not a real project's .opencode/.
rmSync(join(process.cwd(), ".opencode"), { recursive: true, force: true });

const hooks = await plugin({});

assert.ok(hooks.tool, "plugin must export a top-level `tool` map");
assert.ok(hooks.tool.jev_decide, "jev_decide must be registered under hooks.tool");

const def = hooks.tool.jev_decide;
assert.equal(typeof def.execute, "function", "jev_decide.execute must be a function");
assert.ok(def.args, "jev_decide must declare args");
for (const key of ["state", "question", "options"]) {
  assert.ok(key in def.args, `jev_decide.args must declare "${key}"`);
}

assert.ok(
  existsSync(join(installedSkillDir, "SKILL.md")),
  "plugin load must auto-install the bundled skill into .opencode/skills/",
);

rmSync(join(process.cwd(), ".opencode"), { recursive: true, force: true });

console.log("OK: jev_decide registered with the expected shape, and the skill auto-installs");
