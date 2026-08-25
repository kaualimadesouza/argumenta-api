import uuid
from collections.abc import Sequence
from datetime import date
from typing import Protocol


class HabitRepository(Protocol):
    def get_users_with_streak_at_risk(self, today: date) -> Sequence[uuid.UUID]: ...
    def mark_streak_reminders_sent(self, user_ids: Sequence[uuid.UUID], today: date) -> None: ...


class PushNotificationGateway(Protocol):
    def send_streak_reminders(self, tokens: Sequence[str]) -> Sequence[str]:
        """Sends a generic streak reminder payload to the tokens in chunks.
        Returns the list of tokens that resulted in DeviceNotRegistered."""
        ...
