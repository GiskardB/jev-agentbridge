"""Python SDK for JEV-AgentBridge."""

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
    """Minimal Python SDK client for JEV-AgentBridge."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def decide(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[dict[str, str]] | None = None,
        type: str = "choice",
        yes_description: str | None = None,
        no_description: str | None = None,
        score_tolerance: int | None = None,
        min_selected_probability: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate a single decision of any type (``choice``, ``noul``, ``score``).

        Returns a dict with ``type``, ``decision``, ``probabilities``,
        ``selected_probability``, ``accepted``, ``threshold``, ``score`` (score only),
        ``noul`` (noul only), ``score_window_probability`` / ``score_tolerance`` (score only)
        and ``metadata``.
        """
        body: dict[str, Any] = {"type": type, "state": state, "question": question}
        optional = {
            "options": options,
            "yes_description": yes_description,
            "no_description": no_description,
            "score_tolerance": score_tolerance,
            "min_selected_probability": min_selected_probability,
        }
        body.update({key: value for key, value in optional.items() if value is not None})
        resp = self._client.post(f"{self._base_url}/v1/decide", json=body)
        resp.raise_for_status()
        return resp.json()

    def yes_no(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        yes_description: str | None = None,
        no_description: str | None = None,
        min_selected_probability: float | None = None,
    ) -> dict[str, Any]:
        """A noul (yes/no) decision: ``decision.id`` is ``yes`` or ``no``, ``noul`` is P(yes)."""
        return self.decide(
            state=state,
            question=question,
            type="noul",
            yes_description=yes_description,
            no_description=no_description,
            min_selected_probability=min_selected_probability,
        )

    def score(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[dict[str, str]],
        score_tolerance: int | None = None,
        min_selected_probability: float | None = None,
    ) -> dict[str, Any]:
        """A score decision over ``levels`` (lowest first): ``score`` is the expected level.

        ``accepted`` compares the probability of the chosen level ± ``score_tolerance`` levels
        (server default 1) with the threshold; pass 0 to require the exact level.
        """
        return self.decide(
            state=state,
            question=question,
            options=levels,
            type="score",
            score_tolerance=score_tolerance,
            min_selected_probability=min_selected_probability,
        )

    def decide_or_fallback(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        fallback: Callable[[dict[str, Any]], str],
        options: list[dict[str, str]] | None = None,
        type: str = "choice",
        min_selected_probability: float | None = None,
    ) -> GateOutcome:
        """Gate pattern: use JEV when it is confident, otherwise call ``fallback``.

        ``fallback`` receives the request dict ({state, question, options, type}) and must
        return one of the option ids (``yes``/``no`` for noul) — typically by asking your
        LLM. It is also used when the Bridge is down, so the gate never breaks the agent.
        """
        request = {"state": state, "question": question, "options": options, "type": type}
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

        ``decisions`` items have ``question``, optionally ``type`` (``choice`` default,
        ``noul``, ``score``; types can be mixed), ``options`` (not for noul) and
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
