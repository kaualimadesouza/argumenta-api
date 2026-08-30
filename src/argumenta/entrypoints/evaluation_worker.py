"""Worker leg of the async submission flow (issue #68): evaluates one pending
submission outside any HTTP request. A failure never leaves the submission
hanging: it flips to failed (recoverable) in a fresh transaction."""

import logging
import uuid

from sqlalchemy.orm import Session

from argumenta.adapters.db.repositories.accounts import SqlAlchemyExamTargetRepository
from argumenta.adapters.db.repositories.gameplay import (
    SqlAlchemyDailyActivityWriter,
    SqlAlchemyDraftRepository,
    SqlAlchemyEvaluationContextRepository,
    SqlAlchemyProgressWriter,
    SqlAlchemySubmissionRepository,
)
from argumenta.adapters.db.repositories.llm_budget import SqlLlmBudget
from argumenta.adapters.db.session import get_session_factory
from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker
from argumenta.application.evaluation.use_cases import EvaluateArgumentUseCase
from argumenta.application.gameplay.use_cases import (
    EvaluateSubmissionUseCase,
    RecordEvaluationFailureUseCase,
)
from argumenta.presentation.fastapi.dependencies import get_evaluation_engine
from argumenta.settings import get_settings

logger = logging.getLogger(__name__)


def evaluate_submission(submission_id: uuid.UUID) -> None:
    factory = get_session_factory()
    try:
        with factory() as session:
            _build_evaluation(session).execute(submission_id)
            session.commit()
    except Exception:
        logger.exception("evaluation failed: submission=%s", submission_id)
        with factory() as session:
            RecordEvaluationFailureUseCase(
                submissions=SqlAlchemySubmissionRepository(session),
                activity=SqlAlchemyDailyActivityWriter(session),
            ).execute(submission_id)
            session.commit()


def _build_evaluation(session: Session) -> EvaluateSubmissionUseCase:
    settings = get_settings()
    return EvaluateSubmissionUseCase(
        contexts=SqlAlchemyEvaluationContextRepository(session),
        submissions=SqlAlchemySubmissionRepository(session),
        progress=SqlAlchemyProgressWriter(session),
        activity=SqlAlchemyDailyActivityWriter(session),
        drafts=SqlAlchemyDraftRepository(session),
        evaluate=EvaluateArgumentUseCase(
            get_evaluation_engine(),
            SpyllsSpellChecker(),
            SqlLlmBudget(
                session,
                monthly_token_budget=settings.llm_monthly_token_budget,
                alert_ratio=settings.llm_budget_alert_ratio,
            ),
        ),
        exams=SqlAlchemyExamTargetRepository(session),
    )
