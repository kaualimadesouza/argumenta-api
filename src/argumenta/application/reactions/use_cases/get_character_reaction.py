import logging
import uuid
from dataclasses import dataclass

from argumenta.application.evaluation.ports import LlmBudget
from argumenta.application.reactions.ports import (
    ReactionContext,
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
from argumenta.domain.reactions import (
    needs_authored_line,
    reaction_beat_for,
    scripted_reaction,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReactionView:
    beat: ReactionBeat
    character_name: str
    body: str
    provisional: bool
    """True for the authored fallback: nothing was stored, and the real
    reaction still arrives once the engine or the budget recovers. The client
    needs this to mark the beat instead of showing two lines with no
    explanation."""


class GetCharacterReactionUseCase:
    """Get-or-create the character's reaction to a judged submission: one LLM
    call per beat at most, and an authored line when the engine or the monthly
    budget is unavailable. The scripted line is never stored, so the real
    reaction still arrives once the engine recovers.

    A row in character_reactions therefore means tokens were spent, but not the
    other way round: a client that times out, or that loses the race for a beat,
    was billed without leaving a row.
    """

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

        stored = self._reactions.find_body(submission_id, beat)
        if stored is not None:
            return self._view(beat, context, stored, provisional=False)

        try:
            self._budget.ensure_within_budget()
            reaction = self._engine.generate(
                ReactionRequest(
                    character_name=context.character_name,
                    persona_brief=context.persona_brief,
                    chapter_objective=context.chapter_objective,
                    verdict=context.verdict,
                    student_text=context.student_text,
                )
            )
        except (LlmBudgetExceededError, EvaluationFailedError) as error:
            logger.warning("character reaction fell back to the authored line: %s", error)
            return self._view(beat, context, self._authored(beat, context), provisional=True)

        body = self._reactions.store_or_get(submission_id, context.character_id, beat, reaction)
        return self._view(beat, context, body, provisional=False)

    def _authored(self, beat: ReactionBeat, context: ReactionContext) -> str:
        """The scene is only read when the beat has a hand written equivalent,
        so an approved student does not pay for a query nobody reads."""
        authored = (
            self._content.list_beats(context.chapter_id, Branch.CONSEQUENCE)
            if needs_authored_line(beat)
            else ()
        )
        return scripted_reaction(beat, authored)

    @staticmethod
    def _view(
        beat: ReactionBeat, context: ReactionContext, body: str, provisional: bool
    ) -> ReactionView:
        """Always the chapter's current antagonist, in every branch: the name
        must not depend on which path produced the line."""
        return ReactionView(
            beat=beat,
            character_name=context.character_name,
            body=body,
            provisional=provisional,
        )
