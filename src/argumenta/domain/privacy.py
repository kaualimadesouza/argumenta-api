"""LGPD erasure: the one place the universal soft delete does not apply, since
the student's texts are personal data and keeping them is the whole problem."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class DeletionReceipt:
    user_id: uuid.UUID
    requested_at: datetime
    purge_scheduled_for: datetime
    """The account is unusable from `requested_at`; the rows leave at this
    instant. The window is what makes a deletion by mistake recoverable."""


@dataclass(frozen=True)
class PurgeReport:
    user_id: uuid.UUID
    rows_by_table: Mapping[str, int]
    """Rows removed per table tied straight to the account; their own
    dependents (evaluations, scores, annotations) leave by cascade underneath."""

    @property
    def total_rows(self) -> int:
        return sum(self.rows_by_table.values())


def purge_cutoff(now: datetime, grace_days: int) -> datetime:
    """An account that asked to be deleted before this instant gets purged."""
    if grace_days < 0:
        raise ValueError("grace_days cannot be negative")
    return now - timedelta(days=grace_days)
