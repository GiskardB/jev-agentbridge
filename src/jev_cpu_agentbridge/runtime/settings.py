"""Service-level configuration. Engine-specific settings live in each adapter's config."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Settings loaded from environment variables."""

    host: str = "127.0.0.1"
    port: int = 8000
    engine: str = "laya"  # best measured accuracy and latency on CPU; see docs/performance.md
    min_selected_probability: float = 0.60

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("JEV_HOST", cls.host),
            port=int(os.getenv("JEV_PORT", str(cls.port))),
            engine=os.getenv("JEV_ENGINE", cls.engine),
            min_selected_probability=float(
                os.getenv("JEV_MIN_SELECTED_PROBABILITY", str(cls.min_selected_probability))
            ),
        )
