# Changelog

## Unreleased

- Docs: README rewritten around what the project is. It is a standardization bridge toward JEV
  decision models: one versioned contract, SDKs and error model for agents, with each JEV engine
  plugged in as an adapter and measured the same way. A new table lists what the bridge
  normalizes across engines. A new "What it is not" section reports measured engine quality
  honestly, including the LLM baseline.
- Docs: `docs/performance.md` now has the full model-routing results from the external
  evaluation run. The LLM baseline (qwen3-32b) scored 96.2%, against 59.6% for the best JEV
  configuration.
- Add: `examples/eval/model_routing/`, a model-routing evaluation (small / medium / large LLM
  tier). It has 240 hand-labelled requests (120 IT, 120 EN, balanced), labelling rules, and
  `run_eval.py` (stdlib only). The runner evaluates any running Bridge, scores external
  predictions such as an LLM baseline, and writes a comparison `REPORT.md`. `INSTRUCTIONS.md`
  gives step-by-step commands another agent can execute with the published Docker images.
  First run: laya English 59.6% (EN 70.0%, IT 49.2%), 12.1% coverage at 95% accuracy; laya
  multilingual 34.6%.
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

## 0.4.0

Architecture: a standard REST contract with engine adapters behind it (ports & adapters).

- Change: **laya is now the default engine** (`JEV_ENGINE` default, Dockerfile `ENGINE`
  default, and the `:latest` image tag). On the 12-row samples it scored 83.3% (English) and
  75% (Italian), against 41.7% / 41.7% for semif with its default prompt. It was also faster
  (~350ms vs ~530ms p50). `laya` is now a core dependency; the `[laya]` extra is kept empty
  for compatibility. semif moves to the `:semif` tag. **Breaking for `:latest` users who
  relied on semif:** pull `:semif` or set `JEV_ENGINE=semif`.
- Fix: the laya adapter used Laya's `confidence` as `selected_probability`. That field is
  1 − normalized entropy, not the probability of the chosen option. For example, p=0.64 comes
  back as confidence 0.056, so against the 0.60 threshold laya almost never returned
  `accepted=true`. `selected_probability` is now the chosen option's probability, as for every
  engine. Laya's value is still reported as `metadata.engine_details.confidence`.
- Add: `JEV_SEMIF_PROMPT_VERSION` selects the semif prompt. `direct-options-v1` stays the
  default. `direct-options-v2` appends `"\n\nAnswer:"` and scored 75% / 66.7% on the samples
  (v1: 41.7%). The active version is reported in `metadata.engine_details.prompt_version`.
- Add: `examples/eval/sample_it.jsonl`, the Italian version of the sample dataset.
  `docs/performance.md` has the full engine × language table, including
  `JEV_LAYA_SUBFOLDER=multilingual` (75% / 75% at ~170ms).

- Change: code reorganized into `api/` (v1 contract, routes, error envelope), `core/` (domain
  models, `DecisionAdapter` port, `DecisionService`, domain errors) and `adapters/<engine>/`
  (semif, laya, rizzoflow, each with its own config read from its own env vars). Adapters only
  score; validation, argmax, the acceptance threshold, timing and the response shape now live
  once in `DecisionService`, so every engine behaves identically.
- Fix: semif returned `probabilities` keyed by letters (`{"A": .., "B": ..}`) while laya and
  rizzoflow used option ids. All engines now key by option id.
- Fix: per-request `min_selected_probability` was silently ignored (not in the request schema).
  It is now accepted on `/v1/decide`, on each batch item and at batch level. Precedence is
  item, then batch, then `JEV_MIN_SELECTED_PROBABILITY`. The applied value is returned as
  `threshold`.
- Fix: routes were `async` but ran the model synchronously, so one CPU decision blocked every
  other request, `/health` included. They now run in the thread pool. Adapters that are not
  thread-safe are serialized by the service.
- Change: one error envelope `{"error": {code, message, request_id}}` for every failure,
  including 422 validation and 503. New codes: `DUPLICATE_OPTION_ID` (400), `INPUT_TOO_LARGE`
  (413), `ENGINE_UNAVAILABLE` (503, e.g. RizzoFlow unreachable), `MODEL_NOT_READY` (503).
- Change: `/v1/info` now reports `api_version`, `engine{name, model, revision, native_batch}`,
  `available_engines` and `default_min_selected_probability`. `/ready` also reports `engine`.
  Response `metadata` has a stable core (`engine`, `model`, `model_revision`, `mode`,
  `latency_ms`, `input_tokens?`). Adapter-specific fields moved under `engine_details`.
- Add: `jev-eval` (`python -m jev_cpu_agentbridge.evaluation`) measures accuracy vs coverage per
  threshold on a labelled JSONL dataset against any running Bridge, and recommends a
  threshold. Sample format in `examples/eval/sample.jsonl`.
- Add: SDK gate helpers: Python `decide_or_fallback()` and TypeScript `decideOrFallback()`.
  They use JEV when `accepted`, otherwise call your fallback (e.g. an LLM), including when the
  Bridge is unreachable. Both SDKs accept `min_selected_probability`. The TypeScript SDK
  raises a typed `BridgeError` and has a request timeout.
- Change: Python SDK `decide_batch()` now returns the list of results, as its signature
  already said, instead of the `{"decisions": [...]}` wrapper.
- Docs: repositioned around the gate-in-the-orchestrator pattern. Architecture, API and
  integration guides rewritten. First accuracy measurement added to `docs/performance.md`:
  semif with the current prompt got 41.7% on the 12-row sample, and appending `Answer:` to the
  prompt got 9/12.
- Breaking (library imports only; the HTTP API stays backward compatible):
  `jev_cpu_agentbridge.engine.*` and `domain.models` are gone. Use `core.*` and `adapters.*`.
  `JEV_MODEL_DTYPE` and `JEV_PROMPT_VERSION` were never applied and have been removed.

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
