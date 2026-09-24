"""RizzoFlow adapter: thin HTTP client to a separately-run RizzoFlow server.

RizzoFlow (https://github.com/Rizzo-AI-Academy/rizzo-flow) runs its own llama.cpp-backed
server (`rizzo serve`); this adapter calls its native `POST /v1/decisions`. No extra Python
dependency (stdlib urllib only) — the model runs in RizzoFlow's own process.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Sequence

from ...core.errors import EngineUnavailableError
from ...core.models import Decision, Scores, State
from ...core.ports import EngineInfo


@dataclass(frozen=True)
class RizzoFlowConfig:
    base_url: str = "http://localhost:8017"
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "RizzoFlowConfig":
        return cls(
            base_url=os.getenv("JEV_RIZZOFLOW_URL", cls.base_url),
            timeout_seconds=float(
                os.getenv("JEV_RIZZOFLOW_TIMEOUT_SECONDS", str(cls.timeout_seconds))
            ),
        )


def _question(decision: Decision) -> dict[str, Any]:
    return {
        "type": "choice",
        "instructions": decision.question,
        # Without this, RizzoFlow's default policy lets the model abstain ("cannot
        # determine"); the service's `accepted` flag already carries the confidence signal.
        "policy": {"allow_abstain": False},
        "options": [{"id": o.id, "description": o.description} for o in decision.options],
    }


def _scores(answer: dict[str, Any]) -> Scores:
    # Keys starting with "__" are RizzoFlow-internal (e.g. an abstain bucket).
    probabilities = {
        key: float(value)
        for key, value in answer["probabilities"].items()
        if not key.startswith("__")
    }
    return Scores(probabilities=probabilities, details={"status": answer.get("status")})


class RizzoFlowAdapter:
    """DecisionAdapter backed by a running RizzoFlow server."""

    def __init__(self, *, base_url: str, timeout_seconds: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @classmethod
    def from_config(cls, config: RizzoFlowConfig) -> "RizzoFlowAdapter":
        return cls(base_url=config.base_url, timeout_seconds=config.timeout_seconds)

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="rizzoflow",
            model=self._base_url,
            native_batch=True,
            thread_safe=True,  # stateless HTTP client
        )

    def is_ready(self) -> bool:
        # The remote server is checked lazily: an unreachable server surfaces as
        # ENGINE_UNAVAILABLE (503) on the request instead of failing startup.
        return True

    def _post(self, state: State, questions: dict[str, Any], mode: str) -> dict[str, Any]:
        body = json.dumps({"state": state, "questions": questions, "mode": mode}).encode()
        request = urllib.request.Request(
            f"{self._base_url}/v1/decisions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read())
        except urllib.error.URLError as error:
            raise EngineUnavailableError(
                f"RizzoFlow server at {self._base_url} unreachable: {error}"
            ) from error

    def score(self, *, state: State, decision: Decision) -> Scores:
        result = self._post(state, {"decision": _question(decision)}, mode="direct")
        return _scores(result["answers"]["decision"])

    def score_batch(self, *, state: State, decisions: Sequence[Decision]) -> list[Scores]:
        questions = {str(index): _question(decision) for index, decision in enumerate(decisions)}
        result = self._post(state, questions, mode="shared")
        return [_scores(result["answers"][str(index)]) for index in range(len(decisions))]
