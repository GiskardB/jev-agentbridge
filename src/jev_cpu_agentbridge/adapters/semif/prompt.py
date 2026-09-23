"""SemIf-style prompt construction."""

from __future__ import annotations

import hashlib
import json
from typing import Any

PROMPT_VERSION = "direct-options-v1"  # default, unchanged since 0.1.0

# Text appended after the option list, per prompt version. v2 ends on "Answer:" so the next
# token is the option letter; on the 12-row sample it scored 9/12 vs 5/12 for v1
# (docs/performance.md). Direct and batch prompts are prefix + suffix, so both stay equal.
PROMPT_VERSIONS: dict[str, str] = {
    "direct-options-v1": "",
    "direct-options-v2": "\n\nAnswer:",
}


def check_prompt_version(version: str) -> str:
    if version not in PROMPT_VERSIONS:
        raise ValueError(
            f"Unknown semif prompt version {version!r}. Available: {sorted(PROMPT_VERSIONS)}"
        )
    return version


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
    version: str = PROMPT_VERSION,
) -> str:
    """Build a SemIf-style decision prompt.

    The prompt applies the criterion to the evidence and asks the model to
    respond with exactly one uppercase option letter, with no reasoning.
    """

    return build_prefix(state) + build_suffix(question, options, version=version)


def build_prefix(state: str | dict[str, Any] | list[Any]) -> str:
    """Build the shared prefix for a batch of decisions."""

    return (
        "You are a decision engine.\n"
        "Apply the criterion to the supplied evidence. Choose exactly one listed option.\n"
        "Respond with only its uppercase letter, with no explanation or reasoning.\n\n"
        f"Evidence:\n{_serialize_state(state)}\n\n"
        "Criterion:\n"
    )


def build_suffix(
    question: str, options: list[tuple[str, str]], *, version: str = PROMPT_VERSION
) -> str:
    """Build the per-decision suffix for a batch."""

    return (
        f"{question}\n\n"
        "Options:\n"
        f"{_option_lines(options)}"
        f"{PROMPT_VERSIONS[check_prompt_version(version)]}"
    )


def prompt_sha256(prompt: str) -> str:
    """Return the SHA-256 hash of a prompt."""

    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
