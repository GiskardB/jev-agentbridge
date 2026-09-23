# Architecture

```mermaid
flowchart TB
    Agent["<b>AI Agent</b><br/>reasoning · orchestration · planning<br/>tool execution · generative LLM · fallback decisions"]
    Bridge["<b>JEV-CPU-AgentBridge</b><br/>structured decision evaluation · probability calculation · threshold policy<br/><i>NO external LLM · NO orchestration · NO fallback</i>"]
    Registry["Engine registry<br/><code>JEV_ENGINE</code>"]
    SemIf["<b>SemIfEngine</b><br/>Qwen3-0.6B (CPU)<br/>next-token-logit scoring<br/>in-process"]
    Laya["<b>LayaEngine</b><br/>Laya encoders (CPU)<br/>non-autoregressive scoring<br/>in-process"]
    Rizzo["<b>RizzoFlowEngine</b><br/>HTTP client only<br/>calls a separate RizzoFlow server"]

    Agent -- "structured decision request" --> Bridge
    Bridge --> Registry
    Registry -- "JEV_ENGINE=semif (default)" --> SemIf
    Registry -- "JEV_ENGINE=laya (optional)" --> Laya
    Registry -- "JEV_ENGINE=rizzoflow (optional)" --> Rizzo
    Rizzo -. "POST /v1/decisions" .-> RizzoServer["RizzoFlow server<br/>llama.cpp + Spark-X2.5 GGUF<br/>run separately: rizzo serve"]
```

## Sequence diagram

```mermaid
sequenceDiagram
    participant Agent as AI Agent
    participant Bridge as JEV-CPU-AgentBridge (FastAPI)
    participant Engine as DecisionEngine (semif or laya)
    participant Model as Model (CPU)

    Agent->>Bridge: POST /v1/decide<br/>{state, question, options[2..16]}
    Bridge->>Engine: decide(state, question, options)
    Engine->>Engine: build engine-specific prompt/question<br/>(SemIf letters A..P, or Laya criteria dict)
    Engine->>Model: single forward pass — no generate(), no sampling
    Model-->>Engine: logits
    Engine->>Engine: probability distribution over options only
    Engine-->>Bridge: DecisionResult(decision, probabilities, accepted)
    Bridge-->>Agent: 200 OK { decision, probabilities, selected_probability, accepted }

    Note over Agent,Model: decide_batch() scores several decisions against one shared state<br/>in fewer forward passes than calling decide() N times
```

## Separation of concerns

The Bridge answers: *"Given this state, criterion and these possible actions, which option receives the highest score from the local decision model?"*

It does NOT answer: *"What should the entire agent do?"*

## Components

- **API layer**: FastAPI routes for `/v1/decide`, `/v1/decide/batch`, `/health`, `/ready`, `/v1/info`
- **Engine registry** (`engine/registry.py`): picks a `DecisionEngine` implementation from `JEV_ENGINE`
- **Decision engines**: pluggable implementations of the `DecisionEngine` protocol
  - `SemIfEngine` (default, `JEV_ENGINE=semif`): next-token-logit scoring on a causal LM (Qwen3-0.6B), in-process
  - `LayaEngine` (`JEV_ENGINE=laya`, optional): non-autoregressive scoring via the [Laya](https://github.com/NandhaKishorM/laya) encoder models, in-process
  - `RizzoFlowEngine` (`JEV_ENGINE=rizzoflow`, optional): thin HTTP client (stdlib only, no extra
    dependency) to a separately-run [RizzoFlow](https://github.com/Rizzo-AI-Academy/rizzo-flow)
    server (`rizzo serve`), which does llama.cpp + Spark-X2.5 GGUF scoring on its own
- **Prompt builder**: Constructs SemIf-style prompts (used by `SemIfEngine` only)
- **Tokenizer slots**: Validates A-P token mapping (used by `SemIfEngine` only)
- **Model loader**: Loads Qwen3-0.6B with CPU inference (used by `SemIfEngine` only)

## Swapping engines

The API contract (`/v1/decide`, `/v1/decide/batch`, response shape) never changes when you switch
engines — only `engine/registry.py` needs a new entry:

```bash
JEV_ENGINE=semif      # default: Qwen3-0.6B causal LM, next-token scoring
JEV_ENGINE=laya       # optional: Laya encoder models — pull the :laya image, or
                       # pip install jev-cpu-agentbridge[laya] from source
JEV_ENGINE=rizzoflow  # optional: HTTP client to a RizzoFlow server you run separately;
                       # set JEV_RIZZOFLOW_URL (default http://localhost:8017)
```

Adding a fourth backend means writing a `DecisionEngine` implementation and registering it in
`_ENGINES` in `engine/registry.py` — nothing in `api/` or the SDKs changes. If it needs its own
Python dependencies (like Laya), add a matching extra in `pyproject.toml` and a matrix entry in
`.github/workflows/release.yml` so it gets its own image tag; if it's just an HTTP client (like
RizzoFlow), it doesn't need either.
