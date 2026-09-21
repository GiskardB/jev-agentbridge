"""Model and tokenizer loading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .settings import Settings


@dataclass(frozen=True)
class LoadedModel:
    """A loaded model and tokenizer pair."""

    model: Any
    tokenizer: Any


class ModelLoader:
    """Load a model and tokenizer from Hugging Face."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def load(self) -> LoadedModel:
        """Load the configured model and tokenizer."""

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            self._settings.model_name,
            revision=self._settings.model_revision,
        )
        model = AutoModelForCausalLM.from_pretrained(
            self._settings.model_name,
            revision=self._settings.model_revision,
            torch_dtype=torch.float32,
            device_map=self._settings.model_device,
        )
        model.eval()
        return LoadedModel(model=model, tokenizer=tokenizer)
