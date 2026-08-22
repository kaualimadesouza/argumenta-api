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
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class ReactionContext:
    """Everything the reaction needs about a submission the user owns."""

    verdict: Verdict
    student_text: str
    chapter_id: uuid.UUID
    character_id: uuid.UUID
    character_name: str
    persona_brief: str
    chapter_objective: str


class ReactionEngine(Protocol):
    def generate(self, request: ReactionRequest) -> ReactionText: ...


class ReactionRepository(Protocol):
    def get_context(
        self, user_id: uuid.UUID, submission_id: uuid.UUID
    ) -> ReactionContext | None: ...

    def find_body(self, submission_id: uuid.UUID, beat: ReactionBeat) -> str | None:
        """Per beat, not per submission: consequence_intro and recovery_prompt
        share this table (DER). Only reachable after get_context matched the
        submission to the user, which is where ownership is enforced."""
        ...

    def store_or_get(
        self,
        submission_id: uuid.UUID,
        character_id: uuid.UUID,
        beat: ReactionBeat,
        reaction: ReactionText,
    ) -> str:
        """Returns the line that is actually stored, which is not always the
        one just generated: concurrent calls race and the database decides."""
        ...
