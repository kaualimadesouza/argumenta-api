"""All ORM models, imported so Base.metadata sees the full schema (Alembic)."""

from argumenta.adapters.db.models.accounts import (
    AuthIdentity,
    PushDevice,
    User,
    UserExamTarget,
)
from argumenta.adapters.db.models.content import (
    Chapter,
    ChapterBeat,
    Character,
    Story,
    Theme,
)
from argumenta.adapters.db.models.gameplay import (
    ChapterProgress,
    CharacterReaction,
    Draft,
    Evaluation,
    EvaluationAnnotation,
    EvaluationScore,
    Submission,
)
from argumenta.adapters.db.models.habit import DailyActivity, TelemetryEvent

__all__ = [
    "AuthIdentity",
    "Chapter",
    "ChapterBeat",
    "ChapterProgress",
    "Character",
    "CharacterReaction",
    "DailyActivity",
    "Draft",
    "Evaluation",
    "EvaluationAnnotation",
    "EvaluationScore",
    "PushDevice",
    "Story",
    "Submission",
    "TelemetryEvent",
    "Theme",
    "User",
    "UserExamTarget",
]
