"""Tests for the SemIf adapter."""

from __future__ import annotations

import pytest
import torch

from jev_cpu_agentbridge.adapters.semif.prompt import build_decision_prompt, prompt_sha256
from jev_cpu_agentbridge.adapters.semif.tokenizer_slots import (
    TokenSlotError,
    TokenSlotValidator,
)
from jev_cpu_agentbridge.core.errors import InputTooLargeError
from jev_cpu_agentbridge.core.models import Decision, Option
from jev_cpu_agentbridge.core.service import DecisionService
from tests.conftest import FakeModel, FakeTokenizer, HighModel, make_adapter

RETRY_ABORT = (Option(id="retry", description="Retry"), Option(id="abort", description="Abort"))


class DeterministicModel(FakeModel):
    """Model where A (token 0) always wins."""

    def __call__(self, *, input_ids, use_cache, logits_to_keep=None, past_key_values=None):
        self.calls += 1
        if use_cache:
            self.calls_with_cache += 1
        seq_len = max(input_ids.shape[-1] if input_ids.dim() > 1 else 1, 1)
        logits = torch.zeros(1, seq_len, 100)
        logits[:, -1, 0] = 5.0
        logits[:, -1, 1] = 1.0
        cache = object() if use_cache else None
        return type("Out", (), {"logits": logits, "past_key_values": cache})()


def test_token_slot_validation() -> None:
    letters = tuple(chr(ord("A") + i) for i in range(16))
    slots = TokenSlotValidator(FakeTokenizer()).validate(letters)
    assert len(slots) == 16
    for letter in letters:
        assert slots[letter].token_id == ord(letter) - ord("A")


def test_token_slot_collision_detected() -> None:
    class BadTokenizer(FakeTokenizer):
        def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
            return [0] * len(text)

    with pytest.raises(TokenSlotError):
        TokenSlotValidator(BadTokenizer()).validate(("A", "B"))


def test_score_keys_probabilities_by_option_id() -> None:
    scores = make_adapter().score(state="test", decision=Decision("which?", RETRY_ABORT))
    assert set(scores.probabilities) == {"retry", "abort"}
    assert sum(scores.probabilities.values()) == pytest.approx(1.0)
    assert scores.input_tokens and scores.input_tokens > 0
    assert scores.details["prompt_version"] == "direct-options-v1"


def test_batch_uses_kv_cache() -> None:
    adapter = make_adapter()
    results = adapter.score_batch(
        state="test",
        decisions=[
            Decision("which?", RETRY_ABORT),
            Decision("other?", (Option("retry", "Retry"), Option("escalate", "Escalate"))),
        ],
    )
    assert len(results) == 2
    assert set(results[1].probabilities) == {"retry", "escalate"}
    assert adapter._model.calls_with_cache >= 1


def test_direct_and_batch_equivalent() -> None:
    adapter = make_adapter(DeterministicModel())
    decision = Decision("q", (Option("a", "A"), Option("b", "B")))
    direct = adapter.score(state="state", decision=decision)
    batch = adapter.score_batch(state="state", decisions=[decision])[0]
    assert direct.probabilities == pytest.approx(batch.probabilities)


def test_oversized_input_rejected() -> None:
    adapter = make_adapter(max_input_tokens=5)
    with pytest.raises(InputTooLargeError):
        adapter.score(state="x", decision=Decision("y", (Option("a", "A"), Option("b", "B"))))


def test_threshold_applied_by_service() -> None:
    decision = Decision("which?", (Option("a", "A"), Option("b", "B")))
    loose = DecisionService(make_adapter(HighModel()), default_threshold=0.5)
    strict = DecisionService(make_adapter(HighModel()), default_threshold=0.99)
    assert loose.decide(state="t", decision=decision).accepted is True
    result = strict.decide(state="t", decision=decision)
    assert result.decision.id == "a"
    assert result.accepted is False
    assert result.metadata["engine"] == "semif"


def test_prompt_contains_all_components() -> None:
    prompt = build_decision_prompt(
        state="evidence", question="criterion", options=[("A", "A"), ("B", "B")]
    )
    assert "evidence" in prompt and "criterion" in prompt
    assert "A." in prompt and "B." in prompt
    assert len(prompt_sha256(prompt)) == 64


def test_prompt_versions() -> None:
    from jev_cpu_agentbridge.adapters.semif.prompt import build_prefix, build_suffix

    pairs = [("A", "A"), ("B", "B")]
    v1 = build_decision_prompt(state="s", question="q", options=pairs)
    v2 = build_decision_prompt(state="s", question="q", options=pairs, version="direct-options-v2")
    assert v2 == v1 + "\n\nAnswer:"
    assert v2 == build_prefix("s") + build_suffix("q", pairs, version="direct-options-v2")
    with pytest.raises(ValueError, match="Unknown semif prompt version"):
        build_decision_prompt(state="s", question="q", options=pairs, version="nope")


def test_adapter_reports_selected_prompt_version() -> None:
    from jev_cpu_agentbridge.adapters.semif.adapter import SemIfAdapter

    adapter = SemIfAdapter(
        model=FakeModel(),
        tokenizer=FakeTokenizer(),
        model_name="fake",
        model_revision="fake",
        max_input_tokens=10000,
        prompt_version="direct-options-v2",
    )
    scores = adapter.score(state="s", decision=Decision("q", RETRY_ABORT))
    assert scores.details["prompt_version"] == "direct-options-v2"
