import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from argumenta.domain.accounts import ExamTarget, UserAccount
from argumenta.domain.enums import Exam


class RegisterRequest(BaseModel):
    email: EmailStr
    nickname: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=8, max_length=128)
    accepted_terms: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    code: str
    redirect_uri: str


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
