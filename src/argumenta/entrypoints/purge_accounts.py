"""CLI: python -m argumenta.entrypoints.purge_accounts (or `make purge`). The
sweep behind `DELETE /me`, meant to run scheduled: it purges the accounts whose
grace window has passed and reports what it removed."""

import logging
from datetime import UTC, datetime

from argumenta.adapters.db.repositories.accounts import SqlAlchemyAccountPurger
from argumenta.adapters.db.session import session_scope
from argumenta.application.accounts.use_cases import PurgeDeletedAccountsUseCase
from argumenta.settings import get_settings

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    with session_scope() as session:
        reports = PurgeDeletedAccountsUseCase(
            SqlAlchemyAccountPurger(session),
            grace_days=settings.account_purge_grace_days,
            batch_size=settings.account_purge_batch_size,
        ).execute(datetime.now(tz=UTC))
    for report in reports:
        logger.info("purged account %s: %s rows", report.user_id, report.total_rows)
    print(f"purge: {len(reports)} accounts, {sum(r.total_rows for r in reports)} rows")


if __name__ == "__main__":
    main()
