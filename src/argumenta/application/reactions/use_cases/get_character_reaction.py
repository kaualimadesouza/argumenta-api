import uuid
from dataclasses import dataclass

from argumenta.application.evaluation.ports import LlmBudget
from argumenta.application.reactions.ports import (
    ReactionEngine,
    ReactionRepository,
    ReactionRequest,
)
from argumenta.application.track.ports import ContentRepository
from argumenta.domain.enums import Branch, ReactionBeat
from argumenta.domain.errors import (
    EvaluationFailedError,
    LlmBudgetExceededError,
    SubmissionNotFoundError,
)
from argumenta.domain.reactions import reaction_beat_for, scripted_reaction


@dataclass(frozen=True)
class ReactionView:
    beat: ReactionBeat
    character_name: str
    body: str


class GetCharacterReactionUseCase:
    """Get-or-create the character's reaction to a judged submission: one LLM
    call per submission at most, and an authored line when the engine or the
    monthly budget is unavailable. The scripted line is never stored, so the
    real reaction still arrives once the engine recovers, and
    character_reactions keeps meaning exactly "tokens were spent here"."""

    def __init__(
        self,
        reactions: ReactionRepository,
        content: ContentRepository,
        engine: ReactionEngine,
        budget: LlmBudget,
    ) -> None:
        self._reactions = reactions
        self._content = content
        self._engine = engine
        self._budget = budget

    def execute(self, user_id: uuid.UUID, submission_id: uuid.UUID) -> ReactionView | None:
        context = self._reactions.get_context(user_id, submission_id)
        if context is None:
            raise SubmissionNotFoundError("submission not found for this user")
        beat = reaction_beat_for(context.verdict)
        if beat is None:
            return None

        stored = self._reactions.find(user_id, submission_id, beat)
        if stored is not None:
            return ReactionView(beat=beat, character_name=stored.character_name, body=stored.body)

        try:
            self._budget.ensure_within_budget()
            text = self._engine.generate(
                ReactionRequest(
                    character_name=context.character_name,
                    persona_brief=context.persona_brief,
                    chapter_objective=context.chapter_objective,
                    verdict=context.verdict,
                    student_text=context.student_text,
                )
            )
        except (LlmBudgetExceededError, EvaluationFailedError):
            return ReactionView(
                beat=beat,
                character_name=context.character_name,
                body=scripted_reaction(
                    beat, self._content.list_beats(context.chapter_id, Branch.CONSEQUENCE)
                ),
            )
        self._reactions.store(submission_id, context.character_id, beat, text)
        return ReactionView(beat=beat, character_name=context.character_name, body=text.body)
