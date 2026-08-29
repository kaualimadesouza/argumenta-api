import uuid

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from tests.integration.conftest import FakeGoogleGateway

from argumenta.adapters.db.models import AuthIdentity, User
from argumenta.domain.accounts import GoogleIdentity
from argumenta.domain.enums import AuthProvider

REGISTER = {
    "email": "aluno@example.com",
    "nickname": "Aluno",
    "password": "correct-horse-9",  # pragma: allowlist secret
    "accepted_terms": True,
}


def _register(
    client: TestClient, headers: dict[str, str] | None = None, **overrides: object
) -> dict[str, object]:
    body = {**REGISTER, **overrides}
    response = client.post("/auth/register", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_register_creates_user_and_email_identity(client: TestClient, db_engine: Engine) -> None:
    body = _register(client)

    assert body["email"] == "aluno@example.com"
    assert body["terms_accepted_at"] is not None
    with Session(db_engine) as session:
        user = session.scalar(select(User).where(User.email == "aluno@example.com"))
        assert user is not None
        identity = session.scalar(select(AuthIdentity).where(AuthIdentity.user_id == user.id))
        assert identity is not None
        assert identity.provider == AuthProvider.EMAIL
        assert identity.password_hash is not None
        assert "correct-horse-9" not in identity.password_hash


def test_register_sets_session_cookies(client: TestClient) -> None:
    _register(client)

    me = client.get("/me")
    assert me.status_code == 200
    assert me.json()["user"]["nickname"] == "Aluno"


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    _register(client)

    response = client.post("/auth/register", json=REGISTER)
    assert response.status_code == 409


def test_register_requires_terms(client: TestClient) -> None:
    response = client.post("/auth/register", json={**REGISTER, "accepted_terms": False})
    assert response.status_code == 422


def test_login_with_correct_password(client: TestClient) -> None:
    _register(client)
    client.post("/auth/logout")

    response = client.post(
        "/auth/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
    )
    assert response.status_code == 200
    assert client.get("/me").status_code == 200


def test_login_with_wrong_password_fails(client: TestClient) -> None:
    _register(client)
    client.post("/auth/logout")

    response = client.post(
        "/auth/login", json={"email": REGISTER["email"], "password": "wrong-password-1"}
    )
    assert response.status_code == 401


def test_login_is_rate_limited(client: TestClient) -> None:
    _register(client)
    client.post("/auth/logout")

    for _ in range(5):
        response = client.post(
            "/auth/login", json={"email": REGISTER["email"], "password": "wrong-password-1"}
        )
        assert response.status_code == 401
    blocked = client.post(
        "/auth/login", json={"email": REGISTER["email"], "password": REGISTER["password"]}
    )
    assert blocked.status_code == 429


def test_google_login_creates_account(
    client: TestClient, google_gateway: FakeGoogleGateway
) -> None:
    google_gateway.identity = GoogleIdentity(
        subject="google-sub-1", email="nova@example.com", email_verified=True
    )

    response = client.post(
        "/auth/google", json={"code": "any", "redirect_uri": "http://localhost/cb"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "nova@example.com"
    assert client.get("/me").status_code == 200


def test_google_login_is_idempotent_per_subject(
    client: TestClient, google_gateway: FakeGoogleGateway
) -> None:
    google_gateway.identity = GoogleIdentity(
        subject="google-sub-1", email="nova@example.com", email_verified=True
    )

    first = client.post("/auth/google", json={"code": "any", "redirect_uri": "http://localhost/cb"})
    second = client.post(
        "/auth/google", json={"code": "any", "redirect_uri": "http://localhost/cb"}
    )
    assert first.json()["id"] == second.json()["id"]


def test_google_login_links_to_existing_email_user(
    client: TestClient, google_gateway: FakeGoogleGateway, db_engine: Engine
) -> None:
    registered = _register(client)
    client.post("/auth/logout")
    google_gateway.identity = GoogleIdentity(
        subject="google-sub-2", email=str(REGISTER["email"]), email_verified=True
    )

    response = client.post(
        "/auth/google", json={"code": "any", "redirect_uri": "http://localhost/cb"}
    )
    assert response.status_code == 200
    assert response.json()["id"] == registered["id"]
    with Session(db_engine) as session:
        providers = set(
            session.scalars(
                select(AuthIdentity.provider).where(
                    AuthIdentity.user_id == uuid.UUID(str(registered["id"]))
                )
            )
        )
    assert providers == {AuthProvider.EMAIL, AuthProvider.GOOGLE}


def test_google_login_rejects_unverified_email(
    client: TestClient, google_gateway: FakeGoogleGateway
) -> None:
    google_gateway.identity = GoogleIdentity(
        subject="google-sub-3", email="fake@example.com", email_verified=False
    )

    response = client.post(
        "/auth/google", json={"code": "any", "redirect_uri": "http://localhost/cb"}
    )
    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient) -> None:
    assert client.get("/me").status_code == 401


def test_logout_ends_the_session(client: TestClient) -> None:
    _register(client)
    assert client.get("/me").status_code == 200

    assert client.post("/auth/logout").status_code == 204
    assert client.get("/me").status_code == 401


def test_refresh_renews_the_session(client: TestClient) -> None:
    _register(client)

    response = client.post("/auth/refresh")
    assert response.status_code == 204
    assert "access_token" in client.cookies
    assert client.get("/me").status_code == 200


def test_refresh_without_cookie_fails(client: TestClient) -> None:
    assert client.post("/auth/refresh").status_code == 401


MOBILE = {"X-Argumenta-Client": "mobile"}


def test_register_with_mobile_header_returns_tokens_in_body(client: TestClient) -> None:
    body = _register(client, headers=MOBILE)

    assert body["access_token"]
    assert body["refresh_token"]


def test_register_without_mobile_header_has_no_tokens_in_body(client: TestClient) -> None:
    body = _register(client)

    assert body.get("access_token") is None
    assert body.get("refresh_token") is None


def test_login_with_mobile_header_returns_tokens_in_body(client: TestClient) -> None:
    _register(client)
    client.post("/auth/logout")

    response = client.post(
        "/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
        headers=MOBILE,
    )

    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]


def test_google_login_with_mobile_header_returns_tokens_in_body(
    client: TestClient, google_gateway: FakeGoogleGateway
) -> None:
    google_gateway.identity = GoogleIdentity(
        subject="google-sub-mobile", email="mobile@example.com", email_verified=True
    )

    response = client.post(
        "/auth/google",
        json={"code": "any", "redirect_uri": "http://localhost/cb"},
        headers=MOBILE,
    )

    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]


def test_bearer_token_authenticates_with_no_cookie_at_all(client: TestClient) -> None:
    body = _register(client, headers=MOBILE)
    client.cookies.clear()

    response = client.get("/me", headers={"Authorization": f"Bearer {body['access_token']}"})

    assert response.status_code == 200


def test_refresh_with_bearer_and_no_cookie_returns_tokens_in_body(client: TestClient) -> None:
    body = _register(client, headers=MOBILE)
    client.cookies.clear()

    response = client.post(
        "/auth/refresh", headers={"Authorization": f"Bearer {body['refresh_token']}"}
    )

    assert response.status_code == 200
    refreshed = response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]


def test_refresh_with_cookie_still_returns_204_with_no_body(client: TestClient) -> None:
    _register(client)

    response = client.post("/auth/refresh")

    assert response.status_code == 204
    assert response.content == b""
