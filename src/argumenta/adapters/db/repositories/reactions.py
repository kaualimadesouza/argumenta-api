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
from argumenta.application.reactions.ports import (
    ReactionContext,
    ReactionText,
    StoredReaction,
)
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

    def find(
        self, user_id: uuid.UUID, submission_id: uuid.UUID, beat: ReactionBeat
    ) -> StoredReaction | None:
        row = self._session.execute(
            select(CharacterReaction.beat, CharacterReaction.body, Character.name)
            .join(Character, Character.id == CharacterReaction.character_id)
            .join(Submission, Submission.id == CharacterReaction.submission_id)
            .where(
                CharacterReaction.submission_id == submission_id,
                CharacterReaction.beat == beat,
                CharacterReaction.deleted_at.is_(None),
                Submission.user_id == user_id,
                Submission.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            return None
        stored_beat, body, character_name = row
        return StoredReaction(beat=stored_beat, character_name=character_name, body=body)

    def store(
        self,
        submission_id: uuid.UUID,
        character_id: uuid.UUID,
        beat: ReactionBeat,
        reaction: ReactionText,
    ) -> None:
        """Concurrent requests race here, and the partial unique on
        (submission_id, beat) is what decides: the loser keeps its generated
        text and the reader sees the winner's line."""
        self._session.execute(
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
            .on_conflict_do_nothing(
                index_elements=["submission_id", "beat"],
                index_where=text("deleted_at IS NULL"),
            )
        )
        self._session.flush()
