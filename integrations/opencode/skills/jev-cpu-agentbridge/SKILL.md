---
name: jev-cpu-agentbridge
description: Use when the agent has already reduced a problem to a small, closed set of known options (2-16) and just needs to pick one - e.g. retry vs abort, accept vs reject vs escalate, strategy A vs B vs C. JEV runs a fast local CPU model to select among options that are already defined; it does not investigate causes, generate the option set, write or plan content, or handle open-ended/high-stakes decisions. Do not call it just because a question can be phrased as yes/no - only call it once the option set is fixed and the relevant context is already gathered.
metadata:
  purpose: discrete-decision-routing
  version: "0.2.0"
---

# JEV-CPU-AgentBridge

## What this is

JEV is a **local, CPU-only selection primitive**, not a reasoning engine. It scores a small
closed set of options in a single forward pass (no `generate()`) and returns the winner plus a
confidence signal. It is fast and free, but it can only choose between alternatives you already
know - it cannot discover what those alternatives should be.

The main agent stays responsible for everything around the selection: understanding the request,
gathering context, investigating causes, defining the candidate options, executing the result,
and handling uncertainty. JEV only performs the **select one of N** step.

## The gate

Call `jev_decide` only when all of these are true:

1. There is an actual choice, not a request for an answer, an explanation, or an artifact.
2. The candidate outcomes are already known and fixed (you are not still inventing them).
3. The set is small - 2 to 16 options, ideally under 6.
4. You already have the context needed to evaluate the options (state, constraints, facts).
5. The expected output is "one of these options", not generated text.

If any of these is false, do the missing work first (investigate, gather context, or generate
the option set) with your own reasoning, then call JEV once the decision is actually a small
closed choice.

## Shape of a good call

```json
{
  "state": "Deployment failed because the readiness probe timed out after service startup.",
  "question": "What should happen next?",
  "options": [
    { "id": "retry", "description": "Retry the deployment" },
    { "id": "rollback", "description": "Roll back to the previous version" },
    { "id": "escalate", "description": "Escalate to the platform team" }
  ]
}
```

`state` should be the compact decision-relevant evidence, not the whole conversation. `options`
should be mutually distinct and at the same level of abstraction - don't mix `"retry"` with
`"investigate Kubernetes"` in the same list.

A vague call like `{"state": "Something went wrong", "question": "What should we do?",
"options": ["something", "something_else"]}` is not a real decision - it just wraps "I don't
know" in JEV's shape. Do the reasoning first.

## When NOT to use JEV

- **Investigation / reasoning**: "why did this fail", "what's the root cause", "analyze this
  architecture" - these require understanding, not selection.
- **Generation / planning**: writing code, scripts, docs, migration plans - JEV can select which
  already-drafted strategy to run, but it never produces the artifact itself.
- **Options not yet fixed**: if the legitimate alternatives aren't established yet ("should we
  retry?" when rollback/escalate/wait might also be valid), figure out the real option set first.
- **Cosmetic yes/no**: a question phrased as binary ("should we migrate the database?") is not
  automatically a JEV decision if answering it actually requires cost/risk/dependency analysis.
  Surface form is not the test - condition 4 above (context already gathered) is.
- **Deterministic logic**: `if status == 404` or `if retries >= 3` is a plain rule, not a
  semantic judgment call - don't spend a model call on it.

## Reading the result

The response has a `decision` (the selected option) and an `accepted` boolean:

- `accepted: true` - the selection cleared the configured confidence threshold; use it.
- `accepted: false` - the selection did **not** clear the threshold. This does not mean "pick a
  different option" and does not mean "the answer is no". It means JEV is not confident enough,
  and the agent must decide what happens next using its own reasoning (gather more context, ask
  a human, apply a fallback policy, etc.). JEV never resolves its own uncertainty for you.

Don't loop on `accepted: false` by calling JEV again with the same input expecting a different
answer - re-invoke only if the state or option set has materially changed.

## Safety boundary

A small option set doesn't imply a low-stakes decision. For destructive, irreversible, financial,
or security-sensitive actions, treat JEV's output as one input to your existing approval/policy
logic, not as sole authorization to act.
