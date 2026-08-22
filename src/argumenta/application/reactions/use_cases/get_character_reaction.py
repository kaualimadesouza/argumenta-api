import uuid
from dataclasses import dataclass

from argumenta.application.evaluation.ports import LlmBudget
from argumenta.application.reactions.ports import (
    ReactionContext,
    ReactionEngine,
    ReactionRepository,
    ReactionRequest,
    ReactionText,
)
from argumenta.domain.enums import ReactionBeat
from argumenta.domain.errors import (
    EvaluationFailedError,
    LlmBudgetExceededError,
    SubmissionNotFoundError,
)
from argumenta.domain.reactions import reaction_beat_for

FALLBACK_MODEL = "fallback"
FALLBACK_PROMPT_VERSION = "scripted"

_CONVINCED_FALLBACK = "{name} guarda a sua folha e assente devagar. Esta bem. Voce me convenceu."
_REBUTTAL_FALLBACK = "{name} balanca a cabeca. Ainda nao me convenceu. Traga um plano concreto."


@dataclass(frozen=True)
class ReactionView:
    beat: ReactionBeat
    character_name: str
    body: str


class GetCharacterReactionUseCase:
    """Get-or-create the character's reaction to a judged submission: at most
    one LLM call per submission, scripted fallback when the engine or the
    monthly budget fails (the reaction is flavor, never a blocker)."""

    def __init__(
        self, reactions: ReactionRepository, engine: ReactionEngine, budget: LlmBudget
    ) -> None:
        self._reactions = reactions
        self._engine = engine
        self._budget = budget

    def execute(self, user_id: uuid.UUID, submission_id: uuid.UUID) -> ReactionView | None:
        context = self._reactions.get_context(user_id, submission_id)
        if context is None:
            raise SubmissionNotFoundError("submission not found for this user")
        beat = reaction_beat_for(context.verdict)
        if beat is None:
            return None
        existing = self._reactions.find(submission_id)
        if existing is not None:
            return ReactionView(
                beat=existing.beat,
                character_name=existing.character_name,
                body=existing.body,
            )
        text = self._generate(context)
        self._reactions.store(submission_id, context.character_id, beat, text)
        return ReactionView(beat=beat, character_name=context.character_name, body=text.body)

    def _generate(self, context: ReactionContext) -> ReactionText:
        try:
            self._budget.ensure_within_budget()
            return self._engine.generate(
                ReactionRequest(
                    character_name=context.character_name,
                    persona_brief=context.persona_brief,
                    chapter_objective=context.chapter_objective,
                    verdict=context.verdict,
                    student_text=context.student_text,
                )
            )
        except (LlmBudgetExceededError, EvaluationFailedError):
            return ReactionText(
                body=_fallback_body(context),
                model=FALLBACK_MODEL,
                prompt_version=FALLBACK_PROMPT_VERSION,
                output_tokens=None,
            )


def _fallback_body(context: ReactionContext) -> str:
    if reaction_beat_for(context.verdict) == ReactionBeat.CONVINCED:
        return _CONVINCED_FALLBACK.format(name=context.character_name)
    if context.scripted_rebuttal is not None:
        return context.scripted_rebuttal
    return _REBUTTAL_FALLBACK.format(name=context.character_name)
