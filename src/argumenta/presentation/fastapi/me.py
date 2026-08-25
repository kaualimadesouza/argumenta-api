import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from argumenta.application.accounts.ports import (
    AccountRepository,
    ExamTargetRepository,
    PushDeviceRepository,
)
from argumenta.application.accounts.use_cases import (
    AddExamTarget,
    AddExamTargetUseCase,
    DeleteAccountUseCase,
    GetMeUseCase,
    RegisterPushDevice,
    RegisterPushDeviceUseCase,
    RemoveExamTarget,
    RemoveExamTargetUseCase,
    SetActiveExamTarget,
    SetActiveExamTargetUseCase,
    UnregisterPushDevice,
    UnregisterPushDeviceUseCase,
    UpdateNickname,
    UpdateNicknameUseCase,
)
from argumenta.presentation.fastapi.dependencies import (
    AppSettings,
    CurrentUserId,
    get_account_repository,
    get_exam_target_repository,
    get_push_device_repository,
)
from argumenta.presentation.fastapi.schemas import (
    AccountDeletionResponse,
    AddTargetRequest,
    MeResponse,
    RegisterPushDeviceRequest,
    TargetResponse,
    UnregisterPushDeviceRequest,
    UpdateMeRequest,
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


@router.delete("", status_code=202)
def delete_me(
    user_id: CurrentUserId,
    response: Response,
    accounts: Accounts,
    settings: AppSettings,
) -> AccountDeletionResponse:
    """LGPD erasure, self-service: the session dies here and the data is purged
    after the grace window (`ARGUMENTA_ACCOUNT_PURGE_GRACE_DAYS`)."""
    receipt = DeleteAccountUseCase(accounts, settings.account_purge_grace_days).execute(user_id)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/auth")
    return AccountDeletionResponse.from_domain(receipt)


@router.patch("")
def update_me(body: UpdateMeRequest, user_id: CurrentUserId, accounts: Accounts) -> UserResponse:
    """The only editable field of the profile: a Google sign-up gets its nickname
    from the e-mail local part, so this is where the student fixes it."""
    user = UpdateNicknameUseCase(accounts).execute(
        UpdateNickname(user_id=user_id, nickname=body.nickname)
    )
    return UserResponse.from_domain(user)


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


PushDevices = Annotated[PushDeviceRepository, Depends(get_push_device_repository)]


@router.post("/push-devices", status_code=201)
def register_push_device(
    body: RegisterPushDeviceRequest, user_id: CurrentUserId, devices: PushDevices
) -> None:
    RegisterPushDeviceUseCase(devices).execute(
        RegisterPushDevice(user_id=user_id, platform=body.platform, token=body.token)
    )


@router.delete("/push-devices", status_code=204)
def unregister_push_device(
    body: UnregisterPushDeviceRequest, user_id: CurrentUserId, devices: PushDevices
) -> None:
    UnregisterPushDeviceUseCase(devices).execute(
        UnregisterPushDevice(user_id=user_id, token=body.token)
    )
