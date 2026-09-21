---
name: jev-cpu-agentbridge
description: Use this skill when the agent needs to make a small, discrete decision from a fixed set of options, for example retry/abort/escalate, accept/reject, or choose among a few strategies.
version: 0.1.0
---

# JEV-CPU-AgentBridge — When to Use

JEV-CPU-AgentBridge evaluates small, discrete decisions using a local CPU model and returns a structured result. Use it when the task is a **small discrete choice** from a known set of options.

## Use JEV when the task is a small discrete choice, for example:

- Should I retry or abort?
- Which strategy should I use?
- Should this operation continue?
- Which of these 3 actions should I select?
- Should this change be accepted, rejected, or escalated?

## Do NOT use JEV for:

- Long-form reasoning
- Code generation
- Large explanations
- Creative writing
- Summarization
- Open-ended research
- Complex multi-step planning
- Tasks requiring generation

## Important

**JEV does not replace the agent's main LLM.**
**JEV only provides a local structured decision.**

The Bridge returns a result with an `accepted` field:

- `accepted = true` means the selected option met the configured probability threshold.
- `accepted = false` means the selected option did not meet the threshold.
- The Bridge **never** decides what the agent should do next when the result is uncertain.

**If `accepted == false`**, the agent must decide what to do next using its normal reasoning and orchestration.
