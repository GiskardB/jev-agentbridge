"""Model and tokenizer loading for the SemIf adapter."""

from __future__ import annotations

from typing import Any


def load_model(*, model_name: str, revision: str, device: str) -> tuple[Any, Any]:
    """Load a causal LM and its tokenizer from Hugging Face, in eval mode on `device`."""

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        revision=revision,
        torch_dtype=torch.float32,
    )
    model.to(device)
    model.eval()
    return model, tokenizer
