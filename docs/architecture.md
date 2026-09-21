# Architecture

```
┌───────────────────────────────────────────────────┐
│                    AI AGENT                       │
│                                                   │
│  reasoning                                        │
│  orchestration                                    │
│  planning                                         │
│  tool execution                                   │
│  generative LLM                                   │
│  fallback decisions                                │
│                                                   │
└──────────────────────┬────────────────────────────┘
                       │
                       │ structured decision request
                       ▼
┌───────────────────────────────────────────────────┐
│             JEV-CPU-AgentBridge                   │
│                                                   │
│  structured decision evaluation                   │
│  local CPU inference                              │
│  option scoring                                   │
│  probability calculation                          │
│  threshold policy                                 │
│                                                   │
│  NO external LLM                                  │
│  NO orchestration                                 │
│  NO fallback                                      │
│                                                   │
└──────────────────────┬────────────────────────────┘
                       │
                       ▼
                 Qwen3-0.6B
                    CPU
```

## Separation of concerns

The Bridge answers: *"Given this state, criterion and these possible actions, which option receives the highest score from the local decision model?"*

It does NOT answer: *"What should the entire agent do?"*

## Components

- **API layer**: FastAPI routes for `/v1/decide`, `/v1/decide/batch`, `/health`, `/ready`, `/v1/info`
- **Decision engine**: `SemIfEngine` implements `DecisionEngine` protocol
- **Prompt builder**: Constructs SemIf-style prompts
- **Tokenizer slots**: Validates A-P token mapping
- **Model loader**: Loads Qwen3-0.6B with CPU inference
