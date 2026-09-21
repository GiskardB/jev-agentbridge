"""Runtime configuration for JEV-CPU-AgentBridge."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    host: str = "127.0.0.1"
    port: int = 8000
    model_name: str = "Qwen/Qwen3-0.6B"
    model_revision: str = "main"
    model_dtype: str = "float32"
    model_device: str = "cpu"
    max_input_tokens: int = 4096
    min_selected_probability: float = 0.60
    prompt_version: str = "direct-options-v1"
    hf_home: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from the environment."""

        return cls(
            host=os.getenv("JEV_HOST", "127.0.0.1"),
            port=int(os.getenv("JEV_PORT", "8000")),
            model_name=os.getenv("JEV_MODEL_NAME", "Qwen/Qwen3-0.6B"),
            model_revision=os.getenv("JEV_MODEL_REVISION", "main"),
            model_dtype=os.getenv("JEV_MODEL_DTYPE", "float32"),
            model_device=os.getenv("JEV_MODEL_DEVICE", "cpu"),
            max_input_tokens=int(os.getenv("JEV_MAX_INPUT_TOKENS", "4096")),
            min_selected_probability=float(os.getenv("JEV_MIN_SELECTED_PROBABILITY", "0.60")),
            prompt_version=os.getenv("JEV_PROMPT_VERSION", "direct-options-v1"),
            hf_home=os.getenv("HF_HOME"),
        )
