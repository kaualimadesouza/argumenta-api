"""Issue #33: the migration chain has to survive the data the release before it
could write. `alembic upgrade head` runs before traffic switches (deploy skill),
so a statement that fails on real rows keeps the buggy container serving.
"""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import Character
from tests.conftest import ScriptedEngine, submit_text

BEFORE_THE_REACTION_UNIQUE = "c3127ce63329"
"""Initial schema: character_reactions with no unique index, which is what the
first reaction release ran against."""


@pytest.fixture
def alembic_config(db_engine: Engine) -> Iterator[Config]:
    """Always leaves the database at head, so a failure here cannot strand the
    rest of the suite on an older schema."""
    config = Config("alembic.ini")
    try:
        yield config
    finally:
        command.upgrade(config, "head")


class TestReactionUniqueBackfill:
    def test_upgrade_deduplicates_and_retires_what_the_old_release_wrote(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
        alembic_config: Config,
    ) -> None:
        client, chapter_id = game
        engine_double.scripted = "approved"
        submission_id = submit_text(client, chapter_id).json()["submission_id"]
        with Session(db_engine) as session:
            character_id = session.scalar(
                select(Character.id).where(Character.name == "Dona Marta")
            )

        command.downgrade(alembic_config, BEFORE_THE_REACTION_UNIQUE)
        _insert_old_release_rows(db_engine, submission_id, character_id)

        command.upgrade(alembic_config, "head")

        assert _bodies(db_engine, deleted=False) == ["primeira fala"], (
            "the line the student already read is the one that survives"
        )
        assert _bodies(db_engine, deleted=True) == ["fala roteirizada", "segunda fala"]


def _insert_old_release_rows(
    db_engine: Engine, submission_id: str, character_id: uuid.UUID | None
) -> None:
    """Two rows for the same beat (the race the first release had) plus a
    scripted line persisted as `fallback`, which the old code did on every
    engine outage."""
    with db_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO character_reactions
                    (submission_id, character_id, beat, body, model, prompt_version,
                     output_tokens, created_at)
                VALUES
                    (:submission, :character, 'convinced', 'primeira fala',
                     'claude-sonnet-5', 'react-v1.0', 10, now() - interval '2 minutes'),
                    (:submission, :character, 'convinced', 'segunda fala',
                     'claude-sonnet-5', 'react-v1.0', 10, now() - interval '1 minute'),
                    (:submission, :character, 'rebuttal', 'fala roteirizada',
                     'fallback', 'scripted', NULL, now())
                """
            ),
            {"submission": submission_id, "character": character_id},
        )


def _bodies(db_engine: Engine, deleted: bool) -> list[str]:
    clause = "IS NOT NULL" if deleted else "IS NULL"
    with db_engine.begin() as connection:
        rows = connection.execute(
            text(f"SELECT body FROM character_reactions WHERE deleted_at {clause} ORDER BY body")
        )
        return [row[0] for row in rows]
