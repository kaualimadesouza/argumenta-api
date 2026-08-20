import httpx
import jwt

from argumenta.domain.accounts import GoogleIdentity
from argumenta.domain.errors import GoogleSignInFailedError

_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # nosec B105 (URL, not a credential)
_VALID_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class HttpGoogleIdentityGateway:
    """Authorization code flow: exchanges the code at Google's token endpoint.

    The id_token signature is NOT re-verified here: it comes straight from
    Google over TLS in the code exchange, which is the standard trust model for
    confidential clients. Issuer and audience are still checked.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    def exchange_code(self, code: str, redirect_uri: str) -> GoogleIdentity:
        if not self._client_id or not self._client_secret:
            raise GoogleSignInFailedError("Google OAuth is not configured")
        try:
            response = httpx.post(
                _TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise GoogleSignInFailedError(str(error)) from error

        id_token = response.json().get("id_token")
        if not isinstance(id_token, str):
            raise GoogleSignInFailedError("token response without id_token")
        claims = jwt.decode(id_token, options={"verify_signature": False})
        if claims.get("iss") not in _VALID_ISSUERS or claims.get("aud") != self._client_id:
            raise GoogleSignInFailedError("id_token issuer/audience mismatch")
        email = claims.get("email")
        subject = claims.get("sub")
        if not isinstance(email, str) or not isinstance(subject, str):
            raise GoogleSignInFailedError("id_token without email/sub")
        return GoogleIdentity(
            subject=subject,
            email=email,
            email_verified=bool(claims.get("email_verified", False)),
        )
