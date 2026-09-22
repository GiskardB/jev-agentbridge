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
import plugin from "./plugin/jev-cpu-agentbridge.mjs";

const hooks = await plugin({});

assert.ok(hooks.tool, "plugin must export a top-level `tool` map");
assert.ok(hooks.tool.jev_decide, "jev_decide must be registered under hooks.tool");

const def = hooks.tool.jev_decide;
assert.equal(typeof def.execute, "function", "jev_decide.execute must be a function");
assert.ok(def.args, "jev_decide must declare args");
for (const key of ["state", "question", "options"]) {
  assert.ok(key in def.args, `jev_decide.args must declare "${key}"`);
}

console.log("OK: jev_decide registered with the expected shape");
