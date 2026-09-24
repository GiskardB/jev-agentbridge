"""Service-level configuration. Engine-specific settings live in each adapter's config."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Settings loaded from environment variables."""

    host: str = "127.0.0.1"
    port: int = 8000
    engine: str = "laya"  # best measured in-process engine; see docs/performance.md
    min_selected_probability: float = 0.60
    mcp_enabled: bool = True
    # False emulates noul and score as a plain choice even on engines that support them.
    native_types: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("JEV_HOST", cls.host),
            port=int(os.getenv("JEV_PORT", str(cls.port))),
            engine=os.getenv("JEV_ENGINE", cls.engine),
            mcp_enabled=_flag("JEV_MCP_ENABLED"),
            native_types=_flag("JEV_NATIVE_TYPES"),
            min_selected_probability=float(
                os.getenv("JEV_MIN_SELECTED_PROBABILITY", str(cls.min_selected_probability))
            ),
        )


def _flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() not in ("0", "false", "no", "off")
