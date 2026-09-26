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
    # Which noul/score types go to the engine's native path; the rest are asked as a choice.
    # Off by default: on the bundled question-types suite native was never better (Kev: equal;
    # Laya score: much worse). See examples/eval/question_types.
    native_types: bool | frozenset[str] = False
    # score decisions: levels on each side of the chosen one that count towards `accepted`.
    score_tolerance: int = 1

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("JEV_HOST", cls.host),
            port=int(os.getenv("JEV_PORT", str(cls.port))),
            engine=os.getenv("JEV_ENGINE", cls.engine),
            mcp_enabled=_flag("JEV_MCP_ENABLED"),
            native_types=_native_types(os.getenv("JEV_NATIVE_TYPES", "false")),
            score_tolerance=int(os.getenv("JEV_SCORE_TOLERANCE", str(cls.score_tolerance))),
            min_selected_probability=float(
                os.getenv("JEV_MIN_SELECTED_PROBABILITY", str(cls.min_selected_probability))
            ),
        )


def _native_types(value: str) -> bool | frozenset[str]:
    """`true`/`all`, `false`/`none`, or a comma-separated list such as `noul` or `noul,score`."""

    value = value.strip().lower()
    if value in ("1", "true", "yes", "on", "all"):
        return True
    if value in ("", "0", "false", "no", "off", "none"):
        return False
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def _flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() not in ("0", "false", "no", "off")
