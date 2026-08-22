"""Issue #33: the migration chain has to survive the data the release before it
could write. `alembic upgrade head` runs before traffic switches, so a statement
that fails on real rows keeps the buggy container serving."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import Chapter, Submission, User
from argumenta.adapters.db.seed.tutorial import seed_tutorial
from argumenta.domain.enums import SubmissionContext

BEFORE_THE_REACTION_UNIQUE = "c3127ce63329"
"""Initial schema: character_reactions with no unique index, which is what the
first reaction release ran against."""

WITH_THE_REACTION_UNIQUE = "436f0e73948f"  # pragma: allowlist secret
"""The revision that added the index, and where the frozen fallback rows were
written but not yet retired."""


@dataclass(frozen=True)
class ReactionFixture:
    """The three foreign keys a character_reaction needs, resolved once."""

    submission_id: uuid.UUID
    character_id: uuid.UUID


@pytest.fixture
def alembic_config(db_engine: Engine) -> Iterator[Config]:
    """Always leaves the database at head, so a failure here cannot strand the
    rest of the suite on an older schema."""
    config = Config("alembic.ini")
    try:
        yield config
    finally:
        command.upgrade(config, "head")


@pytest.fixture
def reaction_fixture(db_engine: Engine) -> ReactionFixture:
    """Seeded content plus a submission, inserted directly: this is a test about
    SQL, not about auth, track or the submission rules."""
    with Session(db_engine) as session:
        seed_tutorial(session)
        chapter = session.execute(
            select(Chapter.id, Chapter.antagonist_id).where(Chapter.position == 1)
        ).one()
        user = User(email="migration@example.com", nickname="Aluno")
        session.add(user)
        session.flush()
        submission = Submission(
            user_id=user.id,
            chapter_id=chapter.id,
            attempt_number=1,
            context=SubmissionContext.MAIN,
            body="texto do aluno",
            word_count=3,
        )
        session.add(submission)
        session.flush()
        fixture = ReactionFixture(submission_id=submission.id, character_id=chapter.antagonist_id)
        session.commit()
    return fixture


class TestReactionUniqueBackfill:
    def test_upgrade_deduplicates_and_retires_what_the_old_release_wrote(
        self, db_engine: Engine, alembic_config: Config, reaction_fixture: ReactionFixture
    ) -> None:
        command.downgrade(alembic_config, BEFORE_THE_REACTION_UNIQUE)
        _insert_duplicated_beat(db_engine, reaction_fixture)
        _insert_fallback_line(db_engine, reaction_fixture)

        command.upgrade(alembic_config, "head")

        assert _bodies(db_engine, reaction_fixture) == [
            ("fala roteirizada", False),
            ("primeira fala", True),
            ("segunda fala", False),
        ]

    def test_a_tie_on_created_at_still_leaves_one_live_row(
        self, db_engine: Engine, alembic_config: Config, reaction_fixture: ReactionFixture
    ) -> None:
        """Ordering by created_at alone would keep every row of a tie, and the
        CREATE UNIQUE INDEX right after it would fail."""
        command.downgrade(alembic_config, BEFORE_THE_REACTION_UNIQUE)
        _insert_duplicated_beat(db_engine, reaction_fixture, same_instant=True)

        command.upgrade(alembic_config, "head")

        live = [body for body, is_live in _bodies(db_engine, reaction_fixture) if is_live]
        assert len(live) == 1

    def test_a_database_already_at_the_index_still_gets_its_fallback_retired(
        self, db_engine: Engine, alembic_config: Config, reaction_fixture: ReactionFixture
    ) -> None:
        """The dedup had to be edited into the revision that creates the index,
        but retiring the frozen line is a revision of its own: folded into that
        one it would never reach a database already stamped with it."""
        command.downgrade(alembic_config, WITH_THE_REACTION_UNIQUE)
        _insert_fallback_line(db_engine, reaction_fixture)

        command.upgrade(alembic_config, "head")

        assert _bodies(db_engine, reaction_fixture) == [("fala roteirizada", False)]


def _insert_duplicated_beat(
    db_engine: Engine, fixture: ReactionFixture, same_instant: bool = False
) -> None:
    """Two live rows for one beat: the race the first release had, either a
    minute apart or in the same instant."""
    second_created_at = (
        "now() - interval '2 minutes'" if same_instant else "now() - interval '1 minute'"
    )
    with db_engine.begin() as connection:
        connection.execute(
            text(
                f"""
                INSERT INTO character_reactions
                    (submission_id, character_id, beat, body, model, prompt_version,
                     output_tokens, created_at)
                VALUES
                    (:submission, :character, 'convinced', 'primeira fala',
                     'claude-sonnet-5', 'react-v1.0', 10, now() - interval '2 minutes'),
                    (:submission, :character, 'convinced', 'segunda fala',
                     'claude-sonnet-5', 'react-v1.0', 10, {second_created_at})
                """
            ),
            {"submission": fixture.submission_id, "character": fixture.character_id},
        )


def _insert_fallback_line(db_engine: Engine, fixture: ReactionFixture) -> None:
    """The scripted line persisted as `fallback`, which the old code did on
    every engine outage, freezing a generic answer for that beat."""
    with db_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO character_reactions
                    (submission_id, character_id, beat, body, model, prompt_version)
                VALUES
                    (:submission, :character, 'rebuttal', 'fala roteirizada',
                     'fallback', 'scripted')
                """
            ),
            {"submission": fixture.submission_id, "character": fixture.character_id},
        )


def _bodies(db_engine: Engine, fixture: ReactionFixture) -> list[tuple[str, bool]]:
    """(body, still live) for this submission only, so a fixture elsewhere in
    the suite cannot change the answer."""
    with db_engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT body, deleted_at IS NULL
                FROM character_reactions
                WHERE submission_id = :submission
                ORDER BY body
                """
            ),
            {"submission": fixture.submission_id},
        )
        return [(row[0], row[1]) for row in rows]
