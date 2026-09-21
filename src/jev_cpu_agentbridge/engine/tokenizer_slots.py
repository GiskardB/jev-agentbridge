"""Validation of tokenizer slots for option letters A–P."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TokenSlot:
    """A validated tokenizer slot for one option letter."""

    letter: str
    token_id: int


class TokenSlotError(RuntimeError):
    """Raised when tokenizer slots cannot be validated."""


class TokenSlotValidator:
    """Validate that option letters map to exactly one tokenizer token each."""

    def __init__(self, tokenizer: Any) -> None:
        self._tokenizer = tokenizer

    def validate(self, letters: tuple[str, ...]) -> dict[str, TokenSlot]:
        """Validate slots for the given letters and return the mapping."""

        slots: dict[str, TokenSlot] = {}
        seen_token_ids: set[int] = set()

        for letter in letters:
            encoded = self._tokenizer.encode(letter, add_special_tokens=False)
            if len(encoded) != 1:
                raise TokenSlotError(
                    f"Option letter {letter!r} must map to exactly one token; "
                    f"got {len(encoded)} tokens"
                )

            token_id = encoded[0]
            decoded = self._tokenizer.decode([token_id], skip_special_tokens=False)
            if decoded.strip() != letter:
                raise TokenSlotError(
                    f"Option letter {letter!r} does not round-trip correctly "
                    f"(decoded as {decoded!r})"
                )

            if token_id in seen_token_ids:
                raise TokenSlotError(
                    f"Option letter {letter!r} collides with an existing token id {token_id}"
                )

            seen_token_ids.add(token_id)
            slots[letter] = TokenSlot(letter=letter, token_id=token_id)

        return slots
