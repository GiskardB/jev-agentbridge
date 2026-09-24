"""Laya adapter: non-autoregressive scoring on Laya encoder models.

Laya scores all options for a question in one forward pass over an encoder model.
See https://github.com/NandhaKishorM/laya. Requires `pip install jev-agentbridge[laya]`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Sequence

from ...core.models import NO_ID, YES_ID, Decision, Scores, State
from ...core.ports import EngineInfo

# Values of JEV_LAYA_SUBFOLDER that select Laya's English model (the repository root).
_ENGLISH = {"", "english", "en", "root", "none"}


@dataclass(frozen=True)
class LayaConfig:
    model_name: str = "convaiinnovations/laya"
    # Multilingual by default: the English model is near-uniform on non-English text.
    subfolder: str | None = "multilingual"
    device: str = "cpu"

    @classmethod
    def from_env(cls) -> "LayaConfig":
        subfolder = os.getenv("JEV_LAYA_SUBFOLDER", cls.subfolder or "").strip()
        return cls(
            model_name=os.getenv("JEV_LAYA_MODEL_NAME", cls.model_name),
            subfolder=None if subfolder.lower() in _ENGLISH else subfolder,
            device=os.getenv("JEV_MODEL_DEVICE", cls.device),
        )


def _question(decision: Decision) -> dict[str, Any]:
    if decision.type == "noul":
        # Laya's noul head takes no descriptions: "yes"/"no" are implied by the question.
        return {"type": "noul", "instructions": decision.question}
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
    details = {"confidence": answer.get("confidence")}
    if decision.type == "noul":
        yes = float(answer["noul"])
        return Scores(probabilities={YES_ID: yes, NO_ID: round(1.0 - yes, 6)}, details=details)
    if decision.type == "score":
        # Levels come back keyed by position ("0", "1", ...), lowest first.
        probabilities = {
            option.id: float(answer["probabilities"][str(index)])
            for index, option in enumerate(decision.options)
        }
        return Scores(
            probabilities=probabilities, details={**details, "score": answer.get("score")}
        )
    return Scores(
        probabilities={key: float(value) for key, value in answer["probabilities"].items()},
        details={"choice": answer.get("choice"), **details},
    )


class LayaAdapter:
    """DecisionAdapter backed by an in-process Laya agent."""

    def __init__(self, *, agent: Any, model_name: str, subfolder: str | None) -> None:
        self._agent = agent
        self._model_name = model_name
        self._subfolder = subfolder

    @classmethod
    def from_config(cls, config: LayaConfig) -> "LayaAdapter":
        try:
            import laya
        except ImportError as error:
            raise RuntimeError(
                "JEV_ENGINE=laya requires the 'laya' package. Install it with "
                "`pip install jev-agentbridge[laya]`."
            ) from error
        agent = laya.load(config.model_name, device=config.device, subfolder=config.subfolder)
        return cls(agent=agent, model_name=config.model_name, subfolder=config.subfolder)

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="laya",
            model=self._model_name,
            revision=self._subfolder or "english",
            native_batch=True,
            thread_safe=False,
            native_types=frozenset({"choice", "noul", "score"}),
        )

    def is_ready(self) -> bool:
        return True

    def score(self, *, state: State, decision: Decision) -> Scores:
        result = self._agent.predict(state, {"decision": _question(decision)})
        return _scores(result["answers"]["decision"], decision)

    def score_batch(self, *, state: State, decisions: Sequence[Decision]) -> list[Scores]:
        questions = {str(index): _question(decision) for index, decision in enumerate(decisions)}
        result = self._agent.predict(state, questions)
        return [
            _scores(result["answers"][str(index)], decision)
            for index, decision in enumerate(decisions)
        ]
