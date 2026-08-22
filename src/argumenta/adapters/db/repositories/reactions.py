import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import (
    Chapter,
    Character,
    CharacterReaction,
    Evaluation,
    Submission,
)
from argumenta.application.reactions.ports import ReactionContext, ReactionText
from argumenta.domain.enums import ReactionBeat


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
                Chapter.deleted_at.is_(None),
                Character.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            return None
        verdict, student_text, character, objective, chapter_id = row
        return ReactionContext(
            verdict=verdict,
            student_text=student_text,
            chapter_id=chapter_id,
            character_id=character.id,
            character_name=character.name,
            persona_brief=character.persona_brief,
            chapter_objective=objective,
        )

    def find_body(self, submission_id: uuid.UUID, beat: ReactionBeat) -> str | None:
        return self._session.scalar(
            select(CharacterReaction.body).where(
                CharacterReaction.submission_id == submission_id,
                CharacterReaction.beat == beat,
                CharacterReaction.deleted_at.is_(None),
            )
        )

    def store_or_get(
        self,
        submission_id: uuid.UUID,
        character_id: uuid.UUID,
        beat: ReactionBeat,
        reaction: ReactionText,
    ) -> str:
        """One statement, so the caller cannot return a line that is not in the
        database. Concurrent requests race here and the partial unique on
        (submission_id, beat) is the arbiter: the loser writes nothing and
        RETURNING hands it the stored line instead of its own text."""
        stored = self._session.execute(
            insert(CharacterReaction)
            .values(
                submission_id=submission_id,
                character_id=character_id,
                beat=beat,
                body=reaction.body,
                model=reaction.model,
                prompt_version=reaction.prompt_version,
                input_tokens=reaction.input_tokens,
                output_tokens=reaction.output_tokens,
            )
            .on_conflict_do_update(
                index_elements=["submission_id", "beat"],
                index_where=text("deleted_at IS NULL"),
                # touching nothing: the stored line wins, and DO UPDATE is what
                # makes RETURNING give it back (DO NOTHING returns no row)
                set_={"updated_at": CharacterReaction.updated_at},
            )
            .returning(CharacterReaction.body)
        ).scalar_one()
        self._session.flush()
        return str(stored)
