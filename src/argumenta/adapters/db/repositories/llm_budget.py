import logging
from datetime import UTC, datetime

from opentelemetry import metrics
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import CharacterReaction, Evaluation
from argumenta.domain.errors import LlmBudgetExceededError

logger = logging.getLogger(__name__)
_meter = metrics.get_meter(__name__)
_budget_used_ratio = _meter.create_histogram(
    "argumenta.llm.budget_used_ratio",
    description="Fraction of the monthly LLM token budget spent, observed at each check",
)


class SqlLlmBudget:
    """Monthly token cap measured over evaluations + character_reactions
    (issue #7 decision). Cap of 0 disables the guard."""

    def __init__(
        self, session: Session, monthly_token_budget: int, alert_ratio: float = 0.8
    ) -> None:
        self._session = session
        self._budget = monthly_token_budget
        self._alert_ratio = alert_ratio

    def _spent_this_month(self) -> int:
        """Both directions of both callers: a reaction prompt carries the whole
        student text, so its input tokens dominate its own cost."""
        month_start = datetime.now(tz=UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        evaluation_tokens = self._session.scalar(
            select(
                func.coalesce(func.sum(Evaluation.input_tokens), 0)
                + func.coalesce(func.sum(Evaluation.output_tokens), 0)
            ).where(Evaluation.created_at >= month_start, Evaluation.deleted_at.is_(None))
        )
        reaction_tokens = self._session.scalar(
            select(
                func.coalesce(func.sum(CharacterReaction.input_tokens), 0)
                + func.coalesce(func.sum(CharacterReaction.output_tokens), 0)
            ).where(
                CharacterReaction.created_at >= month_start,
                CharacterReaction.deleted_at.is_(None),
            )
        )
        return int(evaluation_tokens or 0) + int(reaction_tokens or 0)

    def ensure_within_budget(self) -> None:
        if self._budget <= 0:
            return
        spent = self._spent_this_month()
        _budget_used_ratio.record(spent / self._budget)
        if spent >= self._budget:
            logger.error("llm budget exhausted: %s of %s tokens this month", spent, self._budget)
            raise LlmBudgetExceededError(
                "monthly correction budget of the beta is exhausted; resets next month"
            )
        if spent >= self._budget * self._alert_ratio:
            logger.warning(
                "llm budget at %.0f%%: %s of %s tokens this month",
                100 * spent / self._budget,
                spent,
                self._budget,
            )
