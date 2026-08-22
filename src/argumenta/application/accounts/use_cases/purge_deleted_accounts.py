from datetime import datetime

from argumenta.application.accounts.ports import AccountPurger
from argumenta.domain.privacy import PurgeReport, purge_cutoff


class PurgeDeletedAccountsUseCase:
    """The sweep behind `DELETE /me`: batched, so one run cannot lock the whole
    table, and idempotent, so a failed run is retried by the next one."""

    def __init__(self, purger: AccountPurger, grace_days: int, batch_size: int) -> None:
        self._purger = purger
        self._grace_days = grace_days
        self._batch_size = batch_size

    def execute(self, now: datetime) -> tuple[PurgeReport, ...]:
        cutoff = purge_cutoff(now, self._grace_days)
        due = self._purger.due_for_purge(cutoff, self._batch_size)
        return tuple(self._purger.purge(user_id) for user_id in due)
