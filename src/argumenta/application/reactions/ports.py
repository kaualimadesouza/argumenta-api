import uuid
from dataclasses import dataclass
from typing import Protocol

from argumenta.domain.enums import ReactionBeat, Verdict


@dataclass(frozen=True)
class ReactionRequest:
    character_name: str
    persona_brief: str
    chapter_objective: str
    verdict: Verdict
    student_text: str


@dataclass(frozen=True)
class ReactionText:
    body: str
    model: str
    prompt_version: str
    output_tokens: int | None


@dataclass(frozen=True)
class ReactionContext:
    """Everything the reaction needs about a submission the user owns."""

    verdict: Verdict
    student_text: str
    character_id: uuid.UUID
    character_name: str
    persona_brief: str
    chapter_objective: str
    scripted_rebuttal: str | None
    """First dialogue of the consequence branch, the authored fallback."""


@dataclass(frozen=True)
class StoredReaction:
    beat: ReactionBeat
    character_name: str
    body: str


class ReactionEngine(Protocol):
    def generate(self, request: ReactionRequest) -> ReactionText: ...


class ReactionRepository(Protocol):
    def get_context(
        self, user_id: uuid.UUID, submission_id: uuid.UUID
    ) -> ReactionContext | None: ...

    def find(self, submission_id: uuid.UUID) -> StoredReaction | None: ...

    def store(
        self,
        submission_id: uuid.UUID,
        character_id: uuid.UUID,
        beat: ReactionBeat,
        text: ReactionText,
    ) -> None: ...
