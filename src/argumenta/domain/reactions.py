"""Which story beat the character's reaction plays for each verdict."""

from argumenta.domain.enums import ReactionBeat, Verdict


def reaction_beat_for(verdict: Verdict) -> ReactionBeat | None:
    """A technical failure gets corrections, not drama: the character only
    reacts when the argument itself was judged."""
    if verdict == Verdict.APPROVED:
        return ReactionBeat.CONVINCED
    if verdict == Verdict.FAILED_PERSUASION:
        return ReactionBeat.REBUTTAL
    return None
