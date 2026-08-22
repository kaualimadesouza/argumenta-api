"""How much thinking a call is allowed to spend."""

from typing import Literal

Effort = Literal["low", "medium", "high", "xhigh", "max"]
"""Mirrors the SDK's own levels, all five: narrowing it here would quietly
forbid the two settings Anthropic recommends for intelligence-sensitive work.
`high` is the API default."""
