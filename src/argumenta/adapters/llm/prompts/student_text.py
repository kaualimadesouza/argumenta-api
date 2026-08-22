"""The student's own words are interpolated into every prompt, so they are the
one part of a prompt this system does not write."""

import re

_FENCE = re.compile(r"<\s*/?\s*texto\s*>", re.IGNORECASE)


def defuse_fence(text: str) -> str:
    """Neutralizes the <texto> delimiter inside the student's text, so the text
    cannot close its own fence and start addressing the model.

    Length preserving on purpose: the evaluation engine reports annotation spans
    as offsets into exactly this string, and shifting them by one character
    would move every highlight the student sees.
    """
    return _FENCE.sub(lambda match: f"({match.group()[1:-1]})", text)
