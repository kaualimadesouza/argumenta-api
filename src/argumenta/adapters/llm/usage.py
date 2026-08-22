"""What counts as billed input on an Anthropic response."""

from anthropic.types import Usage


def billed_input_tokens(usage: Usage) -> int:
    """`usage.input_tokens` excludes cache reads and cache writes, and both are
    billed as input. Summing the three keeps the monthly cap honest the day
    someone turns prompt caching on: today it is the same number."""
    return (
        usage.input_tokens
        + (usage.cache_read_input_tokens or 0)
        + (usage.cache_creation_input_tokens or 0)
    )
