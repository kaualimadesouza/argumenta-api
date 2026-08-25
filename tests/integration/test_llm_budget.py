import logging
import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import (
    Chapter,
    Character,
    Evaluation,
    Story,
    Submission,
    User,
)
from argumenta.adapters.db.repositories.llm_budget import SqlLlmBudget
from argumenta.domain.enums import (
    ChapterKind,
    ContentStatus,
    SubmissionContext,
    Verdict,
)
from argumenta.domain.errors import LlmBudgetExceededError


def _seed_evaluation(session: Session, input_tokens: int, output_tokens: int) -> None:
    user = User(email=f"u{uuid.uuid4().hex[:8]}@example.com", nickname="U")
    story = Story(
        slug=f"s-{uuid.uuid4().hex[:8]}",
        title="S",
        synopsis="S",
        position=10,
        dimension_floor=40,
        min_average=50,
        status=ContentStatus.PUBLISHED,
    )
    session.add_all([user, story])
    session.flush()
    character = Character(story_id=story.id, name="C", persona_brief="B")
    session.add(character)
    session.flush()
    chapter = Chapter(
        story_id=story.id,
        position=1,
        kind=ChapterKind.CONFRONTO,
        title="T",
        objective="O",
        antagonist_id=character.id,
        min_words=120,
        max_words=250,
        evaluator_brief="E",
    )
    session.add(chapter)
    session.flush()
    submission = Submission(
        user_id=user.id,
        chapter_id=chapter.id,
        attempt_number=1,
        context=SubmissionContext.MAIN,
        body="texto",
        word_count=1,
    )
    session.add(submission)
    session.flush()
    session.add(
        Evaluation(
            submission_id=submission.id,
            is_current=True,
            verdict=Verdict.APPROVED,
            average_score=80,
            floor_value=40,
            min_average=50,
            model="claude-sonnet-5",
            prompt_version="eval-v1.0",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )
    session.commit()


def test_within_budget_passes(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        _seed_evaluation(session, input_tokens=100, output_tokens=100)
        SqlLlmBudget(session, monthly_token_budget=1000).ensure_within_budget()


def test_exhausted_budget_blocks_gracefully(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        _seed_evaluation(session, input_tokens=800, output_tokens=300)
        with pytest.raises(LlmBudgetExceededError):
            SqlLlmBudget(session, monthly_token_budget=1000).ensure_within_budget()


def test_approaching_budget_logs_alert(db_engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
    with Session(db_engine) as session:
        _seed_evaluation(session, input_tokens=500, output_tokens=350)
        with caplog.at_level(logging.WARNING):
            SqlLlmBudget(session, monthly_token_budget=1000).ensure_within_budget()
    assert any("llm budget at" in message for message in caplog.messages)


def test_zero_budget_disables_the_guard(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        _seed_evaluation(session, input_tokens=10_000, output_tokens=10_000)
        SqlLlmBudget(session, monthly_token_budget=0).ensure_within_budget()
