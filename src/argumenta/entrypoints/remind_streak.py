import logging
from datetime import UTC, datetime

from argumenta.adapters.db.repositories.accounts import SqlAlchemyPushDeviceRepository
from argumenta.adapters.db.repositories.track import SqlAlchemyActivityRepository
from argumenta.adapters.db.session import get_session_factory
from argumenta.adapters.notifications.expo import HttpExpoPushGateway
from argumenta.application.habit.use_cases.remind_streak_at_risk import RemindStreakAtRiskUseCase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("remind_streak")


def main() -> None:
    session_factory = get_session_factory()
    today = datetime.now(tz=UTC).date()

    with session_factory() as session:
        queries = SqlAlchemyActivityRepository(session)
        devices = SqlAlchemyPushDeviceRepository(session)
        gateway = HttpExpoPushGateway()

        use_case = RemindStreakAtRiskUseCase(queries, devices, gateway)
        use_case.execute(today)

        session.commit()

    logger.info("Successfully executed streak reminders for %s", today)


if __name__ == "__main__":
    main()
