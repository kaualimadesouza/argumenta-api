import uuid
from datetime import timedelta

from argumenta.application.accounts.ports import AccountRepository
from argumenta.domain.errors import AccountNotFoundError
from argumenta.domain.privacy import DeletionReceipt


class DeleteAccountUseCase:
    """Self-service erasure (LGPD): the account stops working now, the rows
    leave when the sweep runs. Nothing here talks to the student's data, so a
    slow purge never blocks the request that asked for it."""

    def __init__(self, accounts: AccountRepository, grace_days: int) -> None:
        self._accounts = accounts
        self._grace_days = grace_days

    def execute(self, user_id: uuid.UUID) -> DeletionReceipt:
        requested_at = self._accounts.soft_delete(user_id)
        if requested_at is None:
            raise AccountNotFoundError("this account was already deleted")
        self._accounts.retire_credentials(user_id)
        return DeletionReceipt(
            user_id=user_id,
            requested_at=requested_at,
            purge_scheduled_for=requested_at + timedelta(days=self._grace_days),
        )
