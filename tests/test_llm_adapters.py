"""Issue #12: what the Claude adapters have to check about a response.

Pure, so it runs on every PR: the adapters themselves are exercised by the
calibration suite, which costs tokens and is opt-in.
"""

import pytest

from argumenta.adapters.llm.responses import ensure_not_truncated
from argumenta.domain.errors import EvaluationFailedError


class TestTruncationGuard:
    def test_a_truncated_response_says_so_instead_of_failing_the_schema(self) -> None:
        """Thinking shares max_tokens with the answer, so this is the failure
        mode a tight budget produces, and the message has to name it."""
        with pytest.raises(EvaluationFailedError, match="truncated at max_tokens=8000"):
            ensure_not_truncated("max_tokens", 8000)

    def test_a_complete_response_passes(self) -> None:
        for stop_reason in ("end_turn", "tool_use", "stop_sequence", None):
            ensure_not_truncated(stop_reason, 8000)
