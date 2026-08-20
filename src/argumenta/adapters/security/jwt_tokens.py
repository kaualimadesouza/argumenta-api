import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class JwtTokenService:
    """Short-lived access token plus a longer refresh token, both HS256.

    Beta limitation, documented in the README: tokens are stateless, so logout
    clears the httpOnly cookies but cannot revoke a token that was exfiltrated;
    a server-side session store is a fase-2 concern.
    """

    def __init__(self, secret: str, access_ttl_seconds: int, refresh_ttl_seconds: int) -> None:
        self._secret = secret
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds

    def issue_pair(self, user_id: uuid.UUID) -> TokenPair:
        return TokenPair(
            access_token=self._issue(user_id, "access", self._access_ttl),
            refresh_token=self._issue(user_id, "refresh", self._refresh_ttl),
        )

    def _issue(self, user_id: uuid.UUID, kind: str, ttl_seconds: int) -> str:
        now = datetime.now(tz=UTC)
        payload = {
            "sub": str(user_id),
            "kind": kind,
            "iat": now,
            "exp": now + timedelta(seconds=ttl_seconds),
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify(self, token: str, kind: str) -> uuid.UUID | None:
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return None
        if payload.get("kind") != kind:
            return None
        try:
            return uuid.UUID(str(payload["sub"]))
        except (KeyError, ValueError):
            return None
