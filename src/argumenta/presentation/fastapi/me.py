import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from argumenta.application.accounts.ports import AccountRepository, ExamTargetRepository
from argumenta.application.accounts.use_cases import (
    AddExamTarget,
    AddExamTargetUseCase,
    GetMeUseCase,
    RemoveExamTarget,
    RemoveExamTargetUseCase,
    SetActiveExamTarget,
    SetActiveExamTargetUseCase,
)
from argumenta.presentation.fastapi.dependencies import (
    CurrentUserId,
    get_account_repository,
    get_exam_target_repository,
)
from argumenta.presentation.fastapi.schemas import (
    AddTargetRequest,
    MeResponse,
    TargetResponse,
    UserResponse,
)

router = APIRouter(prefix="/me", tags=["me"])

Accounts = Annotated[AccountRepository, Depends(get_account_repository)]
Targets = Annotated[ExamTargetRepository, Depends(get_exam_target_repository)]


@router.get("")
def get_me(user_id: CurrentUserId, accounts: Accounts, targets: Targets) -> MeResponse:
    view = GetMeUseCase(accounts, targets).execute(user_id)
    return MeResponse(
        user=UserResponse.from_domain(view.user),
        targets=[TargetResponse.from_domain(t) for t in view.targets],
    )


@router.post("/targets", status_code=201)
def add_target(body: AddTargetRequest, user_id: CurrentUserId, targets: Targets) -> TargetResponse:
    target = AddExamTargetUseCase(targets).execute(
        AddExamTarget(user_id=user_id, exam=body.exam, year=body.year)
    )
    return TargetResponse.from_domain(target)


@router.delete("/targets/{target_id}", status_code=204)
def remove_target(target_id: uuid.UUID, user_id: CurrentUserId, targets: Targets) -> None:
    RemoveExamTargetUseCase(targets).execute(RemoveExamTarget(user_id=user_id, target_id=target_id))


@router.put("/targets/{target_id}/activate", status_code=204)
def activate_target(target_id: uuid.UUID, user_id: CurrentUserId, targets: Targets) -> None:
    SetActiveExamTargetUseCase(targets).execute(
        SetActiveExamTarget(user_id=user_id, target_id=target_id)
    )
