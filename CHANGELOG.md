# Changelog

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
