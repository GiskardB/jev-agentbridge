"""Tests for the SemIf engine."""

from __future__ import annotations

import pytest
import torch

from jev_cpu_agentbridge.engine.base import Option
from jev_cpu_agentbridge.engine.prompt import build_decision_prompt, prompt_sha256
from jev_cpu_agentbridge.engine.semif import SemIfEngine
from jev_cpu_agentbridge.engine.tokenizer_slots import (
    TokenSlotError,
    TokenSlotValidator,
)
from tests.conftest import FakeModel, FakeTokenizer, HighModel, make_engine


class DeterministicModel(FakeModel):
    """Model returning logits based on the input token ids."""

    def __call__(self, *, input_ids, use_cache, logits_to_keep=None, past_key_values=None):
        self.calls += 1
        if use_cache:
            self.calls_with_cache += 1
        seq_len = max(input_ids.shape[-1] if input_ids.dim() > 1 else 1, 1)
        logits = torch.zeros(1, seq_len, 100)
        # Make A (token 0) always win for deterministic equivalence testing.
        logits[:, -1, 0] = 5.0
        logits[:, -1, 1] = 1.0
        cache = object() if use_cache else None
        return type("Out", (), {"logits": logits, "past_key_values": cache})()


def test_token_slot_validation() -> None:
    tokenizer = FakeTokenizer()
    validator = TokenSlotValidator(tokenizer)
    letters = tuple(chr(ord("A") + i) for i in range(16))
    slots = validator.validate(letters)
    assert len(slots) == 16
    for letter in letters:
        assert slots[letter].letter == letter
        assert slots[letter].token_id == ord(letter) - ord("A")


def test_token_slot_collision_detected() -> None:
    class BadTokenizer(FakeTokenizer):
        def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
            return [0] * len(text)

    validator = TokenSlotValidator(BadTokenizer())
    with pytest.raises(TokenSlotError):
        validator.validate(("A", "B"))


def test_direct_decision() -> None:
    engine = make_engine()
    result = engine.decide(
        state="test",
        question="which?",
        options=[Option(id="retry", description="Retry"), Option(id="abort", description="Abort")],
    )
    assert result.decision.id in ("retry", "abort")
    assert len(result.probabilities) == 2
    assert 0 <= result.selected_probability <= 1
    assert isinstance(result.metadata, dict)
    assert result.metadata["mode"] == "direct"


def test_batch_shared_mode() -> None:
    engine = make_engine()
    results = engine.decide_batch(
        state="test",
        decisions=[
            (
                "which?",
                [Option(id="retry", description="Retry"), Option(id="abort", description="Abort")],
            ),
            (
                "other?",
                [
                    Option(id="retry", description="Retry"),
                    Option(id="escalate", description="Escalate"),
                ],
            ),
        ],
    )
    assert len(results) == 2
    assert engine._model.calls_with_cache >= 1


def test_direct_and_batch_equivalent() -> None:
    engine = SemIfEngine(
        model=DeterministicModel(),
        tokenizer=FakeTokenizer(),
        model_name="fake",
        model_revision="fake",
        max_input_tokens=10000,
        min_selected_probability=0.5,
    )
    opts = [Option(id="a", description="A"), Option(id="b", description="B")]
    direct = engine.decide(state="state", question="q", options=opts)
    batch = engine.decide_batch(state="state", decisions=[("q", opts)])[0]
    assert direct.decision.id == batch.decision.id
    assert len(direct.probabilities) == len(batch.probabilities)


def test_oversized_input_rejected() -> None:
    engine = SemIfEngine(
        model=FakeModel(),
        tokenizer=FakeTokenizer(),
        model_name="fake",
        model_revision="fake",
        max_input_tokens=5,
        min_selected_probability=0.5,
    )
    with pytest.raises(ValueError):
        engine.decide(
            state="x",
            question="y",
            options=[Option(id="a", description="A"), Option(id="b", description="B")],
        )


def test_invalid_option_count_rejected() -> None:
    engine = make_engine()
    with pytest.raises(ValueError):
        engine.decide(
            state="x",
            question="y",
            options=[Option(id="a", description="A")],
        )
    with pytest.raises(ValueError):
        engine.decide(
            state="x",
            question="y",
            options=[Option(id=str(i), description=str(i)) for i in range(17)],
        )


def test_accepted_threshold() -> None:
    engine = SemIfEngine(
        model=HighModel(),
        tokenizer=FakeTokenizer(),
        model_name="fake",
        model_revision="fake",
        max_input_tokens=10000,
        min_selected_probability=0.5,
    )
    result = engine.decide(
        state="test",
        question="which?",
        options=[Option(id="a", description="A"), Option(id="b", description="B")],
    )
    assert result.decision.id == "a"
    assert result.accepted is True

    engine2 = SemIfEngine(
        model=HighModel(),
        tokenizer=FakeTokenizer(),
        model_name="fake",
        model_revision="fake",
        max_input_tokens=10000,
        min_selected_probability=0.99,
    )
    result2 = engine2.decide(
        state="test",
        question="which?",
        options=[Option(id="a", description="A"), Option(id="b", description="B")],
    )
    assert result2.accepted is False


def test_prompt_contains_all_components() -> None:
    prompt = build_decision_prompt(
        state="evidence",
        question="criterion",
        options=[("A", "A"), ("B", "B")],
    )
    assert "evidence" in prompt
    assert "criterion" in prompt
    assert "A." in prompt
    assert "B." in prompt
    sha = prompt_sha256(prompt)
    assert len(sha) == 64


def test_prompt_version_set() -> None:
    engine = make_engine()
    result = engine.decide(
        state="test",
        question="which?",
        options=[Option(id="a", description="A"), Option(id="b", description="B")],
    )
    assert result.metadata["prompt_version"] == "direct-options-v1"
