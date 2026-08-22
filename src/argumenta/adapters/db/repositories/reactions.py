import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import (
    Chapter,
    ChapterBeat,
    Character,
    CharacterReaction,
    Evaluation,
    Submission,
)
from argumenta.application.reactions.ports import (
    ReactionContext,
    ReactionText,
    StoredReaction,
)
from argumenta.domain.enums import BeatType, Branch, ReactionBeat


class SqlAlchemyReactionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_context(self, user_id: uuid.UUID, submission_id: uuid.UUID) -> ReactionContext | None:
        row = self._session.execute(
            select(Evaluation.verdict, Submission.body, Character, Chapter.objective, Chapter.id)
            .select_from(Submission)
            .join(Evaluation, Evaluation.submission_id == Submission.id)
            .join(Chapter, Chapter.id == Submission.chapter_id)
            .join(Character, Character.id == Chapter.antagonist_id)
            .where(
                Submission.id == submission_id,
                Submission.user_id == user_id,
                Submission.deleted_at.is_(None),
                Evaluation.is_current,
                Evaluation.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            return None
        verdict, student_text, character, objective, chapter_id = row
        return ReactionContext(
            verdict=verdict,
            student_text=student_text,
            character_id=character.id,
            character_name=character.name,
            persona_brief=character.persona_brief,
            chapter_objective=objective,
            scripted_rebuttal=self._first_consequence_dialogue(chapter_id),
        )

    def _first_consequence_dialogue(self, chapter_id: uuid.UUID) -> str | None:
        return self._session.scalar(
            select(ChapterBeat.body)
            .where(
                ChapterBeat.chapter_id == chapter_id,
                ChapterBeat.branch == Branch.CONSEQUENCE,
                ChapterBeat.beat_type == BeatType.DIALOGUE,
                ChapterBeat.deleted_at.is_(None),
            )
            .order_by(ChapterBeat.position)
            .limit(1)
        )

    def find(self, submission_id: uuid.UUID) -> StoredReaction | None:
        row = self._session.execute(
            select(CharacterReaction.beat, CharacterReaction.body, Character.name)
            .join(Character, Character.id == CharacterReaction.character_id)
            .where(
                CharacterReaction.submission_id == submission_id,
                CharacterReaction.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            return None
        beat, body, character_name = row
        return StoredReaction(beat=beat, character_name=character_name, body=body)

    def store(
        self,
        submission_id: uuid.UUID,
        character_id: uuid.UUID,
        beat: ReactionBeat,
        text: ReactionText,
    ) -> None:
        self._session.add(
            CharacterReaction(
                submission_id=submission_id,
                character_id=character_id,
                beat=beat,
                body=text.body,
                model=text.model,
                prompt_version=text.prompt_version,
                output_tokens=text.output_tokens,
            )
        )
        self._session.flush()
