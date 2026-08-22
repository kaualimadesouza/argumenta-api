"""The student's own words are interpolated into every prompt, so they are the
one part of a prompt this system does not write."""

import re

_FENCE = re.compile(r"<\s*/?\s*texto\s*/?\s*>", re.IGNORECASE)


def defuse_fence(text: str) -> str:
    """Breaks the <texto> delimiter so the text cannot close its own fence; not a
    general injection guard, the other sections are markdown headings. Length
    preserving: annotation spans are offsets into exactly this string."""
    return _FENCE.sub(lambda match: f"({match.group()[1:-1]})", text)
