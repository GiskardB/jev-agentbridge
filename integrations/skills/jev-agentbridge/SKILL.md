---
name: jev-agentbridge
description: Use when the agent has already reduced a problem to a closed question with known answers and just needs the judgment - a yes/no check (is this within policy?), one category out of 2-16 (retry vs abort vs escalate, which team), or a level on an ordinal scale (how urgent, how severe). JEV runs a local decision model (through the jev-agentbridge MCP server) with tools jev_yes_no, jev_choose and jev_score; it does not investigate causes, generate the options, write or plan content, or handle open-ended/high-stakes decisions. Do not call it just because a question can be phrased as yes/no - only call it once the answers are fixed and the relevant context is already gathered.
metadata:
  purpose: discrete-decision-routing
  version: "0.4.0"
---

# JEV-AgentBridge

The tools come from the `jev-agentbridge` MCP server (see `docs/mcp.md` in the repository), one
per JEV question type:

| Question | Tool | Example |
|---|---|---|
| Yes or no? | `jev_yes_no` | "Is the return request within policy?" |
| Which one of these? | `jev_choose` | "Retry, roll back or escalate?" |
| Where on this scale? | `jev_score` | "How urgent: low, medium, high, critical?" |

Plus `jev_decide_batch` (several questions on the same state, types can be mixed) and `jev_info`
(which engine answers). Harnesses show them with a prefix, e.g. `mcp__jev__jev_yes_no` in
Claude Code.

Use the narrowest type. A yes/no question goes to `jev_yes_no`, not to `jev_choose` with
options "yes"/"no". A scale goes to `jev_score` with the levels lowest first, not to
`jev_choose`: the score keeps the order and tells you how far between two levels the answer is.

## What this is

JEV is a **local selection primitive**, not a reasoning engine. It scores a small
closed set of options in a single forward pass (no `generate()`) and returns the winner plus a
confidence signal. It runs locally at no API cost, but it can only choose between alternatives you already
know - it cannot discover what those alternatives should be.

The main agent stays responsible for everything around the selection: understanding the request,
gathering context, investigating causes, defining the candidate options, executing the result,
and handling uncertainty. JEV only performs the **select one of N** step.

## The gate

Call a JEV tool only when all of these are true:

1. There is an actual decision, not a request for an answer, an explanation, or an artifact.
2. The possible answers are already known and fixed (yes/no, the options, the levels of the
   scale), and you are not still inventing them.
3. For a choice or a scale, the set is small - 2 to 16 entries, ideally under 6.
4. You already have the context needed to judge (state, constraints, facts).
5. The expected output is "yes/no", "one of these options" or "a level", not generated text.

If any of these is false, do the missing work first (investigate, gather context, or generate
the option set) with your own reasoning, then call JEV once the decision is actually a small
closed choice.

## Shape of a good call

`jev_yes_no`:

```json
{
  "state": "Customer bought the shoes 10 days ago. Policy: returns within 30 days of purchase.",
  "question": "Is the return request within policy?"
}
```

`jev_score` (levels lowest first):

```json
{
  "state": "Our largest customer has a demo in 40 minutes and SSO login is broken.",
  "question": "How urgent is the request?",
  "levels": [
    { "id": "low", "description": "Can wait days" },
    { "id": "medium", "description": "Within the day" },
    { "id": "high", "description": "Within the hour" },
    { "id": "critical", "description": "Right now, damage ongoing" }
  ]
}
```

`jev_choose`:

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

The response has a `decision` (the selected option: `yes`/`no` for `jev_yes_no`, the level for
`jev_score`) and an `accepted` boolean. `jev_yes_no` also returns `noul`, the probability of
yes; `jev_score` returns `score`, the expected level (0 = first level; 2.4 on a 0-3 scale
means "between the third and fourth level, closer to the third").

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
