"""System One adapter: HTTP client for the TypeSafe System One protocol (`POST /v1/systemone`).

System One is the API of TypeSafe's hosted Jev model, and open implementations reuse it:
Kev (https://github.com/jaredpalmer/kev, `python -m kev.serve`) and RizzoFlow both serve it. So
one protocol adapter covers every System One-compatible server; `kev` and `systemone` in the
registry are two presets of this same class. No extra Python dependency (stdlib urllib only):
the model runs in the server's own process, on whatever hardware that server has.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Sequence

from ...core.errors import EngineError, EngineUnavailableError
from ...core.models import NO_ID, YES_ID, Decision, Scores, State
from ...core.ports import EngineInfo


@dataclass(frozen=True)
class SystemOneConfig:
    engine_name: str = "systemone"
    base_url: str = "http://localhost:8009"
    model: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls, prefix: str, **defaults: Any) -> "SystemOneConfig":
        """Read `<prefix>_URL`, `_MODEL`, `_API_KEY`, `_TIMEOUT_SECONDS`, e.g. JEV_KEV_URL."""

        base = cls(**defaults)
        return cls(
            engine_name=base.engine_name,
            base_url=os.getenv(f"{prefix}_URL", base.base_url),
            model=os.getenv(f"{prefix}_MODEL", base.model or "") or None,
            api_key=os.getenv(f"{prefix}_API_KEY") or base.api_key,
            timeout_seconds=float(
                os.getenv(f"{prefix}_TIMEOUT_SECONDS", str(base.timeout_seconds))
            ),
        )


def _question(decision: Decision) -> dict[str, Any]:
    if decision.type == "noul":
        question: dict[str, Any] = {"type": "noul", "instructions": decision.question}
        custom = decision.custom_noul_descriptions()
        if custom:
            question["criteria"] = {"true": custom[YES_ID], "false": custom[NO_ID]}
        return question
    if decision.type == "score":
        return {
            "type": "score",
            "instructions": decision.question,
            "criteria": [option.description for option in decision.options],
        }
    return {
        "type": "choice",
        "instructions": decision.question,
        "criteria": {option.id: option.description for option in decision.options},
    }


def _scores(answer: dict[str, Any], decision: Decision) -> Scores:
    if answer.get("type") != decision.type:
        raise EngineError(f"System One server returned an unexpected answer: {answer!r}")
    try:
        if decision.type == "noul":
            yes = float(answer["noul"])
            return Scores(probabilities={YES_ID: yes, NO_ID: round(1.0 - yes, 6)})
        details = {"confidence": answer.get("confidence")}
        if decision.type == "score":
            # Levels come back keyed by position ("0", "1", ...), lowest first.
            probabilities = {
                option.id: float(answer["probabilities"][str(index)])
                for index, option in enumerate(decision.options)
            }
            return Scores(
                probabilities=probabilities, details={**details, "score": answer.get("score")}
            )
        ids = {option.id for option in decision.options}
        probabilities = {
            key: float(value) for key, value in answer["probabilities"].items() if key in ids
        }
    except (KeyError, TypeError, ValueError) as error:
        raise EngineError(f"System One server returned an unexpected answer: {answer!r}") from error
    return Scores(probabilities=probabilities, details={"choice": answer.get("choice"), **details})


class SystemOneAdapter:
    """DecisionAdapter backed by any server that speaks TypeSafe System One."""

    def __init__(self, config: SystemOneConfig) -> None:
        self._config = config
        self._base_url = config.base_url.rstrip("/")

    @classmethod
    def from_config(cls, config: SystemOneConfig) -> "SystemOneAdapter":
        return cls(config)

    def info(self) -> EngineInfo:
        return EngineInfo(
            name=self._config.engine_name,
            model=self._config.model or "server default",
            revision=self._base_url,
            native_batch=True,  # every question of a batch goes in one request
            thread_safe=True,  # stateless HTTP client
            native_types=frozenset({"choice", "noul", "score"}),
        )

    def is_ready(self) -> bool:
        # Checked lazily: an unreachable server surfaces as ENGINE_UNAVAILABLE (503) on the
        # request instead of failing the bridge's startup.
        return True

    def _post(self, state: State, questions: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {"state": state, "questions": questions}
        if self._config.model:
            body["model"] = self._config.model
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        request = urllib.request.Request(
            f"{self._base_url}/v1/systemone",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._config.timeout_seconds) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            raise EngineError(f"System One server returned {error.code}: {detail}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise EngineUnavailableError(
                f"System One server at {self._base_url} unreachable: {error}"
            ) from error

    def score(self, *, state: State, decision: Decision) -> Scores:
        result = self._post(state, {"decision": _question(decision)})
        return _scores(result["answers"]["decision"], decision)

    def score_batch(self, *, state: State, decisions: Sequence[Decision]) -> list[Scores]:
        questions = {f"q{index}": _question(decision) for index, decision in enumerate(decisions)}
        result = self._post(state, questions)
        return [
            _scores(result["answers"][f"q{index}"], decision)
            for index, decision in enumerate(decisions)
        ]
