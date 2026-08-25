from datetime import date

from argumenta.application.accounts.ports import PushDeviceRepository
from argumenta.application.habit.ports import HabitRepository, PushNotificationGateway


class RemindStreakAtRiskUseCase:
    def __init__(
        self,
        habits: HabitRepository,
        devices: PushDeviceRepository,
        gateway: PushNotificationGateway,
    ) -> None:
        self._habits = habits
        self._devices = devices
        self._gateway = gateway

    def execute(self, today: date) -> None:
        users = self._habits.get_users_with_streak_at_risk(today)
        if not users:
            return

        tokens = self._devices.get_tokens_for_users(users)
        if not tokens:
            return

        unregistered_tokens = self._gateway.send_streak_reminders(tokens)
        if unregistered_tokens:
            self._devices.unregister_many(unregistered_tokens)

        self._habits.mark_streak_reminders_sent(users, today)
