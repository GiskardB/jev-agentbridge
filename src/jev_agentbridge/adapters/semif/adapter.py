"""SemIf adapter: next-token-logit scoring on a causal LM (Qwen3-0.6B by default).

Each option is presented as a letter A-P; one forward pass scores the next-token logits
of those letters only (softmax over them), then letters are mapped back to option ids.
It never calls model.generate().
"""

from __future__ import annotations

import copy
import os
import threading
from dataclasses import dataclass
from typing import Any, Sequence

import torch

from ...core.errors import InputTooLargeError
from ...core.models import MAX_OPTIONS, Decision, Scores, State
from ...core.ports import EngineInfo
from .prompt import (
    PROMPT_VERSION,
    build_decision_prompt,
    build_prefix,
    build_suffix,
    check_prompt_version,
    prompt_sha256,
)
from .tokenizer_slots import TokenSlotValidator

LETTERS = tuple(chr(ord("A") + i) for i in range(MAX_OPTIONS))


@dataclass(frozen=True)
class SemIfConfig:
    model_name: str = "Qwen/Qwen3-0.6B"
    model_revision: str = "main"
    device: str = "cpu"
    max_input_tokens: int = 4096
    prompt_version: str = PROMPT_VERSION

    @classmethod
    def from_env(cls) -> "SemIfConfig":
        return cls(
            model_name=os.getenv("JEV_MODEL_NAME", cls.model_name),
            model_revision=os.getenv("JEV_MODEL_REVISION", cls.model_revision),
            device=os.getenv("JEV_MODEL_DEVICE", cls.device),
            max_input_tokens=int(os.getenv("JEV_MAX_INPUT_TOKENS", str(cls.max_input_tokens))),
            prompt_version=os.getenv("JEV_SEMIF_PROMPT_VERSION", cls.prompt_version),
        )


def _option_pairs(decision: Decision) -> list[tuple[str, str]]:
    return [(LETTERS[i], option.description) for i, option in enumerate(decision.options)]


class SemIfAdapter:
    """DecisionAdapter backed by an in-process causal LM."""

    def __init__(
        self,
        *,
        model: Any,
        tokenizer: Any,
        model_name: str,
        model_revision: str,
        max_input_tokens: int,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self._model = model
        self._tokenizer = tokenizer
        self._model_name = model_name
        self._model_revision = model_revision
        self._max_input_tokens = max_input_tokens
        self._prompt_version = check_prompt_version(prompt_version)
        self._slots = TokenSlotValidator(tokenizer).validate(LETTERS)
        self._lock = threading.Lock()

    @classmethod
    def from_config(cls, config: SemIfConfig) -> "SemIfAdapter":
        from .model_loader import load_model

        model, tokenizer = load_model(
            model_name=config.model_name,
            revision=config.model_revision,
            device=config.device,
        )
        return cls(
            model=model,
            tokenizer=tokenizer,
            model_name=config.model_name,
            model_revision=config.model_revision,
            max_input_tokens=config.max_input_tokens,
            prompt_version=config.prompt_version,
        )

    def info(self) -> EngineInfo:
        return EngineInfo(
            name="semif",
            model=self._model_name,
            revision=self._model_revision,
            native_batch=True,
            thread_safe=True,  # the forward pass is guarded by self._lock
        )

    def is_ready(self) -> bool:
        return True

    def _tokenize(self, prompt: str) -> torch.Tensor:
        input_ids = self._tokenizer(prompt, return_tensors="pt", truncation=False)["input_ids"]
        if input_ids.shape[-1] > self._max_input_tokens:
            raise InputTooLargeError(
                f"Prompt has {input_ids.shape[-1]} tokens, above the configured maximum of "
                f"{self._max_input_tokens} (JEV_MAX_INPUT_TOKENS)"
            )
        return input_ids

    def _forward(self, **kwargs: Any) -> Any:
        try:
            return self._model(logits_to_keep=1, **kwargs)
        except TypeError:  # older transformers without logits_to_keep
            return self._model(**kwargs)

    def _letter_probabilities(self, logits: torch.Tensor, decision: Decision) -> dict[str, float]:
        letters = LETTERS[: len(decision.options)]
        token_ids = [self._slots[letter].token_id for letter in letters]
        probabilities = torch.softmax(logits[:, -1, :][:, token_ids].squeeze(0), dim=-1)
        return {
            option.id: float(probability)
            for option, probability in zip(decision.options, probabilities)
        }

    def _prompt(self, state: State, decision: Decision) -> str:
        return build_decision_prompt(
            state=state,
            question=decision.question,
            options=_option_pairs(decision),
            version=self._prompt_version,
        )

    def _details(self, prompt: str) -> dict[str, Any]:
        return {"prompt_version": self._prompt_version, "prompt_sha256": prompt_sha256(prompt)}

    def score(self, *, state: State, decision: Decision) -> Scores:
        prompt = self._prompt(state, decision)
        input_ids = self._tokenize(prompt)
        with self._lock, torch.no_grad():
            outputs = self._forward(input_ids=input_ids, use_cache=False)
        return Scores(
            probabilities=self._letter_probabilities(outputs.logits, decision),
            input_tokens=int(input_ids.shape[-1]),
            details=self._details(prompt),
        )

    def score_batch(self, *, state: State, decisions: Sequence[Decision]) -> list[Scores]:
        """Prefill the shared state once, then score each suffix on a copy of the KV cache."""

        prefix_ids = self._tokenize(build_prefix(state))
        suffixes = [
            self._tokenize(
                build_suffix(
                    decision.question, _option_pairs(decision), version=self._prompt_version
                )
            )
            for decision in decisions
        ]
        results: list[Scores] = []
        with self._lock, torch.no_grad():
            prefix_outputs = self._model(input_ids=prefix_ids, use_cache=True)
            past_key_values = prefix_outputs.past_key_values
            if past_key_values is None:
                raise RuntimeError("Model does not expose a reusable KV cache")
            for decision, suffix_ids in zip(decisions, suffixes):
                outputs = self._forward(
                    input_ids=suffix_ids,
                    past_key_values=copy.deepcopy(past_key_values),
                    use_cache=False,
                )
                results.append(
                    Scores(
                        probabilities=self._letter_probabilities(outputs.logits, decision),
                        input_tokens=int(prefix_ids.shape[-1] + suffix_ids.shape[-1]),
                        details=self._details(self._prompt(state, decision)),
                    )
                )
        return results
