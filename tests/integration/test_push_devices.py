import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from tests.integration.conftest import REGISTER

from argumenta.adapters.db.models.accounts import PushDevice, User
from argumenta.domain.enums import DevicePlatform


@pytest.fixture
def registered_user(client: TestClient, db_engine: Engine) -> uuid.UUID:
    assert client.post("/auth/register", json=REGISTER).status_code == 201
    with Session(db_engine) as session:
        user = session.scalar(select(User).where(User.email == REGISTER["email"]))
        assert user is not None
        return user.id


def test_register_push_device(
    client: TestClient, db_engine: Engine, registered_user: uuid.UUID
) -> None:
    response = client.post(
        "/me/push-devices",
        json={"platform": "ios", "token": "ExponentPushToken[1234567890]"},
    )
    assert response.status_code == 201

    with Session(db_engine) as session:
        device = session.query(PushDevice).filter_by(user_id=registered_user).one()
        assert device.platform == DevicePlatform.IOS
        assert device.token == "ExponentPushToken[1234567890]"


def test_register_push_device_idempotent(
    client: TestClient, db_engine: Engine, registered_user: uuid.UUID
) -> None:
    client.post("/me/push-devices", json={"platform": "ios", "token": "Expo[123]"})
    response = client.post("/me/push-devices", json={"platform": "ios", "token": "Expo[123]"})
    assert response.status_code == 201

    with Session(db_engine) as session:
        devices = session.query(PushDevice).filter_by(user_id=registered_user).all()
        assert len(devices) == 1


def test_unregister_push_device(
    client: TestClient, db_engine: Engine, registered_user: uuid.UUID
) -> None:
    client.post("/me/push-devices", json={"platform": "android", "token": "Expo[abc]"})

    response = client.request("DELETE", "/me/push-devices", json={"token": "Expo[abc]"})
    assert response.status_code == 204

    with Session(db_engine) as session:
        devices = (
            session.query(PushDevice)
            .filter(PushDevice.user_id == registered_user, PushDevice.deleted_at.is_(None))
            .all()
        )
        assert len(devices) == 0


def test_unregister_push_device_idempotent(
    client: TestClient, db_engine: Engine, registered_user: uuid.UUID
) -> None:
    response = client.request("DELETE", "/me/push-devices", json={"token": "Expo[non-existent]"})
    assert response.status_code == 204
