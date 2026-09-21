"""Python SDK for JEV-CPU-AgentBridge."""

from __future__ import annotations

from typing import Any

import httpx


class AgentBridgeClient:
    """Minimal Python SDK client for JEV-CPU-AgentBridge."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=30.0)

    def decide(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Evaluate a single decision.

        Args:
            state: The evidence/state to apply the criterion to.
            question: The decision criterion.
            options: List of option dicts with ``id`` and ``description`` keys.

        Returns:
            A dict with ``decision``, ``probabilities``, ``selected_probability``,
            ``accepted``, and ``metadata`` keys.
        """
        resp = self._client.post(
            f"{self._base_url}/v1/decide",
            json={
                "state": state,
                "question": question,
                "options": options,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def decide_batch(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        decisions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Evaluate multiple decisions sharing one state.

        Args:
            state: The shared evidence/state.
            decisions: List of dicts with ``question`` and ``options`` keys.

        Returns:
            List of decision results.
        """
        resp = self._client.post(
            f"{self._base_url}/v1/decide/batch",
            json={
                "state": state,
                "decisions": decisions,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict[str, Any]:
        """Check service health."""
        resp = self._client.get(f"{self._base_url}/health")
        resp.raise_for_status()
        return resp.json()

    def ready(self) -> dict[str, Any]:
        """Check if model is ready."""
        resp = self._client.get(f"{self._base_url}/ready")
        if resp.status_code == 200:
            return resp.json()
        return {"status": "not ready"}

    def info(self) -> dict[str, Any]:
        """Get engine information."""
        resp = self._client.get(f"{self._base_url}/v1/info")
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()