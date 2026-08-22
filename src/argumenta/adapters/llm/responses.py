"""What every Claude adapter has to check about a response before trusting it."""

from typing import Literal

from argumenta.domain.errors import EvaluationFailedError

Effort = Literal["low", "medium", "high"]
"""How much thinking the model spends. Sonnet 5 thinks adaptively and defaults
to high, which for a graded rubric is paid deliberation we do not need."""


def ensure_not_truncated(stop_reason: str | None, max_tokens: int) -> None:
    """Thinking shares max_tokens with the answer, so a tight budget truncates
    the response instead of failing loudly, and the caller then sees a schema
    error (or an empty reaction) that says nothing about the real cause."""
    if stop_reason == "max_tokens":
        raise EvaluationFailedError(
            f"engine response truncated at max_tokens={max_tokens}: thinking plus "
            "answer did not fit"
        )
