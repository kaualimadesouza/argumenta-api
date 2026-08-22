from argumenta.application.accounts.use_cases.add_exam_target import (
    AddExamTarget,
    AddExamTargetUseCase,
)
from argumenta.application.accounts.use_cases.delete_account import DeleteAccountUseCase
from argumenta.application.accounts.use_cases.get_me import GetMeUseCase, MeView
from argumenta.application.accounts.use_cases.login_with_email import (
    LoginWithEmail,
    LoginWithEmailUseCase,
)
from argumenta.application.accounts.use_cases.login_with_google import (
    LoginWithGoogle,
    LoginWithGoogleUseCase,
)
from argumenta.application.accounts.use_cases.purge_deleted_accounts import (
    PurgeDeletedAccountsUseCase,
)
from argumenta.application.accounts.use_cases.register_with_email import (
    RegisterWithEmail,
    RegisterWithEmailUseCase,
)
from argumenta.application.accounts.use_cases.remove_exam_target import (
    RemoveExamTarget,
    RemoveExamTargetUseCase,
)
from argumenta.application.accounts.use_cases.set_active_exam_target import (
    SetActiveExamTarget,
    SetActiveExamTargetUseCase,
)
from argumenta.application.accounts.use_cases.update_nickname import (
    UpdateNickname,
    UpdateNicknameUseCase,
)

__all__ = [
    "AddExamTarget",
    "AddExamTargetUseCase",
    "DeleteAccountUseCase",
    "GetMeUseCase",
    "LoginWithEmail",
    "LoginWithEmailUseCase",
    "LoginWithGoogle",
    "LoginWithGoogleUseCase",
    "MeView",
    "PurgeDeletedAccountsUseCase",
    "RegisterWithEmail",
    "RegisterWithEmailUseCase",
    "RemoveExamTarget",
    "RemoveExamTargetUseCase",
    "SetActiveExamTarget",
    "SetActiveExamTargetUseCase",
    "UpdateNickname",
    "UpdateNicknameUseCase",
]
