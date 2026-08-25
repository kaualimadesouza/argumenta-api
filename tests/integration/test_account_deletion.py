"""Issue #14: self-service account deletion with purge (LGPD), tests first.
The student's texts are personal data, so the purge is a hard delete and the
suite proves nothing of theirs survives it."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session
from tests.integration.conftest import REGISTER, FakeGoogleGateway, ScriptedEngine, submit_text

from argumenta.adapters.db.base import Base
from argumenta.adapters.db.models import (
    Chapter,
    CharacterReaction,
    Evaluation,
    EvaluationAnnotation,
    PushDevice,
    TelemetryEvent,
    User,
)
from argumenta.adapters.db.repositories.accounts import SqlAlchemyAccountPurger
from argumenta.adapters.db.user_data import USER_DATA_TABLES
from argumenta.application.accounts.use_cases import PurgeDeletedAccountsUseCase
from argumenta.domain.accounts import GoogleIdentity
from argumenta.domain.enums import AnnotationType, DevicePlatform, ReactionBeat, Severity
from argumenta.domain.privacy import PurgeReport, purge_cutoff

GRACE = timedelta(days=7)


def _user(db_engine: Engine, email: str = "aluno@example.com") -> User:
    with Session(db_engine) as session:
        user = session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _cookie(client: TestClient, name: str) -> dict[str, str]:
    """Sent by hand: deleting the account clears the jar, and the point is that
    the token itself is dead, not that the browser forgot it."""
    return {"Cookie": f"{name}={client.cookies[name]}"}


class TestPurgeWindow:
    def test_the_cutoff_is_the_grace_period_before_now(self) -> None:
        now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)

        assert purge_cutoff(now, grace_days=7) == now - GRACE

    def test_no_grace_purges_everything_already_asked_for(self) -> None:
        now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)

        assert purge_cutoff(now, grace_days=0) == now

    def test_a_negative_grace_is_a_configuration_error(self) -> None:
        with pytest.raises(ValueError, match="grace"):
            purge_cutoff(datetime.now(tz=UTC), grace_days=-1)


class TestSelfServiceDeletion:
    def test_deleting_marks_the_account_and_dates_the_purge(
        self, client: TestClient, db_engine: Engine
    ) -> None:
        assert client.post("/auth/register", json=REGISTER).status_code == 201

        response = client.delete("/me")

        assert response.status_code == 202, response.text
        body = response.json()
        requested = datetime.fromisoformat(body["requested_at"])
        assert datetime.fromisoformat(body["purge_scheduled_for"]) - requested == GRACE
        assert _user(db_engine).deleted_at is not None

    def test_the_access_token_dies_with_the_account(self, client: TestClient) -> None:
        """Tokens are stateless, so nothing revokes them: what changes is that
        every authenticated request now asks whether the account still exists."""
        client.post("/auth/register", json=REGISTER)
        headers = _cookie(client, "access_token")
        client.delete("/me")

        assert client.get("/me", headers=headers).status_code == 401
        assert client.get("/track", headers=headers).status_code == 401

    def test_the_refresh_token_cannot_revive_the_account(self, client: TestClient) -> None:
        client.post("/auth/register", json=REGISTER)
        headers = _cookie(client, "refresh_token")
        client.delete("/me")

        assert client.post("/auth/refresh", headers=headers).status_code == 401

    def test_the_deleted_student_cannot_log_in(self, client: TestClient) -> None:
        client.post("/auth/register", json=REGISTER)
        client.delete("/me")

        response = client.post(
            "/auth/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
        )

        assert response.status_code == 401

    def test_the_same_email_can_start_over(self, client: TestClient, db_engine: Engine) -> None:
        client.post("/auth/register", json=REGISTER)
        first = _user(db_engine).id
        client.delete("/me")

        response = client.post("/auth/register", json=REGISTER)

        assert response.status_code == 201, response.text
        assert uuid.UUID(response.json()["id"]) != first

    def test_google_can_sign_up_again_after_deletion(
        self, client: TestClient, google_gateway: FakeGoogleGateway
    ) -> None:
        """The identity row carries a partial unique on (provider, subject), so
        a live row from the deleted account would refuse the new sign up."""
        google_gateway.identity = GoogleIdentity(
            subject="google-123", email="aluno@example.com", email_verified=True
        )
        assert (
            client.post("/auth/google", json={"code": "c", "redirect_uri": "u"}).status_code == 200
        )
        client.delete("/me")

        response = client.post("/auth/google", json={"code": "c", "redirect_uri": "u"})

        assert response.status_code == 200, response.text

    def test_a_deleted_account_stops_receiving_push(
        self, client: TestClient, db_engine: Engine
    ) -> None:
        """A retired device is also what lets the same phone register again: the
        Expo token is unique among live rows."""
        client.post("/auth/register", json=REGISTER)
        user_id = _user(db_engine).id
        with Session(db_engine) as session:
            session.add(
                PushDevice(user_id=user_id, platform=DevicePlatform.ANDROID, token="ExponentToken")
            )
            session.commit()

        client.delete("/me")

        with Session(db_engine) as session:
            device = session.scalars(select(PushDevice)).one()
        assert device.deleted_at is not None

    def test_deleting_twice_needs_a_live_session(self, client: TestClient) -> None:
        client.post("/auth/register", json=REGISTER)
        headers = _cookie(client, "access_token")
        assert client.delete("/me").status_code == 202

        assert client.delete("/me", headers=headers).status_code == 401


class TestPurge:
    def test_the_purge_removes_every_trace_of_the_student(
        self, history: uuid.UUID, client: TestClient, db_engine: Engine
    ) -> None:
        before = _counts(db_engine)
        assert all(before[table] > 0 for table in USER_DATA_TABLES), (
            f"the fixture leaves {[t for t in USER_DATA_TABLES if not before[t]]} empty, "
            "so this test would prove nothing about them"
        )
        client.delete("/me")

        reports = _purge(db_engine, now=datetime.now(tz=UTC) + GRACE + timedelta(minutes=1))

        assert [report.user_id for report in reports] == [history]
        assert _counts(db_engine) == dict.fromkeys(USER_DATA_TABLES, 0)
        with Session(db_engine) as session:
            assert session.scalars(select(User)).all() == []
            chapters = session.scalar(select(func.count()).select_from(Chapter))
        assert chapters, "the story is content, not the student's data"

    def test_the_report_says_what_it_removed(
        self, history: uuid.UUID, client: TestClient, db_engine: Engine
    ) -> None:
        client.delete("/me")

        reports = _purge(db_engine, now=datetime.now(tz=UTC) + GRACE + timedelta(minutes=1))

        report = reports[0]
        assert report.rows_by_table["submissions"] == 1
        assert report.rows_by_table["users"] == 1
        assert report.total_rows > 5

    def test_an_account_inside_the_grace_window_is_kept(
        self, history: uuid.UUID, client: TestClient, db_engine: Engine
    ) -> None:
        """The window is what makes a deletion by mistake recoverable, and the
        student cannot tell the difference: their session is already dead."""
        client.delete("/me")

        assert _purge(db_engine, now=datetime.now(tz=UTC) + timedelta(days=1)) == []
        assert _counts(db_engine)["submissions"] == 1

    def test_a_live_account_is_never_purged(self, history: uuid.UUID, db_engine: Engine) -> None:
        assert _purge(db_engine, now=datetime.now(tz=UTC) + timedelta(days=400)) == []
        assert _counts(db_engine)["submissions"] == 1

    def test_the_purge_leaves_other_students_alone(
        self, history: uuid.UUID, client: TestClient, db_engine: Engine
    ) -> None:
        client.delete("/me")
        assert (
            client.post(
                "/auth/register",
                json={**REGISTER, "email": "outra@example.com", "nickname": "Outra"},
            ).status_code
            == 201
        )
        survivor = _user(db_engine, "outra@example.com").id

        _purge(db_engine, now=datetime.now(tz=UTC) + GRACE + timedelta(minutes=1))

        with Session(db_engine) as session:
            assert [user.id for user in session.scalars(select(User)).all()] == [survivor]

    def test_the_cli_runs_the_sweep(
        self, history: uuid.UUID, client: TestClient, db_engine: Engine
    ) -> None:
        """The only production caller: a scheduled `python -m` run, so it is the
        entry point the test drives."""
        from argumenta.entrypoints import purge_accounts

        client.delete("/me")
        with Session(db_engine) as session:
            session.execute(
                update(User).values(deleted_at=datetime.now(tz=UTC) - timedelta(days=30))
            )
            session.commit()

        purge_accounts.main()

        with Session(db_engine) as session:
            assert session.scalars(select(User)).all() == []


@pytest.fixture
def history(
    game: tuple[TestClient, uuid.UUID],
    engine_double: ScriptedEngine,
    db_engine: Engine,
) -> uuid.UUID:
    """A student with a row in every table that hangs off their account, so the
    purge is measured against data and not against an empty schema."""
    client, chapter_id = game
    assert client.post("/me/targets", json={"exam": "enem", "year": 2027}).status_code == 201
    assert client.put(f"/chapters/{chapter_id}/draft", json={"body": "rascunho"}).status_code == 204
    submission_id = uuid.UUID(submit_text(client, chapter_id).json()["submission_id"])
    user = _user(db_engine)
    with Session(db_engine) as session:
        evaluation_id = session.scalar(
            select(Evaluation.id).where(Evaluation.submission_id == submission_id)
        )
        character_id = session.scalar(select(Chapter.antagonist_id).where(Chapter.id == chapter_id))
        session.add_all(
            [
                PushDevice(user_id=user.id, platform=DevicePlatform.IOS, token="ExpoToken"),
                TelemetryEvent(
                    user_id=user.id,
                    submission_id=submission_id,
                    event_type="paste",
                    payload={"chars": 120},
                ),
                EvaluationAnnotation(
                    evaluation_id=evaluation_id,
                    span_start=0,
                    span_end=7,
                    type=AnnotationType.SPELLING,
                    severity=Severity.WARNING,
                    message="acento",
                    priority=1,
                ),
                CharacterReaction(
                    submission_id=submission_id,
                    character_id=character_id,
                    beat=ReactionBeat.CONVINCED,
                    body="Voce me convenceu.",
                    model="claude-sonnet-5",
                    prompt_version="react-v1.0",
                ),
            ]
        )
        session.commit()
    return user.id


def _counts(db_engine: Engine) -> dict[str, int]:
    with Session(db_engine) as session:
        return {
            table: session.scalar(select(func.count()).select_from(Base.metadata.tables[table]))
            or 0
            for table in USER_DATA_TABLES
        }


def _purge(db_engine: Engine, now: datetime) -> list[PurgeReport]:
    with Session(db_engine) as session:
        use_case = PurgeDeletedAccountsUseCase(
            SqlAlchemyAccountPurger(session), grace_days=7, batch_size=100
        )
        reports = use_case.execute(now)
        session.commit()
    return list(reports)
