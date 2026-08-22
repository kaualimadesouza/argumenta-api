import uuid
from datetime import datetime
from typing import Protocol

from argumenta.domain.progress import DimensionSample


class StatsRepository(Protocol):
    def dimension_history(self, user_id: uuid.UUID, since: datetime) -> list[DimensionSample]:
        """One sample per graded dimension of every current evaluation in the
        window, oldest first."""
        ...

    def repertoire_praises(self, user_id: uuid.UUID) -> int: ...

    def passed_boss_chapters(self, user_id: uuid.UUID) -> int: ...
