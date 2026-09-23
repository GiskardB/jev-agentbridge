"""SemIf-style prompt construction."""

from __future__ import annotations

import hashlib
import json
from typing import Any

PROMPT_VERSION = "direct-options-v1"


def _serialize_state(state: str | dict[str, Any] | list[Any]) -> str:
    """Serialize state into a stable string representation."""

    if isinstance(state, str):
        return state
    return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _option_lines(options: list[tuple[str, str]]) -> str:
    return "\n".join(f"{letter}. {description}" for letter, description in options)


def build_decision_prompt(
    *,
    state: str | dict[str, Any] | list[Any],
    question: str,
    options: list[tuple[str, str]],
) -> str:
    """Build a SemIf-style decision prompt.

    The prompt applies the criterion to the evidence and asks the model to
    respond with exactly one uppercase option letter, with no reasoning.
    """

    return (
        "You are a decision engine.\n"
        "Apply the criterion to the supplied evidence. Choose exactly one listed option.\n"
        "Respond with only its uppercase letter, with no explanation or reasoning.\n\n"
        f"Evidence:\n{_serialize_state(state)}\n\n"
        f"Criterion:\n{question}\n\n"
        "Options:\n"
        f"{_option_lines(options)}"
    )


def build_prefix(state: str | dict[str, Any] | list[Any]) -> str:
    """Build the shared prefix for a batch of decisions."""

    return (
        "You are a decision engine.\n"
        "Apply the criterion to the supplied evidence. Choose exactly one listed option.\n"
        "Respond with only its uppercase letter, with no explanation or reasoning.\n\n"
        f"Evidence:\n{_serialize_state(state)}\n\n"
        "Criterion:\n"
    )


def build_suffix(question: str, options: list[tuple[str, str]]) -> str:
    """Build the per-decision suffix for a batch."""

    return (
        f"{question}\n\n"
        "Options:\n"
        f"{_option_lines(options)}"
    )


def prompt_sha256(prompt: str) -> str:
    """Return the SHA-256 hash of a prompt."""

    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
