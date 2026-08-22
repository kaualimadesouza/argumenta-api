"""The Claude call contract every adapter here shares: the knobs we send and
what we check before trusting a response.

Sonnet 5 removed the sampling parameters (a non-default `temperature`, `top_p`
or `top_k` is a 400) and thinks adaptively unless told otherwise, so the only
deliberation knob left is `effort`, and thinking comes out of `max_tokens`.
"""

from anthropic.types import StopReason

from argumenta.adapters.llm.effort import Effort
from argumenta.domain.errors import EvaluationFailedError

__all__ = ["Effort", "ensure_usable"]

_OUT_OF_ROOM: tuple[StopReason, ...] = ("max_tokens", "model_context_window_exceeded")


def ensure_usable(stop_reason: StopReason | None, max_tokens: int) -> None:
    """Raises when the model stopped for a reason that leaves the response
    unusable, instead of letting it surface later as "no tool_use block" or an
    empty reaction, which says nothing about the real cause.

    Thinking shares `max_tokens` with the answer, so running out of room is the
    failure mode a tight budget produces.
    """
    if stop_reason in _OUT_OF_ROOM:
        raise EvaluationFailedError(
            f"engine response unusable: stopped on {stop_reason} with "
            f"max_tokens={max_tokens} shared between thinking and answer"
        )
    if stop_reason == "refusal":
        raise EvaluationFailedError("engine refused to answer this request")
