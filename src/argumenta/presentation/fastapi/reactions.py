import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from argumenta.application.reactions.use_cases import GetCharacterReactionUseCase
from argumenta.domain.enums import ReactionBeat
from argumenta.presentation.fastapi.dependencies import (
    CurrentUserId,
    get_character_reaction_use_case,
)

router = APIRouter(prefix="/submissions", tags=["reactions"])

ReactionUseCase = Annotated[GetCharacterReactionUseCase, Depends(get_character_reaction_use_case)]


class ReactionResponse(BaseModel):
    beat: ReactionBeat
    character_name: str
    body: str


@router.post("/{submission_id}/reaction", response_model=None)
def character_reaction(
    submission_id: uuid.UUID,
    user_id: CurrentUserId,
    use_case: ReactionUseCase,
) -> ReactionResponse | Response:
    """Get-or-create the character's spoken reaction to a judged submission;
    204 when the verdict earns corrections instead of drama (failed_technical)."""
    view = use_case.execute(user_id, submission_id)
    if view is None:
        return Response(status_code=204)
    return ReactionResponse(beat=view.beat, character_name=view.character_name, body=view.body)
