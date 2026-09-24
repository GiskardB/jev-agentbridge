"""Shared test fixtures."""

from __future__ import annotations

import torch


class FakeTokenizer:
    """Tokenizer mapping A-P to tokens 0-15 and other chars to unique tokens."""

    def __init__(self) -> None:
        self._vocab = {letter: i for i, letter in enumerate("ABCDEFGHIJKLMNOP")}
        self.encode_calls = 0
        self.decode_calls = 0

    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
        self.encode_calls += 1
        if len(text) == 1 and text in self._vocab:
            return [self._vocab[text]]
        tokens = []
        for ch in text:
            if ch in self._vocab:
                tokens.append(self._vocab[ch])
            else:
                tokens.append(100 + hash(ch) % 1000)
        return tokens

    def decode(self, tokens: list[int], *, skip_special_tokens: bool = True) -> str:
        self.decode_calls += 1
        for token in tokens:
            if 0 <= token < len("ABCDEFGHIJKLMNOP"):
                return "ABCDEFGHIJKLMNOP"[token]
        return ""

    def __call__(self, text: str, *, return_tensors: str = "pt", truncation: bool = False):
        tokens = self.encode(text, add_special_tokens=False)
        return {"input_ids": torch.tensor([tokens]) if tokens else torch.tensor([[0]])}


class FakeModel:
    """Model returning random logits shaped for any input."""

    def __init__(self) -> None:
        self.calls = 0
        self.calls_with_cache = 0

    def __call__(
        self,
        *,
        input_ids: torch.Tensor,
        use_cache: bool,
        logits_to_keep: int | None = None,
        past_key_values=None,
    ):
        self.calls += 1
        if use_cache:
            self.calls_with_cache += 1
        seq_len = max(input_ids.shape[-1] if input_ids.dim() > 1 else 1, 1)
        logits = torch.randn(1, seq_len, 100)
        cache = object() if use_cache else None
        return type("Out", (), {
            "logits": logits,
            "past_key_values": cache,
        })()


def make_adapter(model: object | None = None, max_input_tokens: int = 10000):
    from jev_agentbridge.adapters.semif.adapter import SemIfAdapter

    return SemIfAdapter(
        model=model or FakeModel(),
        tokenizer=FakeTokenizer(),
        model_name="fake",
        model_revision="fake",
        max_input_tokens=max_input_tokens,
    )


class FakeAdapter:
    """DecisionAdapter returning fixed probabilities: first option gets `top`."""

    def __init__(
        self,
        top: float = 0.8,
        ready: bool = True,
        thread_safe: bool = True,
        native_types: frozenset[str] = frozenset({"choice"}),
    ) -> None:
        self.top = top
        self.ready = ready
        self.thread_safe = thread_safe
        self.native_types = native_types
        self.batch_calls = 0
        self.seen_types: list[str] = []
        self.error: Exception | None = None

    def info(self):
        from jev_agentbridge.core.ports import EngineInfo

        return EngineInfo(
            name="fake",
            model="fake-model",
            thread_safe=self.thread_safe,
            native_types=self.native_types,
        )

    def is_ready(self) -> bool:
        return self.ready

    def score(self, *, state, decision):
        from jev_agentbridge.core.models import Scores

        if self.error is not None:
            raise self.error
        self.seen_types.append(decision.type)
        rest = (1 - self.top) / (len(decision.options) - 1)
        probabilities = {o.id: rest for o in decision.options}
        probabilities[decision.options[0].id] = self.top
        return Scores(probabilities=probabilities, input_tokens=7, details={"k": "v"})

    def score_batch(self, *, state, decisions):
        self.batch_calls += 1
        return [self.score(state=state, decision=d) for d in decisions]


class HighModel(FakeModel):
    """Model where token 0 (A) always has highest logit."""

    def __call__(self, *, input_ids, use_cache, logits_to_keep=None, past_key_values=None):
        self.calls += 1
        if use_cache:
            self.calls_with_cache += 1
        seq_len = max(input_ids.shape[-1] if input_ids.dim() > 1 else 1, 1)
        logits = torch.zeros(1, seq_len, 100)
        logits[:, -1, 0] = 3.0
        logits[:, -1, 1] = 2.0
        cache = object() if use_cache else None
        return type("Out", (), {"logits": logits, "past_key_values": cache})()
