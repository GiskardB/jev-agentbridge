"""Python SDK for JEV-CPU-AgentBridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass(frozen=True)
class GateOutcome:
    """Result of decide_or_fallback().

    source is "jev" when the Bridge answered with accepted=true, "fallback" otherwise
    (low confidence, or the Bridge unreachable/erroring — see `error`).
    """

    decision_id: str
    source: str
    jev_result: dict[str, Any] | None
    error: str | None = None


class AgentBridgeClient:
    """Minimal Python SDK client for JEV-CPU-AgentBridge."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def decide(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[dict[str, str]],
        min_selected_probability: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate a single decision.

        Returns a dict with ``decision``, ``probabilities``, ``selected_probability``,
        ``accepted``, ``threshold`` and ``metadata``.
        """
        body: dict[str, Any] = {"state": state, "question": question, "options": options}
        if min_selected_probability is not None:
            body["min_selected_probability"] = min_selected_probability
        resp = self._client.post(f"{self._base_url}/v1/decide", json=body)
        resp.raise_for_status()
        return resp.json()

    def decide_or_fallback(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[dict[str, str]],
        fallback: Callable[[dict[str, Any]], str],
        min_selected_probability: float | None = None,
    ) -> GateOutcome:
        """Gate pattern: use JEV when it is confident, otherwise call ``fallback``.

        ``fallback`` receives the request dict ({state, question, options}) and must
        return one of the option ids — typically by asking your LLM. It is also used
        when the Bridge is down, so the gate never breaks the agent.
        """
        request = {"state": state, "question": question, "options": options}
        try:
            result = self.decide(**request, min_selected_probability=min_selected_probability)
        except httpx.HTTPError as error:
            return GateOutcome(fallback(request), "fallback", None, str(error))
        if result["accepted"]:
            return GateOutcome(result["decision"]["id"], "jev", result)
        return GateOutcome(fallback(request), "fallback", result)

    def decide_batch(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        decisions: list[dict[str, Any]],
        min_selected_probability: float | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate multiple decisions sharing one state.

        ``decisions`` items have ``question``, ``options`` and optionally
        ``min_selected_probability``. Returns one result per decision.
        """
        body: dict[str, Any] = {"state": state, "decisions": decisions}
        if min_selected_probability is not None:
            body["min_selected_probability"] = min_selected_probability
        resp = self._client.post(f"{self._base_url}/v1/decide/batch", json=body)
        resp.raise_for_status()
        return resp.json()["decisions"]

    def health(self) -> dict[str, Any]:
        """Check service health."""
        resp = self._client.get(f"{self._base_url}/health")
        resp.raise_for_status()
        return resp.json()

    def ready(self) -> dict[str, Any]:
        """Check if the engine is ready."""
        resp = self._client.get(f"{self._base_url}/ready")
        if resp.status_code == 200:
            return resp.json()
        return {"status": "not ready"}

    def info(self) -> dict[str, Any]:
        """Get service and engine information."""
        resp = self._client.get(f"{self._base_url}/v1/info")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
