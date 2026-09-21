"""SemIf/JEV CPU decision engine."""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Sequence

import torch

from .base import DecisionEngine, DecisionResult, Option
from .prompt import (
    PROMPT_VERSION,
    build_decision_prompt,
    build_prefix,
    build_suffix,
    prompt_sha256,
)
from .tokenizer_slots import TokenSlotValidator


class SemIfEngine(DecisionEngine):
    """Decision engine using the SemIf/JEV CPU scoring path.

    The engine scores the next-token logits for the allowed option letters
    (A-P), applies softmax over those letters only, and returns the best
    option. It never calls model.generate().
    """

    def __init__(
        self,
        *,
        model: Any,
        tokenizer: Any,
        model_name: str,
        model_revision: str,
        max_input_tokens: int,
        min_selected_probability: float,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self._model = model
        self._tokenizer = tokenizer
        self._model_name = model_name
        self._model_revision = model_revision
        self._max_input_tokens = max_input_tokens
        self._min_selected_probability = min_selected_probability
        self._prompt_version = prompt_version
        self._letters = tuple(chr(ord("A") + i) for i in range(16))
        self._slots = TokenSlotValidator(tokenizer).validate(self._letters)
        self._lock = threading.Lock()

    @staticmethod
    def _option_letters(count: int) -> tuple[str, ...]:
        return tuple(chr(ord("A") + i) for i in range(count))

    def _tokenize(self, prompt: str) -> torch.Tensor:
        encoded = self._tokenizer(prompt, return_tensors="pt", truncation=False)
        input_ids = encoded["input_ids"]
        if input_ids.shape[-1] > self._max_input_tokens:
            raise ValueError(
                f"Prompt exceeds the configured maximum of "
                f"{self._max_input_tokens} tokens"
            )
        return input_ids

    def _score(
        self,
        *,
        input_ids: torch.Tensor,
        letters: Sequence[str],
    ) -> tuple[dict[str, float], int]:
        """Run one forward pass and score the allowed letters."""

        option_ids = [self._slots[letter].token_id for letter in letters]
        with self._lock, torch.no_grad():
            try:
                outputs = self._model(
                    input_ids=input_ids,
                    use_cache=False,
                    logits_to_keep=1,
                )
            except TypeError:
                outputs = self._model(input_ids=input_ids, use_cache=False)

        logits = outputs.logits[:, -1, :]
        option_logits = logits[:, option_ids].squeeze(0)
        probabilities = torch.softmax(option_logits, dim=-1)
        return (
            {letter: float(probability) for letter, probability in zip(letters, probabilities)},
            int(input_ids.shape[-1]),
        )

    def decide(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: Sequence[Option],
        min_selected_probability: float | None = None,
    ) -> DecisionResult:
        """Evaluate one decision in direct mode."""

        if not 2 <= len(options) <= 16:
            raise ValueError("A decision must contain between 2 and 16 options.")

        started = time.perf_counter()
        letters = self._option_letters(len(options))
        option_pairs = [(letters[i], option.description) for i, option in enumerate(options)]
        prompt = build_decision_prompt(state=state, question=question, options=option_pairs)
        input_ids = self._tokenize(prompt)
        probabilities, input_tokens = self._score(input_ids=input_ids, letters=letters)

        selected_index = max(range(len(options)), key=lambda index: probabilities[letters[index]])
        selected_probability = probabilities[letters[selected_index]]
        threshold = (
            self._min_selected_probability
            if min_selected_probability is None
            else min_selected_probability
        )
        elapsed_ms = (time.perf_counter() - started) * 1000

        return DecisionResult(
            decision=options[selected_index],
            probabilities=probabilities,
            selected_probability=selected_probability,
            accepted=selected_probability >= threshold,
            metadata={
                "engine": "semif",
                "mode": "direct",
                "model": self._model_name,
                "model_revision": self._model_revision,
                "input_tokens": input_tokens,
                "latency_ms": round(elapsed_ms, 3),
                "prompt_version": self._prompt_version,
                "prompt_sha256": prompt_sha256(prompt),
            },
        )

    def decide_batch(
        self,
        *,
        state: str | dict[str, Any] | list[Any],
        decisions: Sequence[tuple[str, Sequence[Option]]],
        min_selected_probability: float | None = None,
    ) -> list[DecisionResult]:
        """Evaluate decisions sharing one state using prefix prefill + KV cache.

        The common prefix is prefilled once, the KV cache is replicated for
        each decision suffix, and suffixes are evaluated together in a batch.
        """

        if not decisions:
            return []

        threshold = (
            self._min_selected_probability
            if min_selected_probability is None
            else min_selected_probability
        )
        started = time.perf_counter()

        prefix_prompt = build_prefix(state)
        prefix_ids = self._tokenize(prefix_prompt)

        results: list[DecisionResult] = []
        with self._lock, torch.no_grad():
            try:
                prefix_outputs = self._model(
                    input_ids=prefix_ids,
                    use_cache=True,
                )
            except TypeError:
                prefix_outputs = self._model(input_ids=prefix_ids, use_cache=True)
            past_key_values = prefix_outputs.past_key_values
            if past_key_values is None:
                raise RuntimeError("Model does not expose a reusable KV cache")

            for question, options in decisions:
                if not 2 <= len(options) <= 16:
                    raise ValueError("A decision must contain between 2 and 16 options.")
                letters = self._option_letters(len(options))
                option_pairs = [
                    (letters[i], option.description) for i, option in enumerate(options)
                ]
                suffix_prompt = build_suffix(question, option_pairs)
                suffix_ids = self._tokenize(suffix_prompt)
                try:
                    suffix_outputs = self._model(
                        input_ids=suffix_ids,
                        past_key_values=copy.deepcopy(past_key_values),
                        use_cache=False,
                        logits_to_keep=1,
                    )
                except TypeError:
                    suffix_outputs = self._model(
                        input_ids=suffix_ids,
                        past_key_values=copy.deepcopy(past_key_values),
                        use_cache=False,
                    )
                logits = suffix_outputs.logits[:, -1, :]
                option_ids = [self._slots[letter].token_id for letter in letters]
                option_logits = logits[:, option_ids].squeeze(0)
                probabilities = torch.softmax(option_logits, dim=-1)
                probability_map = {
                    letter: float(probability)
                    for letter, probability in zip(letters, probabilities)
                }
                selected_index = max(
                    range(len(options)),
                    key=lambda index: probability_map[letters[index]],
                )
                selected_probability = probability_map[letters[selected_index]]
                elapsed_ms = (time.perf_counter() - started) * 1000
                results.append(
                    DecisionResult(
                        decision=options[selected_index],
                        probabilities=probability_map,
                        selected_probability=selected_probability,
                        accepted=selected_probability >= threshold,
                        metadata={
                            "engine": "semif",
                            "mode": "shared",
                            "model": self._model_name,
                            "model_revision": self._model_revision,
                            "input_tokens": int(prefix_ids.shape[-1] + suffix_ids.shape[-1]),
                            "latency_ms": round(elapsed_ms, 3),
                            "prompt_version": self._prompt_version,
                            "prompt_sha256": prompt_sha256(
                                build_decision_prompt(
                                    state=state,
                                    question=question,
                                    options=option_pairs,
                                )
                            ),
                            "prefill_seconds": None,
                            "cache_replication_seconds": None,
                            "suffix_forward_seconds": None,
                        },
                    )
                )

        return results