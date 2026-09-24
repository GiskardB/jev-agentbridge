"""MCP layer: the same decisions as the REST API, as Model Context Protocol tools.

Served by the bridge itself at `/mcp` (streamable HTTP), next to the REST routes, and backed by
the same `DecisionService`, so every engine is reachable from any MCP-capable agent harness
(Claude Code, Codex CLI, Cursor, VS Code, Gemini CLI, OpenCode...). No per-harness plugin.
"""

from __future__ import annotations

from typing import Any, Callable

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from .. import API_VERSION, __version__
from ..core.errors import DecisionError, EngineNotReadyError
from ..core.models import MAX_OPTIONS, MIN_OPTIONS, Decision, DecisionResult, Option
from ..core.service import DecisionService

INSTRUCTIONS = """\
JEV-AgentBridge picks one option out of a small, closed set (2-16) with a local JEV decision
model, and says how confident it is. It selects; it does not investigate, reason or write.

Call jev_decide only when all of these hold:
1. There is an actual choice, not a request for an answer, an explanation or an artifact.
2. The candidate options are already known and fixed.
3. You already have the context needed to evaluate them; pass it compactly as `state`.
4. The expected output is "one of these options".

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
    question: str = Field(description="The decision criterion")
    options: list[McpOption] = Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    min_selected_probability: float | None = Field(default=None, ge=0.0, le=1.0)


def _decision(question: str, options: list[McpOption], threshold: float | None) -> Decision:
    return Decision(
        question=question,
        options=tuple(Option(id=o.id, description=o.description) for o in options),
        min_selected_probability=threshold,
    )


def _result(result: DecisionResult) -> dict[str, Any]:
    return {
        "decision": {"id": result.decision.id, "description": result.decision.description},
        "probabilities": result.probabilities,
        "selected_probability": result.selected_probability,
        "accepted": result.accepted,
        "threshold": result.threshold,
        "metadata": result.metadata,
    }


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

    @mcp.tool(
        title="Pick one option with a JEV model",
        description=(
            "Choose one of 2-16 known options for a closed decision (retry/abort, which team, "
            "which model tier...) using a local JEV decision model. Returns the chosen option, "
            "a probability per option and `accepted` (confident enough to act on)."
        ),
        annotations=_READ_ONLY,
    )
    async def jev_decide(
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[McpOption],
        min_selected_probability: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate one decision."""

        decision = _decision(question, options, min_selected_probability)
        return await run(lambda: _result(service().decide(state=state, decision=decision)))

    @mcp.tool(
        title="Several JEV decisions on one state",
        description=(
            "Evaluate several closed decisions about the same state in one call (cheaper than "
            "calling jev_decide repeatedly). Returns one result per decision, in order."
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
                d.question,
                d.options,
                d.min_selected_probability
                if d.min_selected_probability is not None
                else min_selected_probability,
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
            "engine": {"name": engine.name, "model": engine.model, "revision": engine.revision},
            "default_min_selected_probability": current.default_threshold,
            "min_options": MIN_OPTIONS,
            "max_options": MAX_OPTIONS,
        }

    return mcp
