import uuid
from dataclasses import dataclass
from datetime import datetime

from argumenta.domain.enums import Exam


@dataclass(frozen=True)
class UserAccount:
    id: uuid.UUID
    email: str
    nickname: str
    terms_accepted_at: datetime | None


@dataclass(frozen=True)
class ExamTarget:
    id: uuid.UUID
    exam: Exam
    year: int
    is_active: bool


@dataclass(frozen=True)
class GoogleIdentity:
    """What Google asserts about the person after the code exchange."""

    subject: str
    email: str
    email_verified: bool
