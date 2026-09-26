"""MCP layer: the same decisions as the REST API, as Model Context Protocol tools.

Served by the bridge itself at `/mcp` (streamable HTTP), next to the REST routes, and backed by
the same `DecisionService`, so every engine is reachable from any MCP-capable agent harness
(Claude Code, Codex CLI, Cursor, VS Code, Gemini CLI, OpenCode...). No per-harness plugin.
"""

from __future__ import annotations

from typing import Any, Callable, Literal

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, model_validator

from .. import API_VERSION, __version__
from ..core.errors import DecisionError, EngineNotReadyError
from ..core.models import (
    MAX_OPTIONS,
    MIN_OPTIONS,
    QUESTION_TYPES,
    Decision,
    DecisionResult,
    Option,
    QuestionType,
)
from ..core.service import DecisionService

INSTRUCTIONS = """\
JEV-AgentBridge answers closed questions with a local JEV decision model and says how confident
it is. It judges; it does not investigate, reason or write. Pick the tool by question type:
- jev_yes_no: a yes/no question ("is this request within policy?").
- jev_choose: one category out of 2-16 known options ("which team handles this?").
- jev_score: a position on an ordinal scale, levels lowest first ("how urgent is it?").
Use the tool that matches the question: jev_yes_no answers yes/no directly, jev_score keeps the
order of the scale. Several questions on the same state: jev_decide_batch.

Call these tools only when all of these hold:
1. There is an actual decision, not a request for an answer, an explanation or an artifact.
2. The possible answers are already known and fixed.
3. You already have the context needed to judge; pass it compactly as `state`.
4. The expected output is "yes/no", "one of these options" or "a level on this scale".

Reading the result: use `decision` only when `accepted` is true. `accepted: false` means the
model is not confident enough. It does not mean "no". Decide with your own reasoning instead,
and do not call again with the same input. For destructive, irreversible, financial or
security-sensitive actions, treat the result as one input to your policy, never as sole
authorization.
"""

_READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)


class McpOption(BaseModel):
    id: str = Field(min_length=1, description="Stable identifier returned as the decision")
    description: str = Field(description="What choosing this option means")


class McpDecision(BaseModel):
    type: Literal["choice", "noul", "score"] = Field(
        default="choice", description="choice, noul (yes/no, no options) or score (levels)"
    )
    question: str = Field(description="The decision criterion")
    options: list[McpOption] | None = Field(
        default=None,
        min_length=MIN_OPTIONS,
        max_length=MAX_OPTIONS,
        description="choice: the options. score: the levels, lowest first. noul: omit.",
    )
    yes_description: str | None = Field(default=None, description="noul only")
    no_description: str | None = Field(default=None, description="noul only")
    score_tolerance: int | None = Field(default=None, ge=0, description="score only")
    min_selected_probability: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _fields_match_type(self) -> "McpDecision":
        if (self.type == "noul") != (self.options is None):
            raise ValueError("noul takes no options; choice and score need options")
        return self


def _decision(
    type_: QuestionType,
    question: str,
    options: list[McpOption] | None,
    threshold: float | None,
    *,
    yes_description: str | None = None,
    no_description: str | None = None,
    score_tolerance: int | None = None,
) -> Decision:
    if type_ == "noul":
        return Decision.noul(
            question,
            yes_description=yes_description,
            no_description=no_description,
            min_selected_probability=threshold,
        )
    return Decision(
        question=question,
        options=tuple(Option(id=o.id, description=o.description) for o in options or ()),
        min_selected_probability=threshold,
        type=type_,
        score_tolerance=score_tolerance,
    )


def _result(result: DecisionResult) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": result.type,
        "decision": {"id": result.decision.id, "description": result.decision.description},
        "probabilities": result.probabilities,
        "selected_probability": result.selected_probability,
        "accepted": result.accepted,
        "threshold": result.threshold,
    }
    if result.score is not None:
        out["score"] = result.score
    if result.noul is not None:
        out["noul"] = result.noul
    if result.score_window_probability is not None:
        out["score_window_probability"] = result.score_window_probability
        out["score_tolerance"] = result.score_tolerance
    out["metadata"] = result.metadata
    return out


def create_mcp_server(get_service: Callable[[], DecisionService | None]) -> MCPServer:
    mcp = MCPServer(
        name="jev-agentbridge",
        title="JEV-AgentBridge",
        version=__version__,
        instructions=INSTRUCTIONS,
        website_url="https://github.com/GiskardB/jev-agentbridge",
    )

    def service() -> DecisionService:
        current = get_service()
        if current is None or not current.is_ready():
            raise EngineNotReadyError("The decision engine is not ready yet")
        return current

    async def run(fn: Callable[[], Any]) -> Any:
        try:
            return await anyio.to_thread.run_sync(fn)  # engines are blocking CPU/HTTP calls
        except DecisionError as error:
            # ToolError text reaches the agent; other exceptions are masked by the SDK.
            raise ToolError(f"{error.code}: {error.message}") from error

    async def decide(state: Any, decision: Decision) -> dict[str, Any]:
        return await run(lambda: _result(service().decide(state=state, decision=decision)))

    @mcp.tool(
        title="Yes/no question with a JEV model",
        description=(
            "Answer a yes/no question about the state (is it within policy? is the customer "
            "asking for a refund? ...) with a local JEV decision model. Returns `decision.id` "
            "`yes` or `no`, `noul` (probability of yes) and `accepted` (confident enough)."
        ),
        annotations=_READ_ONLY,
    )
    async def jev_yes_no(
        state: str | dict[str, Any] | list[Any],
        question: str,
        yes_description: str | None = None,
        no_description: str | None = None,
        min_selected_probability: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate one yes/no (noul) decision."""

        decision = _decision(
            "noul",
            question,
            None,
            min_selected_probability,
            yes_description=yes_description,
            no_description=no_description,
        )
        return await decide(state, decision)

    @mcp.tool(
        title="Pick one option with a JEV model",
        description=(
            "Choose one of 2-16 known options (retry/abort, which team, which model tier...) "
            "with a local JEV decision model. Returns the chosen option, a probability per "
            "option and `accepted` (confident enough to act on). For yes/no use jev_yes_no."
        ),
        annotations=_READ_ONLY,
    )
    async def jev_choose(
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[McpOption],
        min_selected_probability: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate one choice decision."""

        return await decide(
            state, _decision("choice", question, options, min_selected_probability)
        )

    @mcp.tool(
        title="Rate on an ordinal scale with a JEV model",
        description=(
            "Place the state on an ordinal scale (urgency, severity, sentiment...) given 2-16 "
            "levels, lowest first, with a local JEV decision model. Returns the most likely "
            "level as `decision`, `score` (expected level, 0 = first level) and `accepted` "
            "(the chosen level ± score_tolerance levels, default 1, is likely enough)."
        ),
        annotations=_READ_ONLY,
    )
    async def jev_score(
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[McpOption],
        min_selected_probability: float | None = None,
        score_tolerance: int | None = None,
    ) -> dict[str, Any]:
        """Evaluate one score decision."""

        decision = _decision(
            "score", question, levels, min_selected_probability, score_tolerance=score_tolerance
        )
        return await decide(state, decision)

    @mcp.tool(
        title="Several JEV decisions on one state",
        description=(
            "Evaluate several closed decisions about the same state in one call, cheaper than "
            "separate calls. Each decision has a `type` (choice, noul, score) and types can be "
            "mixed. Returns one result per decision, in order."
        ),
        annotations=_READ_ONLY,
    )
    async def jev_decide_batch(
        state: str | dict[str, Any] | list[Any],
        decisions: list[McpDecision],
        min_selected_probability: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate several decisions sharing one state."""

        batch = [
            _decision(
                d.type,
                d.question,
                d.options,
                d.min_selected_probability
                if d.min_selected_probability is not None
                else min_selected_probability,
                yes_description=d.yes_description,
                no_description=d.no_description,
                score_tolerance=d.score_tolerance,
            )
            for d in decisions
        ]
        return await run(
            lambda: {
                "decisions": [
                    _result(r) for r in service().decide_batch(state=state, decisions=batch)
                ]
            }
        )

    @mcp.tool(
        title="Bridge and engine info",
        description="Which JEV engine and model answer, the API version and the default threshold.",
        annotations=_READ_ONLY,
    )
    async def jev_info() -> dict[str, Any]:
        """Describe the active engine."""

        current = service()
        engine = current.info()
        return {
            "api_version": API_VERSION,
            "version": __version__,
            "engine": {
                "name": engine.name,
                "model": engine.model,
                "revision": engine.revision,
                "native_types": [t for t in QUESTION_TYPES if t in current.native_types()],
            },
            "supported_types": list(QUESTION_TYPES),
            "default_score_tolerance": current.default_score_tolerance,
            "default_min_selected_probability": current.default_threshold,
            "min_options": MIN_OPTIONS,
            "max_options": MAX_OPTIONS,
        }

    return mcp
