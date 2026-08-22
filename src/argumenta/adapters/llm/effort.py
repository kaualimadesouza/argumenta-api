"""How much thinking a call is allowed to spend, and what each vendor calls it."""

from typing import Literal

Effort = Literal["low", "medium", "high", "xhigh", "max"]
"""Mirrors the SDK's own levels, all five: narrowing it here would quietly
forbid the two settings Anthropic recommends for intelligence-sensitive work.
`high` is the API default."""

OPENAI_EFFORT: dict[Effort, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "high",
    "max": "high",
}
"""Three levels there against five here, so the top three collapse."""

GOOGLE_THINKING_BUDGET: dict[Effort, int] = {
    "low": 1024,
    "medium": 4096,
    "high": 8192,
    "xhigh": 16384,
    "max": 24576,
}
"""Gemini takes a token budget instead of a level. These are the equivalents we
calibrate against, and calibration is per vendor and model anyway (#35)."""
