import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from argumenta.domain.accounts import ExamTarget, UserAccount
from argumenta.domain.enums import Exam
from argumenta.domain.privacy import DeletionReceipt

Nickname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
"""Trimmed at the edge: whitespace is not a name, and the column is 40."""


class RegisterRequest(BaseModel):
    email: EmailStr
    nickname: Nickname
    password: str = Field(min_length=8, max_length=128)
    accepted_terms: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    code: str
    redirect_uri: str


class UpdateMeRequest(BaseModel):
    nickname: Nickname


class AddTargetRequest(BaseModel):
    exam: Exam
    year: int = Field(ge=2024, le=2100)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    nickname: str
    terms_accepted_at: datetime | None

    @classmethod
    def from_domain(cls, user: UserAccount) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            nickname=user.nickname,
            terms_accepted_at=user.terms_accepted_at,
        )


class TargetResponse(BaseModel):
    id: uuid.UUID
    exam: Exam
    year: int
    is_active: bool

    @classmethod
    def from_domain(cls, target: ExamTarget) -> "TargetResponse":
        return cls(id=target.id, exam=target.exam, year=target.year, is_active=target.is_active)


class MeResponse(BaseModel):
    user: UserResponse
    targets: list[TargetResponse]


class AccountDeletionResponse(BaseModel):
    """202, not 204: the account is unusable at `requested_at`, and the rows are
    gone at `purge_scheduled_for`."""

    requested_at: datetime
    purge_scheduled_for: datetime

    @classmethod
    def from_domain(cls, receipt: DeletionReceipt) -> "AccountDeletionResponse":
        return cls(
            requested_at=receipt.requested_at,
            purge_scheduled_for=receipt.purge_scheduled_for,
        )
