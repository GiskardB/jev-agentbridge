"""Laya adapter: non-autoregressive scoring on Laya encoder models.

Laya scores all options for a question in one forward pass over an encoder model.
See https://github.com/NandhaKishorM/laya. Requires `pip install jev-agentbridge[laya]`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Sequence

from ...core.models import Decision, Scores, State
from ...core.ports import EngineInfo


@dataclass(frozen=True)
class LayaConfig:
    model_name: str = "convaiinnovations/laya"
    subfolder: str | None = None
    device: str = "cpu"

    @classmethod
    def from_env(cls) -> "LayaConfig":
        return cls(
            model_name=os.getenv("JEV_LAYA_MODEL_NAME", cls.model_name),
            subfolder=os.getenv("JEV_LAYA_SUBFOLDER") or None,
            device=os.getenv("JEV_MODEL_DEVICE", cls.device),
        )


def _question(decision: Decision) -> dict[str, Any]:
    return {
        "type": "choice",
        "instructions": decision.question,
        "criteria": {option.id: option.description for option in decision.options},
    }


def _scores(answer: dict[str, Any]) -> Scores:
    return Scores(
        probabilities={key: float(value) for key, value in answer["probabilities"].items()},
        details={"choice": answer.get("choice"), "confidence": answer.get("confidence")},
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
            revision=self._subfolder or "main",
            native_batch=True,
            thread_safe=False,
        )

    def is_ready(self) -> bool:
        return True

    def score(self, *, state: State, decision: Decision) -> Scores:
        result = self._agent.predict(state, {"decision": _question(decision)})
        return _scores(result["answers"]["decision"])

    def score_batch(self, *, state: State, decisions: Sequence[Decision]) -> list[Scores]:
        questions = {str(index): _question(decision) for index, decision in enumerate(decisions)}
        result = self._agent.predict(state, questions)
        return [_scores(result["answers"][str(index)]) for index in range(len(decisions))]
