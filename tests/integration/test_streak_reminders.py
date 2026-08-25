import uuid
from collections.abc import Sequence
from datetime import date, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient
from tests.integration.conftest import REGISTER

from argumenta.adapters.db.models.accounts import PushDevice, User
from argumenta.adapters.db.models.habit import DailyActivity
from argumenta.adapters.db.repositories.accounts import SqlAlchemyPushDeviceRepository
from argumenta.adapters.db.repositories.track import SqlAlchemyActivityRepository
from argumenta.application.habit.use_cases.remind_streak_at_risk import RemindStreakAtRiskUseCase
from argumenta.domain.enums import DevicePlatform


class FakePushGateway:
    def __init__(self) -> None:
        self.sent_tokens: list[str] = []
        self.unregistered: list[str] = []

    def send_streak_reminders(self, tokens: Sequence[str]) -> Sequence[str]:
        self.sent_tokens.extend(tokens)
        return [t for t in tokens if t in self.unregistered]


@pytest.fixture
def test_user(client: TestClient, db_engine: Engine) -> uuid.UUID:
    client.post("/auth/register", json=REGISTER)
    with Session(db_engine) as session:
        return session.query(User).filter_by(email=REGISTER["email"]).one().id


def test_job_sends_to_users_at_risk(db_engine: Engine, test_user: uuid.UUID) -> None:
    today = date(2026, 8, 25)
    yesterday = today - timedelta(days=1)

    with Session(db_engine) as session:
        # Create a device
        session.add(PushDevice(user_id=test_user, platform=DevicePlatform.IOS, token="token-123"))
        # Practiced yesterday
        session.add(DailyActivity(user_id=test_user, activity_date=yesterday, submissions_count=1))
        session.commit()

    gateway = FakePushGateway()

    with Session(db_engine) as session:
        use_case = RemindStreakAtRiskUseCase(
            SqlAlchemyActivityRepository(session), SqlAlchemyPushDeviceRepository(session), gateway
        )
        use_case.execute(today)
        session.commit()

    assert gateway.sent_tokens == ["token-123"]

    # Check idempotency
    gateway.sent_tokens.clear()
    with Session(db_engine) as session:
        use_case = RemindStreakAtRiskUseCase(
            SqlAlchemyActivityRepository(session), SqlAlchemyPushDeviceRepository(session), gateway
        )
        use_case.execute(today)
        session.commit()

    assert gateway.sent_tokens == []


def test_job_removes_unregistered_tokens(db_engine: Engine, test_user: uuid.UUID) -> None:
    today = date(2026, 8, 25)
    yesterday = today - timedelta(days=1)

    with Session(db_engine) as session:
        session.add(
            PushDevice(user_id=test_user, platform=DevicePlatform.IOS, token="token-invalid")
        )
        session.add(DailyActivity(user_id=test_user, activity_date=yesterday, submissions_count=1))
        session.commit()

    gateway = FakePushGateway()
    gateway.unregistered = ["token-invalid"]

    with Session(db_engine) as session:
        use_case = RemindStreakAtRiskUseCase(
            SqlAlchemyActivityRepository(session), SqlAlchemyPushDeviceRepository(session), gateway
        )
        use_case.execute(today)
        session.commit()

    assert gateway.sent_tokens == ["token-invalid"]

    with Session(db_engine) as session:
        device = session.query(PushDevice).filter_by(token="token-invalid").one()
        assert device.deleted_at is not None
