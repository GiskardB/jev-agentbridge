# Changelog

## Unreleased

- Add: the OpenCode plugin is now published to npm as
  [`opencode-jev-agentbridge`](https://www.npmjs.com/package/opencode-jev-agentbridge) —
  `{"plugin": ["opencode-jev-agentbridge"]}` in `opencode.json` is now enough, no local clone
  needed. Released independently from the Docker images via `opencode-vX.Y.Z` tags
  (`.github/workflows/publish-opencode-plugin.yml`), starting at `0.1.0`.
- Fix: the skill (`SKILL.md`) lived at `integrations/opencode/skill/SKILL.md`, a path OpenCode
  never scans for auto-discovery (it only loads `skills/<name>/SKILL.md` under `.opencode/`,
  `.claude/`, `.agents/`, or the global skills dir) — the agent never saw it and only called
  `jev_decide` when told to explicitly. Moved to `integrations/opencode/skills/jev-cpu-agentbridge/`
  and rewrote it: a tighter decision gate, explicit false-positive cases, and the `accepted=false`
  semantics (not "no", not "retry" — hand back to the agent), which were undocumented before.
- Note: publishing found a real gotcha — `npm publish` returns `403 Forbidden` for a Granular
  Access Token unless "bypass 2FA" is explicitly enabled on it; a classic **Automation** token
  works out of the box and is what `NPM_TOKEN` should be.
- Add: the plugin now auto-installs its bundled skill into `.opencode/skills/jev-cpu-agentbridge/`
  on first load (copy-once, won't clobber a customized copy) — there's no OpenCode plugin API to
  register a skill in code, only filesystem discovery, so this closes the gap without the
  developer having to copy anything by hand. Global install (`~/.config/opencode/skills/`) is
  still a manual step, documented in `integrations/opencode/README.md`.
- Add: `jev_decide` now logs a one-line summary (`decision`, `accepted`, `selected_probability`,
  `engine`, `latency_ms`) on every successful call, not just on failure — makes it possible to
  confirm from OpenCode's own logs whether a given session actually engaged JEV, without relying
  on scrolling the transcript.
- Fix: `0.1.0`-`0.1.2` installed silently but never actually loaded — `package.json` had no `main`
  or `exports` field, so OpenCode's npm-plugin resolver found no entrypoint to run
  (`opencode plugin <name>` surfaces this as "No plugin targets found" / "does not expose plugin
  entrypoints in package.json"; loading it via `opencode.json`'s `plugin` array failed the same
  way but logged nothing at all — the package just sat in `~/.cache/opencode/packages/` inert).
  Installing from a local file path (`./plugin/jev-cpu-agentbridge.mjs`) was never affected, since
  that bypasses entrypoint resolution entirely — only the npm install path was broken. Fixed by
  adding `"main": "./plugin/jev-cpu-agentbridge.mjs"`.

## 0.3.1

- Change: Docker images now bake in the engine selection (`JEV_ENGINE` is set via the Dockerfile's
  `ENGINE` build arg / `ENV`). Pulling `:laya`, `:semif`, or `:rizzoflow` no longer requires
  `-e JEV_ENGINE=...` — the tag alone determines the runtime engine. Override at runtime with
  `-e JEV_ENGINE=...` if needed.
- Add: `:rizzoflow` image variant — a general JEV integration point that talks to any
  RizzoFlow-compatible server you run yourself (set `JEV_RIZZOFLOW_URL`).
- Change: release and CI workflows now build all three engine variants (`semif`, `laya`,
  `rizzoflow`) instead of `["", "laya"]`; only `laya` still carries extra Python deps
  (`ENGINE_EXTRA=laya`).
- Docs: rewrote README's "What is this" and Pluggable engines section to match the new tag
  convention; updated `docs/architecture.md`, `docs/integration.md`, `docs/api.md`, and
  `docker-compose.yml`.

## 0.3.0

- Add: `RizzoFlowEngine` (`JEV_ENGINE=rizzoflow`) — a thin, stdlib-only HTTP client to a separately-run
  [RizzoFlow](https://github.com/Rizzo-AI-Academy/rizzo-flow) server (llama.cpp + Spark-X2.5 GGUF).
  Verified end-to-end on CPU against a real `rizzo serve` instance, both directly and through this
  Bridge's own `/v1/decide` and `/v1/decide/batch`.
- Add: Dockerfile `ENGINE_EXTRA` build arg; the release pipeline now publishes a `:laya` image
  variant (dependencies baked in) alongside the default `:latest` (semif only, unchanged) — no
  `pip install`/build needed to switch engines, just pull the matching tag
- Fix: README/Quick start built from source (`docker compose up --build`) instead of pulling the
  published image; switched to `docker run ghcr.io/giskardb/jev-agentbridge:latest` as the primary
  path, build-from-source kept as a documented alternative
- Fix: `docker-compose.yml` (root) had the same too-short `HEALTHCHECK start_period` as the
  Dockerfile fix in 0.2.1, missed at the time; also now pulls the published image by default

## 0.2.1

- Fix: the OpenCode plugin's `jev_decide` tool was never actually registered — it exported
  `{'tool.jev_decide': {...}}` instead of the real API's `{tool: {jev_decide: {...}}}`, so OpenCode's
  loader silently ignored it (no error). Found by running the real `opencode` CLI against the plugin
  instead of trusting the code; the "tested" claim in earlier docs was inaccurate.
- Fix: the plugin's `state` argument used a `z.union([..., z.record(z.any()), ...])` schema, which
  crashes OpenCode 1.18.x's internal tool-schema serializer (`ToolRegistry.state`) with
  `TypeError: undefined is not an object (evaluating 'r._zod')`; `state` is now `z.any()`.
- Add: `integrations/opencode/package.json` — the plugin now has a real, declared dependency
  (`@opencode-ai/plugin`) instead of silently assuming it's available; `npm install` is a required setup step
- Add: `integrations/opencode/test_plugin.mjs` (`npm test`) — structural smoke test that would have
  caught the registration-shape bug without needing a live OpenCode session; wired into CI
- Fix: Dockerfile/compose `HEALTHCHECK --start-period` was too short (5-30s) for a cold model load
  (~35-40s observed), causing a false "unhealthy" status right after `docker compose up`

## 0.2.0

- Add: pluggable decision engines selected via `JEV_ENGINE` (`semif` default, `laya` optional) — the
  `/v1/decide` API and SDKs are unaffected by the choice; new backends register in `engine/registry.py`
- Add: `LayaEngine`, an optional adapter for the [Laya](https://github.com/NandhaKishorM/laya) encoder
  models (`pip install jev-cpu-agentbridge[laya]`)
- Add: `python -m benchmarks.run --engine <semif|laya>` now runs a real CPU benchmark instead of a stub
- Fix: `/ready` and `/v1/info` reported the SemIf model name/engine regardless of the active engine

## 0.1.1

- Fix: server crashed on startup (`device_map` required the undeclared `accelerate` dependency)
- Fix: `torch` pulled the full NVIDIA/CUDA toolkit despite CPU-only inference; now resolved from the CPU-only PyTorch index
- Fix: Docker image never installed from the committed lockfile (`uv.lock` wasn't copied, sync silently swallowed failures)
- Fix: `.dockerignore` excluded files the image build actually needs (`pyproject.toml`, `benchmarks/`, `sdk/`)
- Fix: `examples/opencode-docker/` had a broken build context, wrong script path, and a port conflict
- Fix: SDK import example in README/docs referenced the wrong module (`jev_cpu_agentbridge` → `jev_agent_bridge`)
- Docs: rewritten README with sequence diagram, quick start, SDK usage, and integration guides for OpenCode and other agent frameworks
- CI: added `.github/workflows/ci.yml` (lint + tests) and `.github/workflows/release.yml` (tagged Docker releases)

## 0.1.0

- Initial release
- SemIf/JEV CPU decision engine
- FastAPI REST API: /v1/decide, /v1/decide/batch, /health, /ready, /v1/info
- Token slot validation (A-P)
- Direct and shared batch mode
- Python SDK
- TypeScript SDK
- OpenCode integration
- Tests and benchmarks
