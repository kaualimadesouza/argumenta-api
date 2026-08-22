"""Which story beat the character's reaction plays, and what they say when the
AI cannot speak for them."""

from collections.abc import Sequence

from argumenta.domain.enums import BeatType, ReactionBeat, Verdict
from argumenta.domain.track import BeatContent

CONVINCED_FALLBACK = "Esta bem. Voce me convenceu: com esse plano eu topo."
REBUTTAL_FALLBACK = "Ainda nao me convenceu. Traga um plano concreto e conversamos."


def reaction_beat_for(verdict: Verdict) -> ReactionBeat | None:
    """A technical failure gets corrections, not drama: the character only
    reacts when the argument itself was judged."""
    if verdict == Verdict.APPROVED:
        return ReactionBeat.CONVINCED
    if verdict == Verdict.FAILED_PERSUASION:
        return ReactionBeat.REBUTTAL
    return None


def scripted_reaction(beat: ReactionBeat, authored_beats: Sequence[BeatContent]) -> str:
    """The authored line to play when the AI is unavailable. For a rebuttal the
    consequence scene already has the character's answer written by hand, which
    beats anything generic; a convinced beat has no authored equivalent."""
    if beat == ReactionBeat.REBUTTAL:
        authored = next(
            (b.body for b in authored_beats if b.beat_type == BeatType.DIALOGUE),
            None,
        )
        return authored or REBUTTAL_FALLBACK
    return CONVINCED_FALLBACK
